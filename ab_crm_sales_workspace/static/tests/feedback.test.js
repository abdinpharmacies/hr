import {expect, test} from "@odoo/hoot";
import {makeMockEnv} from "@web/../tests/web_test_helpers";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {ConnectionLostError, ConnectionAbortedError} from "@web/core/network/rpc";
import {chatterFeedbackService} from "@ab_crm_sales_workspace/feedback";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

defineMailModels();

async function feedbackHarness() {
    await makeMockEnv();
    const notices = [];
    const feedback = chatterFeedbackService.start({}, {notification: {add(message, options) {
        const entry = {message: String(message), options, closed: false};
        notices.push(entry);
        return () => { entry.closed = true; options.onClose?.(); };
    }}});
    return {feedback, notices};
}

test("connection outages deduplicate, remain dismissed and recover after failed reads succeed", async () => {
    const {feedback, notices} = await feedbackHarness();
    let failed = true;
    const orm = {get silent() { return this; }, async call() {
        if (failed) throw new ConnectionLostError('/web/dataset/call_kw/ab_crm_conversation/workspace_customer_inbox');
        return {items: []};
    }};
    for (let index = 0; index < 3; index++) {
        await expect(feedback.call(orm, "ab_crm_conversation", "workspace_customer_inbox")).rejects.toThrow(ConnectionLostError);
    }
    expect(notices).toHaveLength(1);
    expect(notices[0].options.sticky).toBe(true);
    expect(notices[0].message).not.toInclude('/web/dataset');
    notices[0].options.onClose();
    await expect(feedback.call(orm, "ab_crm_conversation", "workspace_customer_inbox")).rejects.toThrow(ConnectionLostError);
    expect(notices).toHaveLength(1);
    failed = false;
    await feedback.call(orm, "ab_crm_chatter_api", "notifications");
    expect(notices).toHaveLength(1);
    await feedback.call(orm, "ab_crm_conversation", "workspace_customer_inbox");
    expect(notices).toHaveLength(2);
    expect(notices[1].message).toBe("Connection to Odoo restored.");
    expect(notices[0].closed).toBe(true);
    feedback.report(new ConnectionAbortedError());
    expect(notices).toHaveLength(2);
});

test("a failed send is not retried and keeps text, attachments and quote", async () => {
    const {feedback, notices} = await feedbackHarness();
    let sends = 0;
    const orm = {async call(model, method) {
        if (method === "action_reply") { sends++; throw new ConnectionLostError('/send'); }
        return {items: []};
    }};
    const attachment = {name: "keep.pdf", data: "YQ=="};
    const workspace = {feedback, state: {detail: {id: 1}, reply: "Keep draft", attachments: [attachment], replyTo: {id: 4}},
        sendDisabledReason: "", run: SalesWorkspace.prototype.run,
        call: (...args) => feedback.call(orm, ...args), clearAttachments() { throw new Error("Draft was cleared"); }};
    await SalesWorkspace.prototype.send.call(workspace);
    await feedback.call(orm, "ab_crm_conversation", "workspace_customer_inbox");
    expect(sends).toBe(1);
    expect(workspace.state.reply).toBe("Keep draft");
    expect(workspace.state.attachments).toEqual([attachment]);
    expect(workspace.state.replyTo).toEqual({id: 4});
    expect(workspace.state.busy).toBe(false);
    expect(notices[0].message).toInclude("Check the result before retrying an action.");
});

test("inbox refresh keeps current history during an outage and resumes without replacing drafts", async () => {
    const {feedback} = await feedbackHarness();
    let failed = true;
    const message = {id: 9, timestamp: "2026-11-10 10:00:00"};
    const orm = {async call(model, method) {
        if (failed) throw new ConnectionLostError('/inbox');
        if (method === "workspace_customer_inbox") return {items: [{id: 1}], has_more: false};
        return {id: 1, owned: true, messages: [message]};
    }};
    const workspace = {state: {inbox: [{id: 1, name: "Kept inbox"}], detail: {id: 1, messages: [message]},
        reply: "Draft", attachments: [{name: "draft.pdf"}]}, navigationVersion: 0,
        call: (...args) => feedback.call(orm, ...args), loadCustomerInbox: SalesWorkspace.prototype.loadCustomerInbox,
        refreshContacts: async () => {}};
    await expect(SalesWorkspace.prototype.refresh.call(workspace)).rejects.toThrow(ConnectionLostError);
    expect(workspace.state.inbox[0].name).toBe("Kept inbox");
    expect(workspace.state.detail.messages).toEqual([message]);
    expect(workspace.refreshing).toBe(false);
    failed = false;
    await SalesWorkspace.prototype.refresh.call(workspace);
    expect(workspace.state.inbox).toEqual([{id: 1}]);
    expect(workspace.state.reply).toBe("Draft");
    expect(workspace.state.attachments).toEqual([{name: "draft.pdf"}]);
});
