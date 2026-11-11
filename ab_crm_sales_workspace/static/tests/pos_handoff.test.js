import {expect, test} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {contains, makeMockEnv, mountWithCleanup, patchWithCleanup} from "@web/../tests/web_test_helpers";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {registry} from "@web/core/registry";
import {ChatterContacts} from "@ab_crm_sales_workspace/contacts";
import {CrmPosAction} from "@ab_crm_sales_workspace/pos_handoff";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

defineMailModels();

test("contact modes have distinct selected styling and POS matches require selection", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const calls = [];
    const saved = [];
    env.services.dialog.add(ChatterContacts, {mode: "add", token: "crm", initial: {phone: "01012345678"},
        onSaved: contact => saved.push(contact), call: async (model, method, args, values) => {
            calls.push([method, values]);
            if (method === "contact_search") return {contacts: [], branches: [{id: 1, name: "Branch"}]};
            if (method === "contact_pos_search") return {customers: [{id: 8, name: "POS Match", mobile_phone: "01012345678"}], stores: []};
            if (method === "contact_pos_select") return {id: 4, is_ab_customer: true, catalog_customer_id: values.customer_id};
        }});
    await animationFrame(); await animationFrame();
    expect('button:contains(Use existing)').toHaveClass('btn-primary');
    expect('button:contains(Use existing)').toHaveAttribute('aria-pressed', 'true');
    expect('button:contains(Create new)').toHaveClass('btn-outline-success');
    expect('input[aria-label="Search by name or phone"]').toHaveValue('01012345678');
    expect('section[aria-label="POS customers"]').toHaveCount(1);
    expect(saved).toHaveLength(0);
    await contains('button:contains(Create new)').click();
    expect('button:contains(Create new)').toHaveClass('btn-success');
    expect('button:contains(Create new)').toHaveAttribute('aria-pressed', 'true');
    expect('#ab_contact_name').toHaveCount(1);
    await contains('button:contains(Use existing)').click();
    await animationFrame();
    await contains('button:contains(POS Match)').click();
    expect(calls.at(-1)[0]).toBe('contact_pos_select');
    expect(calls.at(-1)[1].customer_id).toBe(8);
    expect(saved[0].catalog_customer_id).toBe(8);
});

test("CRM action subclasses the registered POS and leaves ordinary POS registered", () => {
    const native = registry.category('actions').get('ab_sales.pos');
    expect(Object.getPrototypeOf(CrmPosAction.prototype)).toBe(native.prototype);
    expect(CrmPosAction.template).toBe(native.template);
    expect(registry.category('actions').get('ab_crm_sales_workspace.pos')).toBe(CrmPosAction);
});

test("unregistered prefill runs once and preserves edited native draft fields", async () => {
    const bill = {header: {}, id: 'new-draft'};
    const calls = [];
    const adapter = {_draftRequestScope: () => 'scope', currentBill: bill, persistCache: () => calls.push('persist'), syncContact: async () => calls.push('sync')};
    const data = {name: 'CRM Only', phone: '01012345678', address: 'Address', catalog_customer_id: false};
    await CrmPosAction.prototype.prefillHandoff.call(adapter, bill, data);
    expect(bill.header.customer_id).toBe(undefined);
    expect(bill.header.new_customer_phone).toBe('01012345678');
    expect(bill.header.invoice_address).toBe('Address');
    bill.header.new_customer_address = 'Edited by employee';
    await CrmPosAction.prototype.prefillHandoff.call(adapter, bill, {...data, address: 'Replacement'});
    expect(bill.header.new_customer_address).toBe('Edited by employee');
    expect(calls).toEqual(['persist', 'sync']);
});

test("registered prefill uses normal POS selection then keeps CRM invoice details", async () => {
    const bill = {header: {}, id: 'new-draft'};
    const selected = [];
    const adapter = {_draftRequestScope: () => "scope", currentBill: bill, persistCache() {}, syncContact: async () => {}, onCustomerM2OUpdate: async customer => {
        selected.push(customer.id); Object.assign(bill.header, {customer_id: customer.id, customer_name: 'Core name', invoice_address: 'Master address'});
    }};
    await CrmPosAction.prototype.prefillHandoff.call(adapter, bill, {catalog_customer_id: 91, name: 'CRM name', phone: '01012345678', address: 'Delivery address'});
    expect(selected).toEqual([91]);
    expect(bill.header.customer_name).toBe('Core name');
    expect(bill.header.invoice_address).toBe('Delivery address');
});

