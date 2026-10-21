import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { acceptState, assertSavedInvoice, submitOnce } from './submission.mjs';
import { claimDraft, mayRemoveDraft, readDraftWorkspace } from './draft_workspace.mjs';
import { localOdooUrl } from './connection.mjs';
import { assertEmployeeSession, assertPageHealthy, sessionIdentity } from './session_identity.mjs';
import { callcenterLoginUrl, openCallcenterAction } from './startup_navigation.mjs';
import { assertBackendQuote, isBusinessRpc } from './pricing.mjs';

const tests = [];
async function check(name, work) {
    await work();
    tests.push(name);
    console.log('PASS', name);
}
const token = 'qa-original-token';
const state = (status = 'saved', values = {}) => ({
    token, submission_guard_version: 1, local_header_id: 11, branch_header_id: 92,
    eplus_serial: 3001, request_revision: 1, status, submission_in_progress: false, ...values,
});

await check('local connection validation', () => {
    for (const value of ['http://localhost:4095', 'http://127.0.0.11:5069', 'http://[::1]:5069']) assert.ok(localOdooUrl(value));
    for (const value of ['https://example.com', 'http://localhost/path', 'http://name:secret@localhost', 'http://localhost?db=x']) {
        assert.throws(() => localOdooUrl(value));
    }
});
await check('repeat submission and missing token never trigger another click', async () => {
    let clicks = 0;
    for (const values of [{ token: '', result: {} }, { token, result: { submission: 'SAVED' } },
        { token, result: { submission: 'UNKNOWN' } }]) {
        await assert.rejects(submitOnce({ ...values, click: async () => clicks++, readStates: async () => [] }));
    }
    assert.equal(clicks, 0);
});
await check('combined quote verifies selected promotion and financial fields', () => {
    const expected = { contract: 'contractPromo', promotion: true, customer_pay: 225,
        company_pay: 0, contract_discount: 155, contract_total_after_discount: 225, promotion_discount: 155 };
    const quote = { applied_program_id: 2, selected_program_id: 2, allow_promotions: true,
        cust_pay: 225, company_pay: 0, discount: 155, total_after_discount: 225, promo_discount_amount: 155 };
    assertBackendQuote(quote, expected, 2, 0.01);
    for (const values of [{ selected_program_id: false }, { applied_program_id: 9 }, { company_pay: 1 },
        { cust_pay: 226 }, { discount: 1 }, { total_after_discount: 380 }, { promo_discount_amount: 0 }]) {
        assert.throws(() => assertBackendQuote({ ...quote, ...values }, expected, 2, 0.01));
    }
});
await check('inventory product promotion and branch RPCs participate in settling', () => {
    for (const method of ['pos_refresh_pos_balances', 'pos_promotions', 'pos_contract_totals',
        'search_products', 'get_products_promo_status', 'change_store', 'pos_remove_draft_cache']) {
        assert.equal(isBusinessRpc(`http://127.0.0.1/web/dataset/call_kw/model/${method}`, method), true);
    }
    assert.equal(isBusinessRpc('http://127.0.0.1/web/dataset/call_kw/model/pos_save_draft_cache', 'pos_save_draft_cache'), false);
    assert.equal(isBusinessRpc('http://127.0.0.1/web/assets/test.js', ''), false);
});
await check('Callcenter identity and status validation', () => {
    assert.equal(acceptState(state(), token).local_header_id, 11);
    for (const values of [{ token: 'foreign' }, { submission_guard_version: 2 }, { local_header_id: 0 },
        { branch_header_id: 0 }, { eplus_serial: 0 }, { request_revision: 0 }, { status: 'unexpected' }]) {
        assert.throws(() => acceptState(state('saved', values), token));
    }
    for (const values of [{ local_header_id: 12 }, { branch_header_id: 93 }, { eplus_serial: 3002 }, { request_revision: 2 }]) {
        assert.throws(() => acceptState(state('saved', values), token, state()));
    }
    assert.throws(() => acceptState(state('unknown'), token, state()));
});
const records = { employee_id: 668, employee_access_id: 1, user_id: 2, store_id: 135 };
const employeeSession = { token: 'private-fixture-token', state: 'active', profile_id: 1,
    service_user_id: 2, employee: { id: 668 }, store: { id: 104 } };
