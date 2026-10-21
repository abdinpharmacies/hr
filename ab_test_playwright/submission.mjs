import assert from 'node:assert/strict';

const states = new Set(['prepending', 'unknown', 'rejected', 'pending', 'saved']);

export function acceptState(value, token, previous = null) {
    if (!value || value.token !== token || value.submission_guard_version !== 1 || !states.has(value.status) ||
        !Number.isInteger(value.local_header_id) || value.local_header_id <= 0 ||
        !Number.isInteger(value.request_revision) || value.request_revision < 1 ||
        !Number.isInteger(value.branch_header_id) || value.branch_header_id < 0 ||
        !Number.isInteger(value.eplus_serial) || value.eplus_serial < 0) throw new Error('Invalid Callcenter submission identity');
    if (['pending', 'saved'].includes(value.status) && (!value.branch_header_id || !value.eplus_serial)) {
        throw new Error('Accepted submission lacks Branch identity');
    }
    if (previous && (previous.local_header_id !== value.local_header_id ||
        previous.request_revision !== value.request_revision ||
        (previous.branch_header_id && previous.branch_header_id !== value.branch_header_id) ||
        (previous.eplus_serial && previous.eplus_serial !== value.eplus_serial) ||
        (previous.status === 'saved' && value.status !== 'saved') ||
        (previous.status === 'pending' && !['pending', 'saved'].includes(value.status)))) {
        throw new Error('Submission identity or status changed unexpectedly');
    }
    return value;
}

export async function submitOnce({ click, readStates, token, result, timeoutMs = 60000, pollMs = 1000 }) {
    if (!token) throw new Error('Missing bill client token');
    if (result.submission && result.submission !== 'NOT_EXECUTED') throw new Error('Submission already attempted');
    result.client_token = token;
    result.submission = 'UNKNOWN';
    let latest = null;
    const deadline = Date.now() + timeoutMs;
    try { await click(); } catch (error) { result.transport_error = error.name || 'TransportError'; }
    do {
        let rows;
        try { rows = await readStates(); } catch { rows = null; }
        if (rows !== null) {
            if (!Array.isArray(rows) || rows.length > 1) throw new Error('Ambiguous submission status response');
            if (rows.length) {
                latest = acceptState(rows[0], token, latest);
                result.invoice_id = latest.local_header_id;
                result.branch_header_id = latest.branch_header_id;
                result.eplus_serial = latest.eplus_serial;
                result.request_revision = latest.request_revision;
                result.submission = latest.status.toUpperCase();
                if (latest.status === 'saved' && !latest.submission_in_progress) return latest;
                if (['rejected', 'prepending'].includes(latest.status)) {
                    throw new Error(`Submission ${result.submission}; original bill retained`);
                }
            }
        }
        if (Date.now() >= deadline) break;
        await new Promise(resolve => setTimeout(resolve, Math.min(pollMs, deadline - Date.now())));
    } while (Date.now() <= deadline);
    throw new Error(`Submission ${result.submission} not confirmed saved; no resubmission performed`);
}

export async function assertSavedInvoice({ rpc, suite, test, result, shortages = {} }) {
    if (result.submission === 'NOT_EXECUTED') return;
    assert.equal(result.submission, 'SAVED');
    const fields = ['id', 'pos_client_token', 'status', 'is_callcenter_order', 'store_id', 'customer_id',
        'employee_id', 'contract_id', 'applied_program_ids', 'total_price', 'total_net_amount', 'cust_pay',
        'company_pay', 'discount', 'total_after_discount', 'promo_discount_amount', 'line_ids',
        'branch_header_id', 'eplus_serial', 'branch_request_revision', 'callcenter_promo_snapshot', 'pos_hr_employee_id'];
    const [header] = await rpc('ab_sales_header', 'read', [[result.invoice_id]], { fields });
    assert.ok(header, 'Saved local invoice is not readable');
    const id = value => Array.isArray(value) ? value[0] : value || null;
    const money = (actual, expected, label) => assert.ok(Number.isFinite(actual) &&
        Math.abs(actual - expected) <= suite.defaults.money_tolerance, `Unexpected ${label}`);
    assert.equal(header.pos_client_token, result.client_token);
    assert.equal(header.status, 'saved');
    assert.equal(header.is_callcenter_order, true);
    assert.equal(header.branch_header_id, result.branch_header_id);
    assert.equal(header.eplus_serial, result.eplus_serial);
    assert.equal(header.branch_request_revision, result.request_revision);
    for (const key of ['store_id', 'customer_id', 'employee_id']) assert.equal(id(header[key]), suite.records[key]);
    assert.equal(id(header.pos_hr_employee_id), suite.records.employee_id);
    const contractId = test.expected.contract ? suite.records.contracts[test.expected.contract].id : null;
    const promotionIds = test.expected.promotion ? [suite.records.promotion_id] : [];
    assert.equal(id(header.contract_id), contractId);
    assert.deepEqual([...header.applied_program_ids].sort(), promotionIds);
    money(header.total_price, test.expected.gross_total, 'gross total');
    money(contractId ? header.cust_pay : header.total_net_amount, test.expected.customer_pay, 'customer payment');
    money(header.promo_discount_amount, test.expected.promotion_discount || 0, 'promotion discount');
    if (contractId) {
        money(header.company_pay, test.expected.company_pay, 'company payment');
        if (!promotionIds.length) {
            money(header.discount, test.expected.contract_discount, 'contract discount');
            money(header.total_after_discount, test.expected.contract_total_after_discount, 'contract total');
        }
    }
    const snapshot = header.callcenter_promo_snapshot;
    assert.ok(snapshot, 'Recorded promotion snapshot is missing');
    assert.deepEqual([...(snapshot.program_ids || [])].sort(), promotionIds);
    money(snapshot.discount, test.expected.promotion_discount || 0, 'recorded promotion discount');
    money(snapshot.net, test.expected.gross_total - (test.expected.promotion_discount || 0), 'recorded promotion net');
    const lines = await rpc('ab_sales_line', 'read', [header.line_ids], {
        fields: ['product_id', 'qty', 'sell_price', 'uom_id', 'unavailable_reason', 'unavailable_reason_other'],
    });
    assert.equal(lines.length, test.expected.line_count);
    const remaining = [...lines];
    for (const expected of test.lines) {
        const product = suite.records.products[expected.product];
        const index = remaining.findIndex(line => id(line.product_id) === product.id && Math.abs(line.qty - expected.qty) < 0.000001);
        assert.ok(index >= 0, 'Expected invoice line is missing');
        const [line] = remaining.splice(index, 1);
        assert.equal(id(line.uom_id), product.uom_id);
        money(line.sell_price, product.unit_price, 'line price');
        assert.equal(line.unavailable_reason || false, shortages[product.id] ? suite.out_of_stock.value : false);
        if (shortages[product.id]) assert.equal(line.unavailable_reason_other, suite.out_of_stock.explanation);
    }
    result.checkpoints.push('saved_local_invoice_and_branch_identity');
}
