import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { localOdooUrl } from './connection.mjs';
import { claimDraft, mayRemoveDraft, readDraftWorkspace } from './draft_workspace.mjs';
import { assertSavedInvoice, submitOnce } from './submission.mjs';
import { assertEmployeeSession, assertPageHealthy, sessionIdentity } from './session_identity.mjs';
import { callcenterLoginUrl, openCallcenterAction } from './startup_navigation.mjs';
import { assertBackendQuote, isBusinessRpc } from './pricing.mjs';

const require = createRequire('/opt/playwright/package.json');
process.env.PLAYWRIGHT_BROWSERS_PATH ??= '/opt/playwright/browsers';
const { chromium, expect } = require('@playwright/test');
const configuration = JSON.parse(readFileSync(0, 'utf8'));
const { suite, metadata } = configuration;
const base = localOdooUrl(configuration.url);
const report = { suite_id: suite.suite_id, database: configuration.database,
    mode: suite.cases.some(test => test.steps.some(step => step.action === 'submit')) ? 'submit' : 'preview',
    authentication: { odoo_login_count: 0, employee_login_count: 0 }, cases: [], errors: [], protected_draft_ids: [], submitted_invoices: [] };
const owned = new Set();
const protectedTokens = new Set();
const tasks = new Set();
const pricing = new Set();
const requestOwners = new WeakMap();
let lastPricing = Date.now();
let browser;
let context;
let page;
let employeeToken;
let employeeSession;
let active = report;
let blocked;
let submitAllowed = false;
let waitForRpc = async () => {};
let detachResponse = () => {};
const safe = error => {
    let text = String(error?.message || error).slice(0, 6000);
    for (const secret of [configuration.password, configuration.pin, employeeToken]) {
        if (secret) text = text.split(secret).join('[REDACTED]');
    }
    return text;
};
const save = () => writeFileSync(join(configuration.output, 'results.json'), JSON.stringify(report, null, 2), { mode: 0o600 });
const money = (actual, expected, label) => {
    if (!Number.isFinite(actual) || !Number.isFinite(expected) || Math.abs(actual - expected) > suite.defaults.money_tolerance) {
        throw new Error(`${label}: expected ${expected}, received ${actual}`);
    }
};
const amount = text => Number(text.replace(/,/g, '').trim());
const expectedPromotions = test => test.expected.promotion ? [suite.records.promotion_id] : [];