await check('employee login accepts a different initial branch', () => {
    assert.equal(assertEmployeeSession(employeeSession, records).store_id, 104);
    assert.equal(JSON.stringify(sessionIdentity(employeeSession)).includes(employeeSession.token), false);
});
await check('branch identity is required after selecting the new bill branch', () => {
    assert.throws(() => assertEmployeeSession(employeeSession, records, { requireStore: true }), /Branch selection identity mismatch/);
    assert.equal(assertEmployeeSession({ ...employeeSession, store: { id: 135 } }, records,
        { requireStore: true, token: employeeSession.token }).store_id, 135);
});
await check('denied branch switch cannot pass with the original session branch', () => {
    const denied = { type: 'rpc', method: 'change_store', message: 'Employee is not allowed to work in store QA.' };
    assert.throws(() => assertPageHealthy([denied]), /Employee is not allowed/);
    assert.throws(() => assertEmployeeSession(employeeSession, records,
        { requireStore: true, token: employeeSession.token }), /Branch selection identity mismatch/);
});
await check('wrong employee profile service user and invalid sessions are rejected', () => {
    for (const values of [{ employee: { id: 48 } }, { profile_id: 7 }, { service_user_id: 3 },
        { state: 'locked' }, { token: '' }, { store: { id: 0 } }]) {
        assert.throws(() => assertEmployeeSession({ ...employeeSession, ...values }, records), /Employee login identity mismatch/);
    }
    assert.throws(() => assertEmployeeSession(employeeSession, records, { token: 'another-private-token' }),
        error => !error.message.includes(employeeSession.token) && !error.message.includes('another-private-token'));
});
await check('page and translation errors remain failures with resource paths', () => {
    assertPageHealthy([]);
    assert.throws(() => assertPageHealthy([{ type: 'http', path: '/web/webclient/translations', message: 'HTTP 404' },
        { type: 'pageerror', message: 'Error while fetching translations' }]),
    /Page\/resource errors: http \/web\/webclient\/translations: HTTP 404; pageerror: Error while fetching translations/);
});
await check('one click, pending then saved', async () => {
    let clicks = 0;
    let reads = 0;
    const result = {};
    await submitOnce({ token, result, click: async () => clicks++,
        readStates: async () => [state(++reads === 1 ? 'pending' : 'saved')], timeoutMs: 100, pollMs: 1 });
    assert.equal(clicks, 1);
    assert.equal(result.submission, 'SAVED');
    assert.equal(result.invoice_id, 11);
    assert.equal(result.branch_header_id, 92);
});
await check('lost click response reconciles without resubmission', async () => {
    let clicks = 0;
    const result = {};
    await submitOnce({ token, result, click: async () => { clicks++; throw new Error('Lost response'); },
        readStates: async () => [state()], timeoutMs: 20, pollMs: 1 });
    assert.equal(clicks, 1);
    assert.equal(result.submission, 'SAVED');
});
await check('transient status transport failure can recover', async () => {
    let reads = 0;
    await submitOnce({ token, result: {}, click: async () => {}, readStates: async () => {
        if (++reads === 1) throw new Error('Temporary network failure');
        return [state()];
    }, timeoutMs: 100, pollMs: 1 });
});
await check('rejected and unsubmitted outcomes are not passes', async () => {
    for (const status of ['rejected', 'prepending']) {
        const result = {};
        await assert.rejects(submitOnce({ token, result, click: async () => {},
            readStates: async () => [state(status, { branch_header_id: 0, eplus_serial: 0 })], timeoutMs: 10, pollMs: 1 }));
        assert.equal(result.submission, status.toUpperCase());
    }
});
await check('pending unknown and empty timeouts retain uncertainty', async () => {
    for (const rows of [[state('pending')], [state('unknown', { branch_header_id: 0, eplus_serial: 0 })], []]) {
        let clicks = 0;
        const result = {};
        await assert.rejects(submitOnce({ token, result, click: async () => clicks++,
            readStates: async () => rows, timeoutMs: 2, pollMs: 1 }));
        assert.equal(clicks, 1);
        assert.notEqual(result.submission, 'SAVED');
    }
});
await check('wrong token, duplicate results, revision drift rejected', async () => {
    for (const rows of [[state('saved', { token: 'other' })], [state(), state()], { token: state() }]) {
        await assert.rejects(submitOnce({ token, result: {}, click: async () => {}, readStates: async () => rows, timeoutMs: 2 }));
    }
    let count = 0;
    await assert.rejects(submitOnce({ token, result: {}, click: async () => {},
        readStates: async () => [++count === 1 ? state('pending') : state('saved', { request_revision: 2 })], timeoutMs: 100, pollMs: 1 }));
});
await check('saved invoice validation uses local identity and frozen snapshot', async () => {
    const suite = { defaults: { money_tolerance: 0.01 }, records: { store_id: 4, customer_id: 5, employee_id: 6,
        promotion_id: 8, contracts: {}, products: { promo: { id: 7, uom_id: 1, unit_price: 100 } } } };
    const test = { expected: { contract: null, promotion: true, gross_total: 100, customer_pay: 90, promotion_discount: 10, line_count: 1 },
        lines: [{ product: 'promo', qty: 1 }] };
    const header = { id: 11, pos_client_token: token, status: 'saved', is_callcenter_order: true,
        store_id: [4, 'QA'], customer_id: [5, 'QA'], employee_id: [6, 'QA'], contract_id: false,
        pos_hr_employee_id: [6, 'QA'],
        applied_program_ids: [8], branch_header_id: 92, eplus_serial: 3001, branch_request_revision: 1,
        total_price: 100, total_net_amount: 90, promo_discount_amount: 10, line_ids: [12],
        callcenter_promo_snapshot: { program_ids: [8], discount: 10, net: 90 } };
    const line = { product_id: [7, 'QA'], qty: 1, sell_price: 100, uom_id: [1, 'BOX'], unavailable_reason: false };
    const rpc = async model => model === 'ab_sales_header' ? [header] : [line];
    const result = { submission: 'SAVED', invoice_id: 11, client_token: token, branch_header_id: 92,
        eplus_serial: 3001, request_revision: 1, checkpoints: [] };
    await assertSavedInvoice({ rpc, suite, test, result });
    assert.ok(result.checkpoints.includes('saved_local_invoice_and_branch_identity'));
    header.branch_header_id = 999;
    await assert.rejects(assertSavedInvoice({ rpc, suite, test, result }));
});
await check('draft claim and cleanup refuse foreign or attempted drafts', () => {
    const draft = { id: token, header: { pos_client_token: token, store_id: 4 }, lines: [] };
    const workspace = { selectedId: token, bills: [draft] };
    assert.equal(claimDraft(workspace, new Set(), 4).id, token);
    assert.throws(() => claimDraft(workspace, new Set([token]), 4));
    assert.throws(() => claimDraft(workspace, new Set(), 5));
    assert.equal(mayRemoveDraft(workspace, token, new Set([token]), new Set()), true);
    assert.equal(mayRemoveDraft(workspace, token, new Set(), new Set()), false);
    assert.equal(mayRemoveDraft(workspace, token, new Set([token]), new Set([token])), false);
    draft.submission = { attempted: true };
    assert.equal(mayRemoveDraft(workspace, token, new Set([token]), new Set()), false);
});

