import {expect, test} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {mountWithCleanup, contains, makeMockEnv} from "@web/../tests/web_test_helpers";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {LocationDialog} from "@ab_crm_sales_workspace/composer";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

defineMailModels();

const branch = {id: 4, revision: 2, language: "en_US", name: "Branch", address: "Street", latitude: 0, longitude: 180, store_id: 8, store_code: "08", region: "Region", hotline: "19036", details: "Branch\nStreet\nShared hotline: 19036", fallback: true};

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
    expect(".ab_branch_picker .ab_location_card").toHaveCount(1);
    expect("button:contains(Use for delivery)").toHaveCount(0);
    expect(".ab_branch_picker .alert-warning").toHaveCount(1);
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
    await contains(".ab_branch_picker input[type=checkbox]").click();
    expect(".ab_branch_picker pre").toHaveText(branch.details);
    expect(sends).toEqual([]);
    valid = false;
    await contains(".modal-footer button:first").click();
    expect("[role=alert]").toHaveText("This branch picker has expired. Open it again from the conversation.");
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
        state: {inbox: [{id: 1}], inboxQuery: "", detail: {id: 1, owned: true, messages: [{id: 1, body: "Old"}, {id: 60, body: "Recent"}], last_update_at: "before", has_older: false}, reply: "Draft", attachments: [{name: "draft.pdf"}], phone: ""},
        navigationVersion: 1, refreshContacts: async () => {},
        call: async (model, method, args, values) => {
            calls.push({method, values});
            if (method === "workspace_inbox") return [{id: 1}];
            return {id: 1, owned: true, last_update_at: "after", messages: values.message_ids ? [{id: 1, body: "Edited text", edited_at: "now"}] : values.after_id ? [] : [{id: 60, body: "Recent"}]};
        },
    };
    await SalesWorkspace.prototype.refresh.call(workspace);
    expect(workspace.state.detail.messages[0].body).toBe("Edited text");
    expect(calls.at(-1).values.message_ids).toEqual([1]);
    expect(workspace.state.reply).toBe("Draft");
    expect(workspace.state.attachments).toEqual([{name: "draft.pdf"}]);
});
