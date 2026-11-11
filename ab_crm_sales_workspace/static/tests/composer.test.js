import {user} from "@web/core/user";
import {expect, test, getFixture} from "@odoo/hoot";
import {runAllTimers} from "@odoo/hoot-dom";
import {animationFrame} from "@odoo/hoot-mock";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {mountWithCleanup, contains, makeMockEnv, patchWithCleanup} from "@web/../tests/web_test_helpers";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {LocationDialog} from "@ab_crm_sales_workspace/composer";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

defineMailModels();

const branch = {id: 4, revision: 2, language: "en_US", name: "Branch", address: "Street", latitude: 0, longitude: 180, store_id: 8, store_code: "08", region: "Region", hotline: "19036", details: "Branch\nStreet\nShared hotline: 19036", fallback: true};

async function chooseBranch() {
    await contains(".ab_branch_search input").edit("Branch", {confirm: false});
    await runAllTimers();
    await animationFrame();
    await contains(".ab_branch_search [role=option]:first").click();
    await animationFrame();
}

test("branch picker previews a native card and sends selected server revision", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const calls = [];
    const call = async (model, method, args) => {
        calls.push({method, args});
        return method === "workspace_branch_directory" ? [branch] : method === "workspace_branch_preview" ? branch : 1;
    };
    env.services.dialog.add(LocationDialog, {call, conversationId: 1, valid: () => true, storeId: 8});
    await animationFrame();
    await chooseBranch();
    expect(".ab_branch_picker .ab_location_card").toHaveCount(1);
    expect("button:contains(Use for delivery)").toHaveCount(0);
    expect(".ab_branch_picker .alert-warning").toHaveCount(0);
    expect(".o_notification").toHaveText(/Some text is unavailable/);
    await contains(".modal-footer button:first").click();
    const sent = calls.find(call => call.method === "action_share_branch");
    expect(sent.args.slice(0, 4)).toEqual([[1], 4, 2, "en_US"]);
    expect(sent.args[4].length).toBe(36);
    expect(sent.args[5]).toBe(false);
});

test("branch details are explicit and expired navigation prevents a send", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const sends = [];
    let valid = true;
    env.services.dialog.add(LocationDialog, {conversationId: 1, storeId: 8, valid: () => valid,
        call: async (model, method, args) => method === "workspace_branch_directory" ? [branch] : method === "workspace_branch_preview" ? branch : sends.push(args)});
    await animationFrame();
    await chooseBranch();
    await contains(".ab_branch_picker input[type=checkbox]").click();
    expect(".ab_branch_picker pre").toHaveText(branch.details);
    expect(sends).toEqual([]);
    valid = false;
    await contains(".modal-footer button:first").click();
    expect(".o_notification:contains(This branch picker has expired)").toHaveCount(1);
    expect(sends).toEqual([]);
});

test("branch picker preserves composer text attachments replies and navigation epoch", () => {
    let props;
    const workspace = {state: {detail: {id: 1, owned: true, orders: []}, reply: "Draft", attachments: [{name: "file"}], replyTo: {id: 5}}, navigationVersion: 3,
        call: () => {}, dialog: {add: (component, values) => { props = values; }}};
    const before = structuredClone(workspace.state);
    SalesWorkspace.prototype.location.call(workspace);
    expect(props.valid()).toBe(true);
    workspace.navigationVersion++;
    expect(props.valid()).toBe(false);
    expect(workspace.state.reply).toBe(before.reply);
    expect(workspace.state.attachments).toEqual(before.attachments);
    expect(workspace.state.replyTo).toEqual(before.replyTo);
});

test("a file picker opened in another conversation cannot attach to the current draft", async () => {
    const attached = [];
    const workspace = {state: {detail: {id: 2}}, fileConversationId: 1,
        attachFiles: files => attached.push(files)};
    const target = {files: [new File(["data"], "document.pdf", {type: "application/pdf"})], value: "selected"};
    await SalesWorkspace.prototype.filesChanged.call(workspace, {target});
    expect(attached).toEqual([]);
    expect(target.value).toBe("");
    workspace.fileConversationId = 2;
    await SalesWorkspace.prototype.filesChanged.call(workspace, {target});
    expect(attached.length).toBe(1);
});

