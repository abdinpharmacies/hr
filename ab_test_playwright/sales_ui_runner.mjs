// Runs UI, backend quote, and explicitly requested submission checks.
import { submitOnce, assertSavedInvoice } from './submission.mjs';
import { localOdooUrl } from './connection.mjs';
import { readDraftWorkspace } from './draft_workspace.mjs';
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
const require = createRequire('/opt/playwright/package.json');
const { chromium, expect } = require('@playwright/test');
const cfg = JSON.parse(readFileSync(0, 'utf8'));
const base = localOdooUrl(cfg.url);
const suite = cfg.suite;
const report = { suite_id: suite.suite_id, mode: suite.cases.some(c => c.steps.some(s => s.action === 'submit')) ? 'submit' : 'preview', database: cfg.database,
    submitted_invoices: [], cases: [], errors: [], authentication: { odoo_login_count: 0, employee_login_count: 0 } };
const browser = await chromium.launch({ headless: !cfg.headed, slowMo: cfg.headed ? 150 : 0 });
const amount = text => Number(text.replace(/,/g, '').trim());
function equalMoney(actual, expected, field) {
    if (!Number.isFinite(actual) || Math.abs(actual - expected) > suite.defaults.money_tolerance)
        throw new Error(`${field}: expected ${expected}, got ${actual}`);
}
function safeError(error) {
    let message = String(error?.message || error);
    for (const secret of [cfg.password, cfg.pin]) if (secret) message = message.split(secret).join('[REDACTED]');
    return message.slice(0, 3000);
}
let context;
let hrToken = null;
let blockedReason = null;
let activeResult = report;
try {
    context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    let hrSession = null;
    let authenticated = false;
    const ownedDraftIds = new Set();
    const tasks = new Set();
    const requestOwners = new WeakMap();
    const pendingPricing = new Set();
    let lastPricingActivity = Date.now();
    const isPricingRequest = request => request.url().includes('/web/dataset/call_kw/') &&
        !request.url().endsWith('/pos_save_draft_cache');
    const finishPricing = request => {
        if (pendingPricing.delete(request)) lastPricingActivity = Date.now();
    };
    page.on('requestfinished', finishPricing);
    page.on('requestfailed', finishPricing);
    const waitForPricing = async () => {
        // Cover the 300/350 ms pricing debounces, then wait for RPCs and rendering.
        const started = Date.now();
        await expect.poll(() => pendingPricing.size === 0 &&
            Date.now() - Math.max(started, lastPricingActivity) >= 700,
            { timeout: 15000, message: 'Pricing RPCs must settle before assertions' }).toBe(true);
    };
    let selectedDraftId = null;
    const draftTokens = new Map();
    const protectedDraftIds = new Set();
    page.on('request', request => {
        requestOwners.set(request, activeResult);
        if (isPricingRequest(request)) {
            pendingPricing.add(request);
            lastPricingActivity = Date.now();
        }
        if (new URL(request.url()).pathname === '/web/login' && request.method() === 'POST')
            report.authentication.odoo_login_count++;
        if (request.url().endsWith('/employee_login')) report.authentication.employee_login_count++;
    });
    const rpc = async (model, method, args = [], kwargs = {}) => {
        const response = await context.request.post(`${base.origin}/web/dataset/call_kw/${model}/${method}`, {
            timeout: 10000,
            data: { jsonrpc: '2.0', method: 'call', params: { model, method, args, kwargs: { context: { lang: 'en_US' }, ...kwargs } }, id: 1 },
        });
        const body = await response.json();
        if (body.error) throw new Error(body.error.data?.message || body.error.message);
        return body.result;
    };
    const m2o = async (placeholder, name, parent = page) => {
        const input = parent.getByPlaceholder(placeholder, { exact: true });
        await input.fill(name);
        await page.locator('.o-autocomplete--dropdown-item').filter({ hasText: name }).first().click();
    };
    page.on('pageerror', e => activeResult.errors.push({ type: 'pageerror', message: safeError(e) }));
    page.on('console', message => {
        if (message.type() === 'error') activeResult.errors.push({ type: 'console', message: safeError(message.text()) });
    });
    page.on('requestfailed', request => {
        const reason = request.failure()?.errorText || 'Request failed';
        if (!reason.includes('ERR_ABORTED')) (requestOwners.get(request) || report).errors.push({ type: 'network', message: safeError(reason), path: new URL(request.url()).pathname });
    });
    page.on('response', response => {
        if (!response.url().includes('/web/dataset/call_kw/')) return;
        const owner = requestOwners.get(response.request()) || report;
        const work = (async () => {
            try {
                const body = await response.json();
                if (body.error) owner.errors.push({ type: 'rpc', method: response.url().split('/').pop(), message: safeError(body.error.data?.message || body.error.message) });
                if (response.url().endsWith('/employee_login')) {
                    hrToken = body.result?.token || hrToken;
                    hrSession = body.result;
                }
            } catch { /* Ignore responses aborted during browser teardown. */ }
        })();
        tasks.add(work); work.finally(() => tasks.delete(work));
    });
    try {
        report.setup_stage = 'login_odoo';
        await page.goto(`${base.origin}/web/login?db=${encodeURIComponent(cfg.database)}`);
        await page.locator('[name=login]').fill(suite.credentials.login);
        await page.locator('[name=password]').fill(cfg.password);
        await page.locator('button[type=submit]').click();
        await page.waitForURL(u => !u.pathname.startsWith('/web/login'));
        const sessionResponse = await context.request.post(`${base.origin}/web/session/get_session_info`, { data: { jsonrpc: '2.0', method: 'call', params: {}, id: 1 } });
        const session = (await sessionResponse.json()).result;
        if (session?.uid !== suite.records.user_id || session?.db !== cfg.database) throw new Error('Wrong authenticated user/database');
        report.setup_stage = 'open_pos';
        await page.goto(`${base.origin}/odoo/action-${cfg.metadata.action_id}`);
        await page.locator('.ab_pos_hr_overlay').waitFor({ timeout: 45000 });
        report.setup_stage = 'select_employee';
        await m2o('Select employee...', cfg.metadata.employee.name);
        report.setup_stage = 'employee_pin_login';
        await page.getByPlaceholder('Enter PIN', { exact: true }).fill(cfg.pin);
        await page.locator('.ab_pos_hr_overlay button.btn-primary').click();
        await page.locator('.ab_pos_hr_overlay').waitFor({ state: 'hidden', timeout: 30000 });
        authenticated = true;
        // The overlay closes before asynchronous draft-cache/session setup finishes.
        await page.getByText(`Logged in as ${cfg.metadata.employee.name}.`, { exact: true }).waitFor({ timeout: 30000 });
        await Promise.all([...tasks]);
        if (hrSession?.store?.id !== suite.records.store_id || hrSession?.employee?.id !== suite.records.employee_id)
            throw new Error('POS session uses a different branch or employee');
        if (report.errors.length) throw new Error('Browser/backend errors during suite authentication');
    } catch (error) {
        blockedReason = safeError(error);
        report.setup_error = blockedReason;
    }
    for (const test of suite.cases) {
        const result = { id: test.id, status: 'RUNNING', last_action: report.setup_error ? report.setup_stage : 'new_empty_bill', checkpoints: [], errors: [], submission: 'NOT_EXECUTED' };
        activeResult = result;
        let caseDraftId = null;
        const shortages = {};
        const sessionAvailable = async () => authenticated && !page.isClosed() &&
            !new URL(page.url()).pathname.startsWith('/web/login') &&
            !(await page.locator('.ab_pos_hr_overlay').isVisible());
        try {
            if (blockedReason) {
                result.status = 'BLOCKED';
                throw new Error(blockedReason);
            }
            if (!(await sessionAvailable())) throw new Error('Session expired or locked; no automatic reauthentication');
            for (const step of test.steps) {
                result.last_action = step.action;
                const expected = typeof step.expected === 'object' ? step.expected : test.expected;
                if (step.action.startsWith('assert_') || ['select_promotion_manually', 'ensure_promotion_selected', 'clear_contract'].includes(step.action))
                    await waitForPricing();
                switch (step.action) {
                    case 'new_empty_bill': {
                        if (caseDraftId) throw new Error('Only one new bill is allowed per case');
                        await Promise.all([...tasks]);
                        const before = await readDraftWorkspace(page, suite.records);
                        const previousIds = new Set(before.bills.map(bill => bill.id));
                        const slot = page.locator('.ab_pos_draft_slot_empty').first();
                        await expect(slot).toBeEnabled({ timeout: 15000 });
                        await slot.click();
                        const manager = page.locator('.ab_pos_draft_manager');
                        await manager.waitFor();
                        await m2o('Select store...', cfg.metadata.store.name, manager);
                        await manager.getByRole('button', { name: 'Create', exact: true }).click();
                        await manager.waitFor({ state: 'hidden' });
                        // Ready bills are tab-local and intentionally do not trigger a server save.
                        await expect.poll(async () => {
                            const workspace = await readDraftWorkspace(page, suite.records);
                            const bill = workspace.bills.find(item => item.id === workspace.selectedId);
                            if (!bill || previousIds.has(bill.id) || protectedDraftIds.has(bill.id) ||
                                bill.header?.store_id !== suite.records.store_id ||
                                bill.header?.pos_client_token !== bill.id) return false;
                            selectedDraftId = bill.id;
                            ownedDraftIds.add(bill.id);
                            draftTokens.set(bill.id, bill.header.pos_client_token);
                            return true;
                        }, { timeout: 15000, message: 'Create must select a new test-owned local bill' }).toBe(true);
                        caseDraftId = selectedDraftId;
                        result.draft_id = caseDraftId;
                        await expect(page.locator('.ab_pos_line_row')).toHaveCount(0);
                        await expect(page.locator('.ab_pos_store_code_value')).toHaveText(suite.records.store_code);
                        await expect(page.getByPlaceholder('Customer...', { exact: true })).toHaveValue('');
                        await expect(page.getByPlaceholder('Contract...', { exact: true })).toHaveValue('');
                        await page.locator('.ab_pos_product_filter_any_balance_input').uncheck();
                        await page.locator('.ab_pos_product_filter_store_balance_input').uncheck();
                        result.checkpoints.push('shared_session_empty_bill');
                        break;
                    }
                    case 'select_customer': await m2o('Customer...', cfg.metadata.customer.name); break;
                    case 'search_product':
                        await page.locator('.ab_pos_product_search_input').fill(step.query);
                        await page.locator('.ab_pos_product_search_input').press('Enter');
                        await page.locator('.ab_pos_product_cards').getByText(suite.records.products.find(p => p.id === step.id).name, { exact: true }).waitFor();
                        break;
                    case 'add_product':
                        await page.locator('.ab_pos_product_cards').getByText(suite.records.products.find(p => p.id === step.id).name, { exact: true }).click();
                        await page.locator(`.ab_pos_line_row[data-product-id="${step.id}"]`).waitFor();
                        break;
                    case 'set_quantity': {
                        const row = page.locator(`.ab_pos_line_row[data-product-id="${step.product_id}"]`);
                        await row.locator('.ab_pos_line_qty_input').fill(String(step.quantity));
                        await row.locator('.ab_pos_line_qty_input').press('Tab');
                        const product = suite.records.products.find(p => p.id === step.product_id);
                        equalMoney(amount(await row.locator('.ab_pos_line_sell_price_input').inputValue()), product.unit_price, 'unit price');
                        break;
                    }
                    case 'handle_shortage_if_present': {
                        const row = page.locator(`.ab_pos_line_row[data-product-id="${step.product_id}"]`);
                        const selector = row.locator('.ab_pos_line_unavailable_reason_select');
                        if (await selector.isVisible()) {
                            await selector.selectOption(suite.out_of_stock.value);
                            await row.locator('.ab_pos_line_unavailable_reason_other_input').fill(suite.out_of_stock.explanation);
                            shortages[step.product_id] = true;
                            result.checkpoints.push(`shortage_reason:${step.product_id}`);
                        }
                        break;
                    }
                    case 'select_contract': await m2o('Contract...', cfg.metadata.contracts.find(c => c.id === step.id).name); await waitForPricing(); break;
                    case 'clear_contract': {
                        const input = page.getByPlaceholder('Contract...', { exact: true });
                        await input.fill(''); await input.press('Tab'); break;
                    }
                    case 'clear_promotion_if_selected': {
                        const clear = page.locator('.o_ab_sales_pos_promo_panel').getByRole('button', { name: 'Clear', exact: true });
                        await page.locator('.o_ab_sales_pos_promo_chip').first().waitFor({ timeout: 5000 }).catch(() => {});
                        if (await clear.isVisible() && await clear.isEnabled()) await clear.click();
                        break;
                    }
                    case 'ensure_promotion_selected': {
                        const chip = page.locator('.o_ab_sales_pos_promo_chip').filter({ hasText: cfg.metadata.promotion.name });
                        await chip.waitFor();
                        if (!(await chip.getAttribute('class')).includes('is-applied')) await chip.click();
                        await expect(chip).toHaveClass(/is-applied/);
                        break;
                    }
                    case 'assert_promotion_unselected': {
                        const chip = page.locator('.o_ab_sales_pos_promo_chip').filter({ hasText: cfg.metadata.promotion.name });
                        await expect(chip).toBeVisible();
                        await expect(page.locator('.o_ab_sales_pos_promo_chip.is-applied, .o_ab_sales_pos_promo_chip.is-selected')).toHaveCount(0);
                        result.checkpoints.push('promotion_unselected');
                        break;
                    }
                    case 'select_promotion_manually': {
                        const chip = page.locator('.o_ab_sales_pos_promo_chip').filter({ hasText: cfg.metadata.promotion.name });
                        await expect(chip).toBeVisible();
                        await expect(chip).not.toHaveClass(/is-applied|is-selected/);
                        await chip.click();
                        await waitForPricing();
                        await expect(chip).toHaveClass(/is-applied/);
                        result.checkpoints.push('promotion_manual_click');
                        break;
                    }
                    case 'assert_promotion_applied':
                        await expect(page.locator('.o_ab_sales_pos_promo_chip').filter({ hasText: cfg.metadata.promotion.name })).toHaveClass(/is-applied/);
                        result.checkpoints.push('promotion_applied');
                        break;
                    case 'assert_promotion_cleared':
                    case 'assert_promotion_unavailable': await expect(page.locator('.o_ab_sales_pos_promo_chip')).toHaveCount(0); break;
                    case 'assert_ui_totals':
                        await expect.poll(async () => amount(await page.locator('.ab_pos_meta_value_total').innerText())).toBeCloseTo(expected.gross_total, 2);
                        await expect.poll(async () => amount(await page.locator('.ab_pos_meta_value_net').innerText())).toBeCloseTo(expected.customer_pay, 2);
                        await expect(page.locator('.ab_pos_line_row')).toHaveCount(expected.line_count);
                        result.checkpoints.push('ui_totals'); break;
                    case 'assert_backend_quote': {
                        const lines = test.lines.map(l => ({ product_id: l.product_id, qty_str: String(l.qty), uom_id: 1,
                            sell_price: suite.records.products.find(p => p.id === l.product_id).unit_price }));
                        let quote;
                        if (test.expected.contract_id) {
                            quote = await rpc('ab_sales_pos_api', 'pos_contract_totals', [], {
                                contract_id: expected.contract_id, lines, store_id: suite.records.store_id,
                                customer_id: suite.records.customer_id,
                                applied_program_id: expected.applied_promotion_ids[0] || false, manual_clear: true,
                            });
                            for (const [key, field] of [['discount', 'contract_discount'], ['total_after_discount', 'contract_total_after_discount'], ['cust_pay', 'customer_pay'], ['company_pay', 'company_pay']])
                                equalMoney(Number(quote[key]), expected[field], key);
                            if ((quote.applied_program_id || false) !== (expected.applied_promotion_ids[0] || false))
                                throw new Error('Wrong promotion applied by contract pricing');
                            if (quote.allow_promotions) {
                                if ((quote.selected_program_id || false) !== (expected.applied_promotion_ids[0] || false))
                                    throw new Error('Wrong promotion selected by contract pricing');
                                equalMoney(Number(quote.promo_discount_amount || 0), expected.promotion_discount || 0, 'promotion discount');
                            }
                        } else {
                            quote = await rpc('ab_sales_pos_api', 'pos_promotions', [], { store_id: suite.records.store_id, customer_id: suite.records.customer_id, lines,
                                applied_program_id: test.expected.applied_promotion_ids[0] || false, manual_clear: !test.expected.applied_promotion_ids.length });
                            equalMoney(Number(quote.total_net_amount ?? quote.amount_total_after_promo), expected.customer_pay, 'backend net');
                            if ((quote.applied_program_id || false) !== (test.expected.applied_promotion_ids[0] || false))
                                throw new Error('Wrong promotion applied by backend');
                            equalMoney(Number(quote.promo_discount_amount), test.expected.promotion_discount || 0, 'promotion discount');
                        }
                        result.backend_quote = quote;
                        result.checkpoints.push('backend_quote'); break;
                    }
                    case 'prepare_submission': {
                        await page.locator('.ab_pos_btn_submit_bill').click();
                        const dialog = page.locator('.o_ab_sales_pos_submit_dialog');
                        await dialog.waitFor();
                        if (test.expected.contract_id) {
                            const insurance = dialog.locator('.o_ab_sales_pos_submit_section').filter({ has: page.locator('.o_ab_sales_pos_section_title', { hasText: 'Insurance' }) });
                            await insurance.locator('input').nth(0).fill(suite.submission.insurance_name);
                            await insurance.locator('input').nth(1).fill(`TEST-${test.id}`);
                        }
                        const employee = dialog.getByPlaceholder('Select employee...', { exact: true });
                        if (await employee.isVisible() && !(await employee.inputValue())) await m2o('Select employee...', cfg.metadata.employee.name, dialog);
                        await dialog.locator('#ab_sales_pos_is_delivery').uncheck();
                        await dialog.locator('textarea').last().fill(`PLAYWRIGHT-TEST-${test.id}-${Date.now()}`);
                        result.checkpoints.push('pre_submit_dialog'); break;
                    }
                    case 'submit':
                        protectedDraftIds.add(caseDraftId);
                        await submitOnce({ page, rpc, token: draftTokens.get(caseDraftId), result });
                        report.submitted_invoices.push({ case_id: test.id, id: result.invoice_id, eplus_serial: result.eplus_serial });
                        await page.locator('.o_ab_sales_pos_submit_dialog').waitFor({ state: 'hidden' });
                        break;
                    case 'submit_or_preview':
                        await page.screenshot({ path: join(cfg.output, `${test.id}.png`) });
                        await page.locator('.o_ab_sales_pos_submit_dialog').getByRole('button', { name: 'Back', exact: true }).click();
                        await page.locator('.o_ab_sales_pos_submit_dialog').waitFor({ state: 'hidden' });
                        break;
                    case 'assert_saved_invoice_if_submitted':
                        await assertSavedInvoice({ rpc, suite, test, result, shortages });
                        break;
                    default: throw new Error(`Unsupported JSON action: ${step.action}`);
                }
            }
            await Promise.all([...tasks]);
            if (result.errors.length) throw new Error('Browser/backend errors were recorded');
            result.status = result.submission === 'SAVED' ? 'PASS_SUBMITTED' : 'PASS_PREVIEW';
        } catch (error) {
            if (result.status !== 'BLOCKED') result.status = 'FAIL';
            result.error = safeError(error);
            if (await sessionAvailable()) await page.screenshot({ path: join(cfg.output, `${test.id}-failure.png`) }).catch(() => {});
            else blockedReason ||= 'Session expired or locked; no automatic reauthentication';
        } finally {
            await Promise.all([...tasks]);
            if (protectedDraftIds.has(caseDraftId)) {
                result.draft_preserved = true;
                ownedDraftIds.delete(caseDraftId);
                selectedDraftId = null;
                if (result.submission !== 'SAVED') blockedReason = 'Submission unresolved or rejected; invoice retained for review';
            }
            if (caseDraftId && !protectedDraftIds.has(caseDraftId) && await sessionAvailable()) {
                try {
                    const dialog = page.locator('.o_ab_sales_pos_submit_dialog');
                    if (await dialog.isVisible()) {
                        await dialog.getByRole('button', { name: 'Back', exact: true }).click();
                        await dialog.waitFor({ state: 'hidden' });
                    }
                    selectedDraftId = (await readDraftWorkspace(page, suite.records)).selectedId;
                    if (!ownedDraftIds.has(caseDraftId) || selectedDraftId !== caseDraftId)
                        throw new Error('Current bill is not the case-owned draft; refusing cleanup');
                    // Click once: after removal another user's bill may become selected.
                    // The UI handles local-only removal or revision-checked server deletion.
                    await page.locator('.ab_pos_btn_remove_bill').click();
                    const confirm = page.getByRole('dialog').getByRole('button', { name: 'Confirm', exact: true });
                    await confirm.waitFor({ timeout: 1000 }).then(() => confirm.click()).catch(() => {});
                    await expect.poll(async () => {
                        const workspace = await readDraftWorkspace(page, suite.records);
                        return !workspace.bills.some(bill => bill.id === caseDraftId);
                    }, { timeout: 15000, message: 'Run-owned draft must leave the tab workspace' }).toBe(true);
                    await expect(page.locator('.ab_pos_draft_slot_empty').first()).toBeEnabled();
                    ownedDraftIds.delete(caseDraftId);
                    if (selectedDraftId === caseDraftId) selectedDraftId = null;
                    result.cleaned_draft_count = 1;
                } catch (error) {
                    result.cleanup_warning = safeError(error);
                    blockedReason = 'Draft cleanup failed; stopping to preserve existing bills';
                }
            }
            await Promise.all([...tasks]);
            if (result.errors.length && ['PASS_PREVIEW', 'PASS_SUBMITTED'].includes(result.status)) result.status = 'FAIL';
            if (result.cleanup_warning && ['PASS_PREVIEW', 'PASS_SUBMITTED'].includes(result.status)) result.status = 'FAIL_CLEANUP';
            report.cases.push(result);
            writeFileSync(join(cfg.output, 'results.json'), JSON.stringify(report, null, 2), { mode: 0o600 });
            console.log(`${test.id}: ${result.status}${result.error ? ` (${result.last_action}: ${result.error.split('\n')[0]})` : ''}`);
            activeResult = report;
        }
    }
    await Promise.all([...tasks]);
    report.remaining_owned_draft_ids = [...ownedDraftIds].filter(id => !protectedDraftIds.has(id));
    report.protected_draft_ids = [...protectedDraftIds];
} catch (error) {
    report.suite_error = safeError(error);
} finally {
    if (hrToken && context) {
        try {
            const response = await context.request.post(`${base.origin}/web/dataset/call_kw/ab_employee_access_sales_pos_api/logout_session`, {
                data: { jsonrpc: '2.0', method: 'call', params: { model: 'ab_employee_access_sales_pos_api', method: 'logout_session',
                    args: [], kwargs: { session_token: hrToken, close_shift: true } }, id: 1 },
            });
            const body = await response.json();
            if (body.error) throw new Error(body.error.data?.message || body.error.message);
            report.employee_session_closed = true;
        } catch (error) { report.cleanup_warning = safeError(error); }
    }
    await context?.close();
    await browser.close();
    writeFileSync(join(cfg.output, 'results.json'), JSON.stringify(report, null, 2), { mode: 0o600 });
}
process.exitCode = report.suite_error || report.setup_error || report.cleanup_warning || report.errors.length ||
    report.remaining_owned_draft_ids?.length || report.cases.some(c => !['PASS_PREVIEW', 'PASS_SUBMITTED'].includes(c.status)) ? 1 : 0;
