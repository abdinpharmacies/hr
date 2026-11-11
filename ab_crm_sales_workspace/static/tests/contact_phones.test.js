import {expect, test} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {contains, makeMockEnv, mountWithCleanup} from "@web/../tests/web_test_helpers";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {ChatterContacts} from "@ab_crm_sales_workspace/contacts";

defineMailModels();

test("contact phone actions retain the editor and submit confirmation separately", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const initial = {id: 7, name: "Saved customer", phone: "+201014763233", address: "", branch_id: 1,
        phones: [{id: 10, number: "+201014763233", label: "Personal", primary: true}]};
    const calls = [];
    const saved = [];
    env.services.dialog.add(ChatterContacts, {mode: "edit", token: "test", initial,
        onSaved: contact => saved.push(contact.id), call: async (model, method, args, values) => {
            calls.push([method, values]);
            if (method === "contact_search") return {contacts: [], branches: [{id: 1, name: "Branch"}], has_more: false};
            if (method === "contact_phone_add") return {...initial, phones: [...initial.phones, {id: 11, number: "+201012345678", label: "Work", primary: false}]};
            return {...initial, phone: "+201012345678", phones: [{id: 10, number: initial.phone, label: "Personal", primary: false}, {id: 11, number: "+201012345678", label: "Work", primary: true}]};
        }});
    await animationFrame(); await animationFrame();
    expect("#ab_contact_phone").toHaveAttribute("readonly");
    await contains('.ab_contact_phones textarea').edit("Customer confirmed the work number");
    await contains('input[placeholder="Additional number"]').edit("01012345678");
    await contains('.ab_contact_phones > input[placeholder="Phone label"]').edit("Work");
    await contains('.ab_contact_phones input[type="checkbox"]:first').click();
    await contains('button:contains(Add number)').click();
    expect(calls.find(call => call[0] === "contact_phone_add")[1].customer_confirmed).toBe(true);
    expect(".ab_chatter_contacts").toHaveCount(1);
    expect("#ab_contact_phone").toHaveValue(initial.phone);
    await contains('button:contains(Make primary)').click();
    expect(calls.at(-1)[1].phone_id).toBe(11);
    expect("#ab_contact_phone").toHaveValue("+201012345678");
    expect(saved).toEqual([7, 7]);
});

test("using an existing customer opens its editor with the proposed number for review", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const contact = {id: 7, name: "Saved customer", phone: "+201014763233", display_phone: "01014763233", address: "", branch_id: 1, phones: []};
    const saved = [];
    env.services.dialog.add(ChatterContacts, {mode: "add", token: "test", initial: {phone: "+201098320212"},
        onSaved: value => saved.push(value), call: async (model, method) => method === "contact_accounts" ? {accounts: []} : {contacts: [contact], branches: [{id: 1, name: "Branch"}]}});
    await animationFrame(); await animationFrame();
    expect('button:contains(Create new)').toHaveCount(1);
    await contains('button:contains(Saved customer)').click();
    expect('#ab_contact_phone').toHaveValue("01014763233");
    expect('input[placeholder="Additional number"]').toHaveValue("+201098320212");
    expect(saved).toHaveLength(0);
    expect('.ab_chatter_contacts').toHaveCount(1);
});

test("archival preselects the saved customer and keeps number archival separate", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    env.services.dialog.add(ChatterContacts, {mode: "delete", token: "test", initial: {id: 7, name: "Saved customer", phone: "+201014763233"},
        onSaved() {}, call: async () => ({contacts: [], branches: []})});
    await animationFrame(); await animationFrame();
    expect('.ab_chatter_contacts').toHaveText(/Archive contact\?/);
    expect('.ab_chatter_contacts').toHaveText(/Messages and orders remain/);
    expect('button:contains(Archive number)').toHaveCount(0);
    expect('.modal-footer button:contains(Archive)').toHaveCount(1);
});