try {
    browser = await chromium.launch({ headless: !configuration.headed, slowMo: configuration.headed ? 100 : 0 });
    context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    page = await context.newPage();
    page.setDefaultTimeout(15000);
    await page.route('**/web/dataset/call_kw/**', async route => {
        let method;
        try { method = route.request().postDataJSON()?.params?.method; } catch { method = null; }
        if (['pos_submit', 'pos_retry'].includes(method) && !submitAllowed) {
            active.errors.push({ type: 'unexpected_submission', message: 'Submission blocked outside an explicit submit action' });
            return route.abort('blockedbyclient');
        }
        return route.continue();
    });
    const methodOf = request => {
        try { return request.postDataJSON()?.params?.method || ''; } catch { return ''; }
    };
    page.on('request', request => {
        requestOwners.set(request, active);
        const method = methodOf(request);
        if (new URL(request.url()).pathname === '/web/login' && request.method() === 'POST') report.authentication.odoo_login_count++;
        if (method === 'employee_login') report.authentication.employee_login_count++;
        if (isBusinessRpc(request.url(), method)) {
            pricing.add(request);
            lastPricing = Date.now();
        }
    });
    const finish = request => { if (pricing.delete(request)) lastPricing = Date.now(); };
    page.on('requestfinished', finish);
    page.on('requestfailed', request => {
        finish(request);
        if (!request.failure()?.errorText?.includes('ERR_ABORTED')) {
            (requestOwners.get(request) || active).errors.push({ type: 'network', message: safe(request.failure()?.errorText || 'Request failed'),
                path: new URL(request.url()).pathname });
        }
    });
    page.on('pageerror', error => active.errors.push({ type: 'pageerror', message: safe(error) }));
    page.on('console', message => {
        if (message.type() === 'error') active.errors.push({ type: 'console', message: safe(message.text()) });
    });
    const onResponse = response => {
        if (response.status() >= 400 && new URL(response.url()).origin === base.origin) {
            (requestOwners.get(response.request()) || active).errors.push({ type: 'http',
                path: new URL(response.url()).pathname, message: `HTTP ${response.status()}` });
        }
        if (!response.url().includes('/web/dataset/call_kw/')) return;
        const owner = requestOwners.get(response.request()) || active;
        const task = (async () => {
            try {
                const body = await response.json();
                const method = methodOf(response.request());
                if (body.error) {
                    const message = safe(body.error.data?.message || body.error.message);
                    owner.errors.push({ type: 'rpc', method, message });
                    if (/employee.*session.*(missing|expired|required)|valid employee session/i.test(message)) {
                        blocked = 'Employee session missing or expired; no automatic login';
                    }
                }
                if (['employee_login', 'change_store'].includes(method) && body.result) {
                    employeeSession = body.result;
                    if (method === 'employee_login') employeeToken = body.result.token;
                    const actual = sessionIdentity(body.result);
                    report.session_identity = { expected: { employee_id: suite.records.employee_id,
                        employee_access_id: suite.records.employee_access_id, user_id: suite.records.user_id,
                        store_id: suite.records.store_id, state: 'active' }, actual };
                    if (method === 'employee_login') report.login_identity = actual;
                    try {
                        assertEmployeeSession(body.result, suite.records, { requireStore: method === 'change_store', token: employeeToken });
                    } catch (error) {
                        owner.errors.push({ type: 'identity', message: safe(error) });
                    }
                }
            } catch (error) {
                owner.errors.push({ type: 'rpc_response', path: new URL(response.url()).pathname,
                    message: safe(error) });
            }
        })();
        tasks.add(task);
        task.finally(() => tasks.delete(task));
    };
    page.on('response', onResponse);
    detachResponse = () => page.off('response', onResponse);
    const rpc = async (model, method, args = [], kwargs = {}) => {
        const response = await context.request.post(`${base.origin}/web/dataset/call_kw/${model}/${method}`, {
            timeout: 10000,
            data: { jsonrpc: '2.0', method: 'call', id: 1, params: { model, method, args,
                kwargs: { context: { lang: 'en_US' }, ...kwargs } } },
        });
        const body = await response.json();
        if (body.error) throw new Error(body.error.data?.message || body.error.message);
        return body.result;
    };
    const settle = async () => {
        const start = Date.now();
        await expect.poll(() => pricing.size === 0 && Date.now() - Math.max(start, lastPricing) >= 750,
            { timeout: 45000, message: 'Wait for browser RPCs, inventory refresh, and debounced pricing' }).toBe(true);
        await Promise.all([...tasks]);
    };
    waitForRpc = settle;
    const choose = async (placeholder, name, parent = page) => {
        await parent.getByPlaceholder(placeholder, { exact: true }).fill(name);
        await page.locator('.o-autocomplete--dropdown-item').filter({ hasText: name }).first().click();
    };
    const available = async () => employeeToken && !page.isClosed() &&
        !(await page.locator('.ab_pos_hr_overlay').isVisible()) && !new URL(page.url()).pathname.startsWith('/web/login');
    const assertSession = async () => {
        try {
            await rpc('ab_sales_pos_api', 'pos_submission_states', [], { tokens: [], pos_hr_session_token: employeeToken });
        } catch (error) {
            blocked = 'Employee session cannot be verified; no automatic login';
            throw error;
        }
    };
    try {
        report.setup_stage = 'odoo_login';
        await page.goto(callcenterLoginUrl(base.origin, configuration.database, metadata.action_id));
        await page.locator('[name=login]').fill(suite.credentials.login);
        await page.locator('[name=password]').fill(configuration.password);
        await page.locator('button[type=submit]').click();
        await page.waitForURL(url => !url.pathname.startsWith('/web/login'));
        const response = await context.request.post(`${base.origin}/web/session/get_session_info`, {
            data: { jsonrpc: '2.0', method: 'call', params: {}, id: 1 },
        });
        const session = (await response.json()).result;
        if (session?.uid !== suite.records.user_id || session?.db !== configuration.database) throw new Error('Wrong Odoo user or database');
        report.setup_stage = 'open_callcenter_pos';
        await openCallcenterAction(page, base.origin, metadata.action_id);
        await page.locator('.ab_pos_hr_overlay').waitFor({ timeout: 45000 });
        report.setup_stage = 'employee_selection';
        await choose('Select employee...', metadata.employee.name);
        report.setup_stage = 'employee_pin_login';
        await page.getByPlaceholder('Enter PIN', { exact: true }).fill(configuration.pin);
        await page.locator('.ab_pos_hr_overlay button.btn-primary').click();
        await page.locator('.ab_pos_hr_overlay').waitFor({ state: 'hidden', timeout: 30000 });
        await page.getByText(`Logged in as ${metadata.employee.name}.`, { exact: true }).waitFor({ timeout: 30000 });
        await settle();
        assertEmployeeSession(employeeSession, suite.records, { token: employeeToken });
        report.setup_stage = 'page_health';
        assertPageHealthy(report.errors);
        await assertSession();
        if (report.authentication.odoo_login_count !== 1 || report.authentication.employee_login_count !== 1) throw new Error('Expected exactly one Odoo and employee login');
    } catch (error) {
        report.setup_error = safe(error);
        if (report.errors.length && !report.setup_error.startsWith('Page/resource errors:')) {
            report.setup_error += '\nPage/resource errors: ' + safe(report.errors.map(item =>
                `${item.type}${item.path ? ' ' + item.path : ''}: ${item.message}`).join('; '));
        }
        blocked = report.setup_error;
    }
    for (const test of suite.cases) {
        const result = { id: test.id, status: 'RUNNING', last_action: report.setup_stage,
            checkpoints: [], errors: [], submission: 'NOT_EXECUTED' };
        active = result;
        let token;
        const shortages = {};
        const promotionChip = () => page.locator('.o_ab_sales_pos_promo_chip').filter({ hasText: metadata.promotion.name });
        const row = alias => page.locator(`.ab_pos_line_row[data-product-id="${suite.records.products[alias].id}"]`);
        try {
            if (blocked) { result.status = 'BLOCKED'; throw new Error(blocked); }
            if (!(await available())) throw new Error('Employee session expired or locked; no automatic login');
            await assertSession();
            for (const step of test.steps) {
                result.last_action = step.action;
                await settle();
                const expected = step.expected && typeof step.expected === 'object' ? step.expected : test.expected;
                const product = step.product ? suite.records.products[step.product] : null;
                switch (step.action) {
                    case 'new_empty_bill': {
                        if (token) throw new Error('Only one new bill is allowed per case');
                        const before = await readDraftWorkspace(page, suite.records);
                        const previous = new Set(before.bills.map(bill => bill.id));
                        await page.locator('.ab_pos_draft_slot_empty').first().click();
                        const dialog = page.getByRole('dialog').filter({ has: page.getByRole('tab', { name: 'New Bill', exact: true }) });
                        await dialog.waitFor();
                        await choose('Select store...', metadata.store.name, dialog);
                        try {
                            await dialog.getByRole('button', { name: 'Create', exact: true }).click();
                            await dialog.waitFor({ state: 'hidden' });
                            await settle();
                            assertEmployeeSession(employeeSession, suite.records, { requireStore: true, token: employeeToken });
                        } catch (error) {
                            const details = result.errors.filter(item => item.type === 'rpc' || item.type === 'identity')
                                .map(item => item.message).join('; ');
                            throw new Error('Branch selection failed: ' + safe(details || error));
                        }
                        assertPageHealthy(result.errors);
                        await expect.poll(async () => {
                            try {
                                const draft = claimDraft(await readDraftWorkspace(page, suite.records), previous, suite.records.store_id);
                                token = draft.id;
                                return true;
                            } catch { return false; }
                        }).toBe(true);
                        owned.add(token);
                        result.draft_id = token;
                        await expect(page.locator('.ab_pos_line_row')).toHaveCount(0);
                        await expect(page.locator('.ab_pos_store_code_value')).toHaveText(suite.records.store_code);
                        await expect(page.getByPlaceholder('Customer...', { exact: true })).toHaveValue('');
                        await expect(page.getByPlaceholder('Contract...', { exact: true })).toHaveValue('');
                        await page.locator('.ab_pos_product_filter_any_balance_input').uncheck();
                        await page.locator('.ab_pos_product_filter_store_balance_input').uncheck();
                        await page.locator('.ab_pos_product_item_type_filter').getByRole('button', { name: 'All', exact: true }).click();
                        result.checkpoints.push('new_owned_empty_draft');
                        break;
                    }
                    case 'select_customer': await choose('Customer...', metadata.customer.name); break;
                    case 'search_product':
                        await page.locator('.ab_pos_product_search_input').fill(product.code);
                        await page.locator('.ab_pos_product_search_input').press('Enter');
                        await page.locator('.ab_pos_product_cards').getByText(metadata.products[step.product].name, { exact: true }).waitFor();
                        break;
                    case 'add_product':
                        await page.locator('.ab_pos_product_cards').getByText(metadata.products[step.product].name, { exact: true }).click();
                        await row(step.product).waitFor();
                        break;
                    case 'set_quantity':
                        await row(step.product).locator('.ab_pos_line_qty_input').fill(String(step.quantity));
                        await row(step.product).locator('.ab_pos_line_qty_input').press('Tab');
                        money(amount(await row(step.product).locator('.ab_pos_line_sell_price_input').inputValue()), product.unit_price, 'unit price');
                        break;
                    case 'handle_shortage_if_present': {
                        const reason = row(step.product).locator('.ab_pos_line_unavailable_reason_select');
                        if (await reason.isVisible()) {
                            await reason.selectOption(suite.out_of_stock.value);
                            await row(step.product).locator('.ab_pos_line_unavailable_reason_other_input').fill(suite.out_of_stock.explanation);
                            shortages[product.id] = true;
                            result.checkpoints.push(`shortage_reason:${product.id}`);
                        }
                        break;
                    }
                    case 'select_contract': await choose('Contract...', metadata.contracts[step.contract].name); break;
                    case 'clear_contract':
                        await page.getByPlaceholder('Contract...', { exact: true }).fill('');
                        await page.getByPlaceholder('Contract...', { exact: true }).press('Tab');
                        break;
                    case 'clear_promotion_if_selected': {
                        const clear = page.locator('.o_ab_sales_pos_promo_panel').getByRole('button', { name: 'Clear', exact: true });
                        await page.locator('.o_ab_sales_pos_promo_chip').first().waitFor({ timeout: 5000 }).catch(() => {});
                        if (await clear.isVisible() && await clear.isEnabled()) await clear.click();
                        break;
                    }
                    case 'ensure_promotion_selected':
                        await expect(promotionChip()).toBeVisible();
                        if (!(await promotionChip().getAttribute('class')).includes('is-applied')) await promotionChip().click();
                        await expect(promotionChip()).toHaveClass(/is-applied/);
                        break;
                    case 'select_promotion_manually':
                        await expect(promotionChip()).toBeVisible();
                        await expect(promotionChip()).not.toHaveClass(/is-applied|is-selected/);
                        await promotionChip().click();
                        await expect(promotionChip()).toHaveClass(/is-applied/);
                        result.checkpoints.push('promotion_manual_click');
                        break;
                    case 'assert_promotion_unselected':
                        await expect(promotionChip()).toBeVisible();
                        await expect(page.locator('.o_ab_sales_pos_promo_chip.is-applied, .o_ab_sales_pos_promo_chip.is-selected')).toHaveCount(0);
                        result.checkpoints.push('promotion_unselected');
                        break;
                    case 'assert_promotion_applied':
                        await expect(promotionChip()).toHaveClass(/is-applied/);
                        result.checkpoints.push('promotion_applied');
                        break;
                    case 'assert_promotion_cleared':
                    case 'assert_promotion_unavailable': await expect(page.locator('.o_ab_sales_pos_promo_chip')).toHaveCount(0); break;
                    case 'assert_ui_totals':
                        await expect.poll(async () => amount(await page.locator('.ab_pos_meta_value_total').innerText())).toBeCloseTo(expected.gross_total, 2);
                        await expect.poll(async () => amount(await page.locator('.ab_pos_meta_value_net').innerText())).toBeCloseTo(expected.customer_pay, 2);
                        await expect(page.locator('.ab_pos_line_row')).toHaveCount(expected.line_count);
                        result.checkpoints.push('ui_totals');
                        break;
                    case 'assert_backend_quote': {
                        const lines = test.lines.map(line => ({ product_id: suite.records.products[line.product].id,
                            qty_str: String(line.qty), uom_id: suite.records.products[line.product].uom_id,
                            sell_price: suite.records.products[line.product].unit_price }));
                        const values = { store_id: suite.records.store_id, customer_id: suite.records.customer_id,
                            lines, applied_program_id: expectedPromotions(test)[0] || false,
                            manual_clear: expected.contract ? true : !expected.promotion };
                        let quote;
                        if (expected.contract) {
                            quote = await rpc('ab_sales_pos_api', 'pos_contract_totals', [], {
                                ...values, contract_id: suite.records.contracts[expected.contract].id,
                            });
                        } else {
                            quote = await rpc('ab_sales_pos_api', 'pos_promotions', [], values);
                        }
                        assertBackendQuote(quote, expected, suite.records.promotion_id, suite.defaults.money_tolerance);
                        result.backend_quote = quote;
                        result.checkpoints.push('independent_backend_quote');
                        break;
                    }
                    case 'prepare_submission': {
                        await page.locator('.ab_pos_btn_submit_bill').click();
                        const dialog = page.locator('.o_ab_sales_pos_submit_dialog');
                        await dialog.waitFor();
                        if (expected.contract) {
                            const insurance = dialog.locator('.o_ab_sales_pos_submit_section').filter({ has: page.locator('.o_ab_sales_pos_section_title', { hasText: 'Insurance' }) });
                            await insurance.locator('input').nth(0).fill(suite.submission.insurance_name);
                            await insurance.locator('input').nth(1).fill(`QA-${test.id}`);
                        }
                        const employee = dialog.getByPlaceholder('Select employee...', { exact: true });
                        if (await employee.isVisible() && !(await employee.inputValue())) await choose('Select employee...', metadata.employee.name, dialog);
                        await dialog.locator('#ab_sales_pos_is_delivery').uncheck();
                        await dialog.locator('textarea').last().fill(`CALLCENTER-QA-${test.id}-${Date.now()}`);
                        result.checkpoints.push('pre_submit_dialog');
                        break;
                    }
                    case 'submit': {
                        if (!configuration.allowSubmit) throw new Error('Explicit --allow-submit is required');
                        protectedTokens.add(token);
                        submitAllowed = true;
                        try {
                            await submitOnce({
                                click: () => page.locator('.o_ab_sales_pos_submit_dialog').getByRole('button', { name: 'Submit (F10)', exact: true }).click({ timeout: 15000 }),
                                readStates: () => rpc('ab_sales_pos_api', 'pos_submission_states', [], {
                                    tokens: [token], pos_hr_session_token: employeeToken,
                                }), token, result,
                            });
                            report.submitted_invoices.push({ case_id: test.id, id: result.invoice_id,
                                branch_header_id: result.branch_header_id, eplus_serial: result.eplus_serial });
                            await page.locator('.o_ab_sales_pos_submit_dialog').waitFor({ state: 'hidden' });
                        } finally { submitAllowed = false; }
                        break;
                    }
                    case 'submit_or_preview':
                        await page.screenshot({ path: join(configuration.output, `${test.id}.png`) });
                        await page.locator('.o_ab_sales_pos_submit_dialog').getByRole('button', { name: 'Back', exact: true }).click();
                        await page.locator('.o_ab_sales_pos_submit_dialog').waitFor({ state: 'hidden' });
                        break;
                    case 'assert_saved_invoice_if_submitted':
                        await assertSavedInvoice({ rpc, suite, test, result, shortages });
                        break;
                    default: throw new Error('Unregistered action reached browser runner');
                }
            }
            await settle();
            if (result.errors.length) throw new Error('Browser or backend errors recorded: ' + result.errors.map(item => `${item.method || item.type}: ${item.message}`).join('; '));
            result.status = result.submission === 'SAVED' ? 'PASS_SUBMITTED' : 'PASS_PREVIEW';
        } catch (error) {
            if (result.status !== 'BLOCKED') result.status = 'FAIL';
            result.error = safe(error);
            if (await available()) await page.screenshot({ path: join(configuration.output, `${test.id}-failure.png`) }).catch(() => {});
            else blocked ||= 'Employee session expired or locked; remaining cases blocked';
        } finally {
            await Promise.all([...tasks]);
            if (protectedTokens.has(token)) {
                result.draft_preserved = true;
                owned.delete(token);
                if (result.submission !== 'SAVED') blocked = 'Submission not confirmed saved; original bill retained';
            } else if (token && !blocked && await available()) {
                try {
                    const dialog = page.locator('.o_ab_sales_pos_submit_dialog');
                    if (await dialog.isVisible()) await dialog.getByRole('button', { name: 'Back', exact: true }).click();
                    const workspace = await readDraftWorkspace(page, suite.records);
                    if (!mayRemoveDraft(workspace, token, owned, protectedTokens)) throw new Error('Refusing to remove a draft not owned and selected by this case');
                    await page.locator('.ab_pos_btn_remove_bill').click();
                    const confirmation = page.getByRole('dialog').getByRole('button', { name: 'Confirm', exact: true });
                    let confirmVisible = false;
                    try {
                        await confirmation.waitFor({ state: 'visible', timeout: 1000 });
                        confirmVisible = true;
                    } catch (error) {
                        if (error.name !== 'TimeoutError') throw error;
                    }
                    if (confirmVisible) await confirmation.click();
                    await expect.poll(async () => !(await readDraftWorkspace(page, suite.records)).bills.some(bill => bill.id === token)).toBe(true);
                    await expect(page.locator('.ab_pos_draft_slot_empty').first()).toBeEnabled();
                    owned.delete(token);
                    result.cleaned_draft_count = 1;
                } catch (error) {
                    result.cleanup_error = safe(error);
                    blocked = 'Draft cleanup failed; remaining cases blocked';
                    result.status = 'FAIL_CLEANUP';
                }
            }
            await Promise.all([...tasks]);
            if (result.errors.length && result.status.startsWith('PASS')) result.status = 'FAIL';
            report.cases.push(result);
            save();
            console.log(`${test.id}: ${result.status}${result.error ? ' (' + result.last_action + ': ' + result.error.split('\n')[0] + ')' : ''}`);
            active = report;
        }
    }
} catch (error) {
    report.suite_error = safe(error);
} finally {
    if (page && !page.isClosed()) {
        try { await waitForRpc(); } catch (error) { report.cleanup_error = safe(error); }
    }
    if (employeeToken && context) {
        try {
            const response = await context.request.post(`${base.origin}/web/dataset/call_kw/ab_employee_access_sales_pos_api/logout_session`, {
                timeout: 10000, data: { jsonrpc: '2.0', method: 'call', id: 1, params: {
                    model: 'ab_employee_access_sales_pos_api', method: 'logout_session', args: [],
                    kwargs: { session_token: employeeToken, close_shift: false },
                } },
            });
            const body = await response.json();
            if (body.error) throw new Error(body.error.data?.message || body.error.message);
            report.employee_session_closed = true;
        } catch (error) { report.cleanup_error = safe(error); }
    }
    detachResponse();
    await Promise.all([...tasks]);
    await context?.close();
    await browser?.close();
    report.protected_draft_ids = [...protectedTokens];
    report.remaining_owned_draft_ids = [...owned];
    save();
}
process.exitCode = report.suite_error || report.setup_error || report.cleanup_error || report.errors.length ||
    owned.size || report.cases.some(test => !['PASS_PREVIEW', 'PASS_SUBMITTED'].includes(test.status)) ? 1 : 0;
