// Normal UI submission; status reads never replay the submit request.
export async function submitOnce({ page, rpc, token, result, timeoutMs = 60000, pollMs = 1000 }) {
    if (!token) throw new Error('Missing bill client token');
    if (result.submission !== 'NOT_EXECUTED') throw new Error('Submission already attempted');
    const button = page.locator('.o_ab_sales_pos_submit_dialog').getByRole('button', { name: 'Submit (F10)', exact: true });
    await button.waitFor();
    result.submission = 'UNKNOWN'; // Protect the bill even if the click or response times out.
    result.client_token = token;
    let responseBody;
    const listener = async response => {
        if (!response.url().endsWith('/pos_submit')) return;
        const params = response.request().postDataJSON()?.params;
        const payload = params?.kwargs?.payload || params?.kwargs || params?.args?.[0];
        if (payload?.header?.pos_client_token !== token) return;
        try { responseBody = await response.json(); } catch { /* Resolve through status lookup. */ }
    };
    page.on('response', listener);
    const deadline = Date.now() + timeoutMs;
    try {
        try { await button.click({ timeout: Math.min(timeoutMs, 15000) }); }
        catch { /* A timed-out click may already have reached the server. Do not repeat it. */ }
        do {
            let state;
            try { state = (await rpc('ab_sales_pos_api', 'pos_submission_status', [], { tokens: [token] }))?.[token]; }
            catch { /* A transient read failure does not authorize another submission. */ }
            state ||= responseBody?.result;
            if (state) {
                result.invoice_id = state.id || state.recovery_header_id || state.pos_header_id || result.invoice_id;
                result.eplus_serial = state.eplus_serial || result.eplus_serial || null;
                result.submission = String(state.status || (state.pos_header_id ? 'prepending' : 'unknown')).toUpperCase();
                if (state.status === 'saved' && result.invoice_id && !state.submission_in_progress) return;
                if (['rejected', 'prepending'].includes(state.status) || state.pos_header_id)
                    throw new Error(`Submission ${result.submission}; invoice retained for review`);
            }
            if (responseBody?.error) {
                result.submission = 'REJECTED';
                throw new Error(responseBody.error.data?.message || responseBody.error.message);
            }
            if (Date.now() >= deadline) break;
            await new Promise(resolve => setTimeout(resolve, Math.min(pollMs, deadline - Date.now())));
        } while (Date.now() <= deadline);
        throw new Error(`Submission ${result.submission} after timeout; not retried`);
    } finally { page.off('response', listener); }
}

export async function assertSavedInvoice({ rpc, suite, test, result, shortages = {} }) {
    if (result.submission === 'NOT_EXECUTED') return;
    if (result.submission !== 'SAVED' || !result.invoice_id) throw new Error('No confirmed saved invoice to verify');
    const fields = ['id', 'pos_client_token', 'status', 'store_id', 'customer_id', 'employee_id', 'contract_id',
        'applied_program_ids', 'total_price', 'total_net_amount', 'cust_pay', 'company_pay', 'discount',
        'total_after_discount', 'promo_discount_amount', 'line_ids'];
    const rows = await rpc('ab_sales_header', 'read', [[result.invoice_id]], { fields });
    const h = rows?.[0];
    const id = value => Array.isArray(value) ? value[0] : value || null;
    const eq = (a, b, name) => { if (a !== b) throw new Error(`${name}: expected ${b}, got ${a}`); };
    const money = (a, b, name) => {
        if (!Number.isFinite(a) || !Number.isFinite(b) || Math.abs(a - b) > suite.defaults.money_tolerance)
            throw new Error(`${name}: expected ${b}, got ${a}`);
    };
    if (!h) throw new Error('Saved invoice is not readable');
    eq(h.pos_client_token, result.client_token, 'invoice token');
    eq(h.status, 'saved', 'invoice status');
    for (const key of ['store_id', 'customer_id', 'employee_id']) eq(id(h[key]), suite.records[key], key);
    eq(id(h.contract_id), test.expected.contract_id || null, 'contract');
    eq(JSON.stringify([...h.applied_program_ids].sort()), JSON.stringify([...test.expected.applied_promotion_ids].sort()), 'promotions');
    money(h.total_price, test.expected.gross_total, 'saved gross');
    money(h.contract_id ? h.cust_pay : h.total_net_amount, test.expected.customer_pay, 'saved customer payment');
    money(h.promo_discount_amount, test.expected.promotion_discount || 0, 'saved promotion discount');
    if (test.expected.contract_id) {
        money(h.company_pay, test.expected.company_pay, 'saved company payment');
        // Combined pricing includes promotion discounts in the contract totals.
        if (!test.expected.applied_promotion_ids.length) {
            money(h.discount, test.expected.contract_discount, 'saved contract discount');
            money(h.total_after_discount, test.expected.contract_total_after_discount, 'saved contract net');
        }
    }
    const lines = await rpc('ab_sales_line', 'read', [h.line_ids], { fields: ['product_id', 'qty', 'sell_price', 'uom_id', 'unavailable_reason', 'unavailable_reason_other'] });
    eq(lines.length, test.expected.line_count, 'saved line count');
    const remaining = [...lines];
    for (const expected of test.lines) {
        const index = remaining.findIndex(l => id(l.product_id) === expected.product_id && Math.abs(l.qty - expected.qty) <= 0.000001);
        if (index < 0) throw new Error(`Missing saved line: ${expected.product_id} qty ${expected.qty}`);
        const [line] = remaining.splice(index, 1);
        money(line.sell_price, suite.records.products.find(p => p.id === expected.product_id).unit_price, 'saved unit price');
        eq(id(line.uom_id), 1, 'saved UoM');
        const shortage = shortages[expected.product_id];
        eq(line.unavailable_reason || false, shortage ? suite.out_of_stock.value : false, 'shortage reason');
        if (shortage) eq(line.unavailable_reason_other, suite.out_of_stock.explanation, 'shortage explanation');
    }
    if (remaining.length) throw new Error('Unexpected saved lines');
    result.checkpoints.push('saved_invoice');
}