process.env.PLAYWRIGHT_BROWSERS_PATH ??= '/opt/playwright/browsers';
const require = createRequire('/opt/playwright/package.json');
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true });
try {
    const context = await browser.newContext();
    const page = await context.newPage();
    for (const scenario of ['saved', 'rejected', 'pending', 'lost_response', 'timeout']) {
        await check(`real Chromium submission fixture ${scenario} clicks only once`, async () => {
            let requests = 0;
            await page.route('http://127.0.0.1/posting/**', async route => {
                if (new URL(route.request().url()).pathname === '/posting/pos_submit') {
                    requests++;
                    if (['lost_response', 'timeout'].includes(scenario)) return route.abort();
                    return route.fulfill({ json: { result: scenario } });
                }
                return route.fulfill({ contentType: 'text/html', body:
                    '<button onclick="fetch(\'/posting/pos_submit\',{method:\'POST\'}).catch(()=>{})">Submit (F10)</button>' });
            });
            await page.goto('http://127.0.0.1/posting/fixture');
            const result = { submission: 'NOT_EXECUTED' };
            const submit = () => submitOnce({ token, result,
                click: () => page.getByRole('button', { name: 'Submit (F10)', exact: true }).click(),
                readStates: async () => requests && scenario !== 'timeout'
                    ? [state(scenario === 'lost_response' ? 'saved' : scenario)] : [], timeoutMs: 250, pollMs: 10 });
            if (['saved', 'lost_response'].includes(scenario)) {
                await submit();
                assert.equal(result.submission, 'SAVED');
            } else {
                await assert.rejects(submit());
                assert.equal(result.submission, scenario === 'timeout' ? 'UNKNOWN' : scenario.toUpperCase());
            }
            await assert.rejects(submit(), /already attempted/);
            assert.equal(requests, 1);
            await page.unroute('http://127.0.0.1/posting/**');
        });
    }
    await check('real Chromium login opens Sales directly without reloading its RPC responses', async () => {
        const origin = 'http://127.0.0.1';
        let actionLoads = 0;
        let homeLoads = 0;
        await page.route(origin + '/**', async route => {
            const url = new URL(route.request().url());
            if (url.pathname === '/web/login') {
                assert.equal(url.searchParams.get('db'), 'qa_callcenter');
                assert.equal(url.searchParams.get('redirect'), '/odoo/action-218');
                return route.fulfill({ contentType: 'text/html', body:
                    '<button onclick="location.href=new window.URL(location.href).searchParams.get(\'redirect\')">Login</button>' });
            }
            if (url.pathname === '/odoo/action-218') {
                actionLoads++;
                return route.fulfill({ contentType: 'text/html', body:
                    '<div class="ab_pos_hr_overlay">Employee Login</div><script>window.rpc=fetch("/web/dataset/call_kw/fixture/read").then(r=>r.json());</script>' });
            }
            if (url.pathname === '/web/dataset/call_kw/fixture/read') {
                return route.fulfill({ json: { result: 'intact' } });
            }
            if (url.pathname === '/odoo') homeLoads++;
            return route.fulfill({ contentType: 'text/html', body: 'Home' });
        });
        await page.goto(callcenterLoginUrl(origin, 'qa_callcenter', 218));
        await page.getByRole('button', { name: 'Login', exact: true }).click();
        await page.waitForURL(origin + '/odoo/action-218');
        await page.locator('.ab_pos_hr_overlay').waitFor();
        await openCallcenterAction(page, origin, 218);
        assert.equal(await page.evaluate(() => window.rpc.then(body => body.result)), 'intact');
        assert.equal(actionLoads, 1);
        assert.equal(homeLoads, 0);
        await page.goto(origin + '/odoo');
        await openCallcenterAction(page, origin, 218);
        assert.equal(actionLoads, 2);
        await page.unroute(origin + '/**');
    });
    await page.route('http://127.0.0.1/fixture', route => route.fulfill({ contentType: 'text/html',
        body: '<button id="commit">Commit</button><script>window.clicks=0;document.querySelector("button").onclick=()=>window.clicks++;</script>' }));
    await page.goto('http://127.0.0.1/fixture');
    await check('real Chromium commit click is performed exactly once', async () => {
        await submitOnce({ token, result: {}, click: () => page.locator('#commit').click(),
            readStates: async () => [state()], timeoutMs: 100 });
        assert.equal(await page.evaluate(() => window.clicks), 1);
    });
    await check('real Chromium reads the employee-scoped workspace only', async () => {
        await page.evaluate(token => {
            const key = 'ab_sales_pos_cache_v1_2_user_2_employee_3';
            sessionStorage.setItem(key + '_workspace', JSON.stringify([{ id: token }]));
            sessionStorage.setItem(key + '_selection', token);
            sessionStorage.setItem('ab_sales_pos_cache_v1_2_user_2_employee_99_workspace', '[{"id":"foreign"}]');
        }, token);
        assert.deepEqual(await readDraftWorkspace(page, { user_id: 2, employee_id: 3 }), { bills: [{ id: token }], selectedId: token });
    });
    await context.close();
} finally {
    await browser.close();
}
console.log(JSON.stringify({ passed: tests.length, scope: 'Isolated simulations and browser fixture; no Odoo login or business posting' }));