test("failed CRM synchronization retries without customer creation or invoice submission", async () => {
    const bill = {id: 'native-token', crm_handoff_id: 9, crm_prefilled: true, header: {customer_id: 17}};
    const calls = [];
    let retry;
    let failure = true;
    const adapter = {crmSyncing: new Set(), crmAcknowledged: new Map(),
        _saveCacheToServer: async () => calls.push('save'),
        crmCall: async (method, values) => { calls.push([method, values]); if (failure) throw new Error('Offline'); return {catalog_customer_id: 17}; },
        crmError: (error, callback) => { retry = callback; }};
    adapter.syncContact = draft => CrmPosAction.prototype.syncContact.call(adapter, draft);
    await adapter.syncContact(bill);
    expect(adapter.crmAcknowledged.has(bill.id)).toBe(false);
    failure = false;
    await retry();
    expect(adapter.crmAcknowledged.get(bill.id)).toBe(17);
    expect(calls.filter(call => Array.isArray(call)).map(call => call[0])).toEqual(['pos_handoff_sync', 'pos_handoff_sync']);
    expect(calls.at(-1)[1]).toEqual({handoff_id: 9, draft_token: 'native-token'});
});

test("reload selects the bound draft without reapplying contact prefill", async () => {
    const bill = {id: 'saved', crm_handoff_id: 3, crm_prefilled: true, header: {invoice_address: 'Edited'}};
    const selected = [];
    const adapter = {_draftRequestScope: () => "scope", crmHandoffId: 3, state: {bills: [bill]}, crmCall: async () => ({id: 5, draft_token: 'saved'}),
        selectBill: id => selected.push(id), syncContact: async () => {}, prefillHandoff: async () => { throw new Error('Repeated prefill'); }};
    await CrmPosAction.prototype.resumeHandoff.call(adapter);
    await CrmPosAction.prototype.resumeHandoff.call(adapter);
    expect(selected).toEqual(['saved']);
    expect(bill.header.invoice_address).toBe('Edited');
});

test("Invoices uses the existing Bill Wizard action with no CRM filters", () => {
    const actions = [];
    SalesWorkspace.prototype.openInvoices.call({action: {doAction: (...args) => actions.push(args)}});
    expect(actions).toEqual([['ab_sales.ab_sales_bill_wizard_action']]);
});

test("full native draft capacity never overwrites another bill", async () => {
    const original = {id: 'existing', header: {invoice_address: 'Keep'}};
    let warned = 0;
    const adapter = {crmPending: true, crmHandoffId: 1, state: {bills: [original]}, emptyDraftSlots: [],
        crmCall: async () => ({}), _draftRequestScope: () => 'scope', _draftLimitWarning: () => warned++};
    await CrmPosAction.prototype.createNewBill.call(adapter, 4);
    expect(warned).toBe(1);
    expect(adapter.state.bills).toEqual([original]);
    expect(original.header.invoice_address).toBe('Keep');
});

test("employee switch while loading prevents creating a handoff draft", async () => {
    let scope = 'original';
    const adapter = {crmPending: true, crmHandoffId: 1, _draftRequestScope: () => scope,
        crmCall: async () => { scope = 'different'; return {}; }};
    await CrmPosAction.prototype.createNewBill.call(adapter, 4);
    expect(adapter.crmCreating).toBe(false);
    expect(adapter.crmReady).toBe(undefined);
});

test("handoff creates a separate native draft and claims it before prefill", async () => {
    const native = registry.category('actions').get('ab_sales.pos');
    const original = {id: 'existing', header: {invoice_address: 'Keep'}};
    const created = {id: 'new', header: {}};
    const calls = [];
    patchWithCleanup(native.prototype, {async createNewBill(store) {
        calls.push(['native', store]); this.state.bills.push(created); this.currentBill = created; return true;
    }});
    const adapter = {crmPending: true, crmHandoffId: 1, state: {bills: [original]}, emptyDraftSlots: [{number: 2}],
        crmCall: async method => { calls.push(method); return {}; }, _draftRequestScope: () => 'scope',
        prefillHandoff: async bill => calls.push(['prefill', bill.id])};
    await CrmPosAction.prototype.createNewBill.call(adapter, 4);
    expect(calls).toEqual(['pos_handoff_prepare', ['native', 4], 'pos_handoff_claim', ['prefill', 'new']]);
    expect(original.header.invoice_address).toBe('Keep');
    expect(created.crm_handoff_id).toBe(1);
    expect(adapter.crmPending).toBe(false);
});