test("branch details checkbox adds details while always sharing the location", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const sends = [];
    env.services.dialog.add(LocationDialog, {conversationId: 1, storeId: 8, valid: () => true,
        call: async (model, method, args) => method === "workspace_branch_directory" ? [branch] : method === "workspace_branch_preview" ? branch : sends.push({method, args})});
    await animationFrame();
    await chooseBranch();
    expect(".ab_branch_picker input[type=checkbox]").not.toBeChecked();
    await contains(".ab_branch_picker input[type=checkbox]").click();
    expect(".ab_branch_picker .ab_location_card").toHaveCount(1);
    expect(".ab_branch_picker pre").toHaveText(branch.details);
    await contains(".modal-footer button:first").click();
    expect(sends.length).toBe(1);
    expect(sends[0].method).toBe("action_share_branch");
    expect(sends[0].args[5]).toBe(true);
});

test("refresh updates edited messages in loaded older history without changing drafts", async () => {
    const calls = [];
    const workspace = {
        loadCustomerInbox: SalesWorkspace.prototype.loadCustomerInbox,
        state: {inbox: [{id: 1}], inboxQuery: "", detail: {id: 1, owned: true, messages: [{id: 1, body: "Old"}, {id: 60, body: "Recent"}], last_update_at: "before", has_older: false}, reply: "Draft", attachments: [{name: "draft.pdf"}], phone: ""},
        navigationVersion: 1, refreshContacts: async () => {},
        call: async (model, method, args, values) => {
            calls.push({method, values});
            if (method === "workspace_customer_inbox") return {items: [{id: 1, group_key: "test", streams: [{id: 1}]}], has_more: false};
            return {id: 1, owned: true, last_update_at: "after", messages: values.message_ids ? [{id: 1, body: "Edited text", edited_at: "now"}] : values.after_id ? [] : [{id: 60, body: "Recent"}]};
        },
    };
    await SalesWorkspace.prototype.refresh.call(workspace);
    expect(workspace.state.detail.messages[0].body).toBe("Edited text");
    expect(calls.at(-1).values.message_ids).toEqual([1]);
    expect(workspace.state.reply).toBe("Draft");
    expect(workspace.state.attachments).toEqual([{name: "draft.pdf"}]);
});

for (const lang of ["en_US", "ar", "ar_001"]) {
    test(`branch search starts collapsed and sends Arabic without a language selector for ${lang}`, async () => {
        patchWithCleanup(user, {context: {...user.context, lang}});
        const env = await makeMockEnv();
        await mountWithCleanup(MainComponentsContainer);
        const calls = [];
        env.services.dialog.add(LocationDialog, {conversationId: 1, storeId: 8, valid: () => true,
            call: async (model, method, args) => {
                calls.push({method, args});
                if (method === "workspace_branch_directory") return [branch];
                if (method === "workspace_branch_preview") return {...branch, language: args[2]};
            }});
        await animationFrame();
        expect(".ab_branch_picker select").toHaveCount(0);
        expect(".ab_branch_search [role=combobox]").toBeFocused();
        expect(".ab_branch_search [role=option]").toHaveCount(0);
        expect(".ab_branch_picker .ab_location_card").toHaveCount(0);
        expect(".ab_branch_search_header input[type=checkbox]").toHaveCount(1);
        expect(".modal-footer button:first").not.toBeEnabled();
        expect(calls).toEqual([]);
        await chooseBranch();
        expect(".ab_branch_search [role=option]").toHaveCount(0);
        expect(".ab_branch_picker .ab_location_card").toHaveCount(1);
        expect(calls.map(call => call.args[2])).toEqual(["ar_001", "ar_001"]);
        await contains(".modal-footer button:first").click();
        expect(calls.at(-1).method).toBe("action_share_branch");
        expect(calls.at(-1).args[3]).toBe("ar_001");
    });
}