test("merge review separates both contacts and submits the reviewed fingerprint", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const canonical = {id: 7, name: "Keep customer", phone: "+201098320212", display_phone: "01098320212", phones: []};
    const duplicate = {id: 8, name: "Duplicate customer", phone: "+201012345678", display_phone: "01012345678", phones: []};
    const calls = [];
    env.services.dialog.add(ChatterContacts, {mode: "consolidate", token: "test", initial: canonical, onSaved() {},
        call: async (model, method, args, values) => {
            calls.push([method, values]);
            if (method === "contact_search") return {contacts: [duplicate], branches: []};
            if (values.fingerprint) return canonical;
            return {canonical, duplicate, fingerprint: "reviewed-fingerprint",
                identity_details: [{id: 1, customer_id: 7, provider: "telegram", account: "12345"}],
                conversation_details: [{id: 2, customer_id: 8, provider: "whatsapp", destination: "01012345678", label: "Business inbox"}]};
        }});
    await animationFrame(); await animationFrame();
    await contains('button:contains(Duplicate customer)').click();
    expect('.ab_chatter_contacts section:first').toHaveText(/Keep customer/);
    expect('.ab_chatter_contacts section:first').toHaveText(/01098320212/);
    expect('.ab_chatter_contacts section:first').toHaveText(/12345/);
    expect('.ab_chatter_contacts section:last').toHaveText(/Duplicate customer/);
    expect('.ab_chatter_contacts section:last').toHaveText(/Business inbox/);
    await contains('.ab_chatter_contacts textarea').edit('Reviewed both customer records');
    await contains('.modal-footer button:contains(Save)').click();
    expect(calls.at(-1)[1]).toEqual({token: "test", canonical_id: 7, duplicate_id: 8,
        fingerprint: "reviewed-fingerprint", reason: "Reviewed both customer records"});
});

test("an exact verified phone match links without displaying a review reason", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const contact = {id: 7, name: "Same customer", phone: "+201012345678", display_phone: "01012345678"};
    const calls = [];
    const saved = [];
    env.services.dialog.add(ChatterContacts, {mode: "link", token: "test", conversationId: 9,
        onSaved: value => saved.push(value.id), call: async (model, method, args) => {
            calls.push([method, args]);
            if (method === "contact_search") return {contacts: [contact], branches: []};
            if (method === "action_preview_customer_link") return {automatic_match: true, fingerprint: "verified-match"};
            return {customer_id: 7, conversation_id: 9};
        }});
    await animationFrame(); await animationFrame();
    await contains('button:contains(Same customer)').click();
    await animationFrame();
    expect(calls.find(call => call[0] === "action_confirm_customer_link")[1]).toEqual([[9], 7, "verified-match"]);
    expect(saved).toEqual([7]);
    expect('.ab_chatter_contacts').toHaveCount(0);
});


test("manual contact linking needs neither a reason nor same-person checkbox", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const contact = {id: 7, name: "Existing customer", display_phone: "01012345678"};
    const calls = [];
    const saved = [];
    env.services.dialog.add(ChatterContacts, {mode: "link", token: "test", conversationId: 9, branchId: 3,
        onSaved: value => saved.push(value.id), call: async (model, method, args, kwargs) => {
            calls.push([method, args, kwargs]);
            if (method === "contact_search") return {contacts: [contact], branches: []};
            if (method === "action_preview_customer_link") return {automatic_match: false, requires_confirmation: true, fingerprint: "manual-match"};
            return {customer_id: 7, conversation_id: 9};
        }});
    await animationFrame(); await animationFrame();
    await contains('button:contains(Existing customer)').click();
    expect(calls.find(call => call[0] === "contact_search")[2]).toEqual({token: "test", query: "", offset: 0, branch_id: 3});
    expect('.ab_chatter_contacts textarea').toHaveCount(0);
    expect('.ab_chatter_contacts input[type="checkbox"]').toHaveCount(0);
    await contains('.modal-footer button:contains(Save)').click();
    expect(calls.find(call => call[0] === "action_confirm_customer_link")).toEqual([
        "action_confirm_customer_link", [[9], 7, "manual-match"], {resolve_conflict: false}]);
    expect(saved).toEqual([7]);
    expect('.ab_chatter_contacts').toHaveCount(0);
});