test("branch search supports keyboard selection, clearing and no matches", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const calls = [];
    env.services.dialog.add(LocationDialog, {conversationId: 1, valid: () => true,
        call: async (model, method, args) => {
            calls.push(method);
            return method === "workspace_branch_directory" ? (args[1] === "missing" ? [] : [branch]) : branch;
        }});
    await animationFrame();
    await contains(".ab_branch_search input").edit("Branch", {confirm: false});
    await runAllTimers();
    await animationFrame();
    await contains(".ab_branch_search input").press("Escape");
    expect(".ab_branch_picker").toHaveCount(1);
    expect(".ab_branch_search [role=option]").toHaveCount(0);
    await contains(".ab_branch_search input").press("ArrowDown");
    await animationFrame();
    await contains(".ab_branch_search input").press("Enter");
    await animationFrame();
    expect(".ab_branch_picker .ab_location_card").toHaveCount(1);
    await contains(".ab_branch_search input").edit("", {confirm: false});
    expect(".ab_branch_picker .ab_location_card").toHaveCount(0);
    expect(".modal-footer button:first").not.toBeEnabled();
    const before = calls.length;
    await runAllTimers();
    await animationFrame();
    expect(calls.length).toBe(before);
    expect(".ab_branch_search [role=option]").toHaveCount(0);
    await contains(".ab_branch_search input").edit("missing", {confirm: false});
    await runAllTimers();
    await animationFrame();
    expect(".ab_branch_search .dropdown-menu").toHaveText("No reviewed branches available.");
    expect(".modal-footer button:first").not.toBeEnabled();
});

test("stale branch results and previews cannot select a replaced query", async () => {
    let resolve;
    const picker = {state: {query: "first", preview: null, error: ""}, sequence: 0, check() {},
        props: {conversationId: 1, call: () => new Promise(done => { resolve = done; })}};
    const pendingSearch = LocationDialog.prototype.search.call(picker, "first");
    LocationDialog.prototype.searchInput.call(picker, {target: {value: "second"}});
    resolve([branch]);
    expect(await pendingSearch).toEqual([]);
    const pendingPreview = LocationDialog.prototype.preview.call(picker, branch.id);
    LocationDialog.prototype.searchInput.call(picker, {target: {value: ""}});
    resolve(branch);
    await pendingPreview;
    expect(picker.state.preview).toBe(null);
});

for (const direction of ["ltr", "rtl"]) {
    test(`branch dropdown fits the search field and header wraps at narrow width in ${direction}`, async () => {
        const env = await makeMockEnv();
        await mountWithCleanup(MainComponentsContainer);
        env.services.dialog.add(LocationDialog, {conversationId: 1, valid: () => true,
            call: async () => [branch]});
        await animationFrame();
        const picker = getFixture().querySelector(".ab_branch_picker");
        picker.dir = direction;
        picker.closest(".modal-dialog").style.width = "360px";
        await contains(".ab_branch_search input").edit("Branch", {confirm: false});
        await runAllTimers();
        await animationFrame();
        const input = picker.querySelector(".ab_branch_search input");
        const menu = picker.querySelector(".dropdown-menu");
        expect(Math.abs(input.getBoundingClientRect().width - menu.getBoundingClientRect().width) < 2).toBe(true);
        expect(picker.scrollWidth <= picker.clientWidth).toBe(true);
        expect(picker.querySelector(".ab_branch_search_header").scrollWidth <= picker.clientWidth).toBe(true);
        await contains(".ab_branch_details_toggle").click();
        expect(".ab_branch_search [role=option]").toHaveCount(0);
    });
}

test("live refresh uses the ingestion cursor after historical timestamp sorting", async () => {
    const positions = [];
    const workspace = {
        loadCustomerInbox: SalesWorkspace.prototype.loadCustomerInbox,
        state: {inbox: [], inboxQuery: "", detail: {id: 1, message_cursor: 90, messages: [{id: 2, timestamp: "2026-01-01"}, {id: 1, timestamp: "2026-01-02"}]}, attachments: [], phone: ""},
        navigationVersion: 1, refreshContacts: async () => {},
        call: async (model, method, args, values) => {
            if (method === "workspace_customer_inbox") return {items: [], has_more: false};
            positions.push(values.after_id);
            return {id: 1, owned: true, message_cursor: 91, messages: [{id: 91, timestamp: "2026-11-09", body: "Fresh"}]};
        },
    };
    await SalesWorkspace.prototype.refresh.call(workspace);
    expect(positions[0]).toBe(90);
    expect(workspace.state.detail.messages.at(-1).id).toBe(91);
});
