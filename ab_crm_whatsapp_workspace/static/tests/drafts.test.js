import {WhatsAppTemplates} from "@ab_crm_whatsapp_workspace/templates";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {animationFrame} from "@odoo/hoot-mock";
import {expect, test} from "@odoo/hoot";
import {useState, useRef} from "@odoo/owl";
import {mountWithCleanup, makeMockEnv, contains} from "@web/../tests/web_test_helpers";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

test("Telegram and WhatsApp drafts retain separate text, attachments and quotes", () => {
    const workspace = {drafts: new Map(), state: {detail: {id: 1}, reply: "Telegram draft", attachments: [{name: "telegram.pdf"}], replyTo: {id: 11}}};
    SalesWorkspace.prototype.rememberDraft.call(workspace);
    workspace.state = {detail: {id: 2}, reply: "WhatsApp draft", attachments: [{name: "whatsapp.pdf"}], replyTo: {id: 22}};
    SalesWorkspace.prototype.rememberDraft.call(workspace);
    expect(workspace.drafts.get(1)).toEqual({reply: "Telegram draft", attachments: [{name: "telegram.pdf"}], replyTo: {id: 11}});
    expect(workspace.drafts.get(2)).toEqual({reply: "WhatsApp draft", attachments: [{name: "whatsapp.pdf"}], replyTo: {id: 22}});
});


defineMailModels();

class WhatsAppHarness extends SalesWorkspace {
    setup() {
        this.direction = "ltr";
        this.messagesRef = useRef("messages");
        this.replyRef = useRef("reply");
        this.filesRef = useRef("files");
        this.state = useState({loggedIn: true, inbox: [], contacts: [], attachments: [], reply: "", employee: "Agent", inboxQuery: "",
            detail: {id: 2, name: "Customer", phone: "", can_send: true, owned: true, provider: "whatsapp", streams: [],
                whatsapp_templates: true, messages: [], orders: []}});
    }
}

test("WhatsApp composition enables text and approved templates", async () => {
    await mountWithCleanup(WhatsAppHarness);
    expect(".ab_composer fieldset:disabled").toHaveCount(0);
    expect(".ab_composer textarea").toHaveCount(1);
    await contains(".ab_attach_toggle").click();
    expect(".ab_attachment_menu").toHaveText(/Approved WhatsApp templates/);
});

test("WhatsApp composition retains RTL direction", async () => {
    class RTLWhatsAppHarness extends WhatsAppHarness {
        setup() { super.setup(); this.direction = "rtl"; }
    }
    await mountWithCleanup(RTLWhatsAppHarness);
    expect(".ab_crm_sales_workspace").toHaveAttribute("dir", "rtl");
    expect(".ab_composer fieldset:disabled").toHaveCount(0);
});

test("approved templates select first, render parameters and only queue complete values", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const calls = [];
    env.services.dialog.add(WhatsAppTemplates, {conversationId: 1, call: async (model, method, args, kwargs) => {
        calls.push([method, kwargs]);
        return [{id: 1, name: "Approved greeting", language: "en", body: "Hello {{1}}", parameters: [1]}];
    }});
    await animationFrame();
    await animationFrame();
    expect(".ab_template_item.active").toHaveCount(1);
    expect("button:contains(Queue template)[disabled]").toHaveCount(1);
    await contains(".ab_template_editor input").edit("   ");
    expect("button:contains(Queue template)[disabled]").toHaveCount(1);
    await contains(".ab_template_editor input").edit("Customer");
    expect(".ab_template_preview").toHaveText("Hello Customer");
    expect(calls.map(call => call[0])).toEqual(["whatsapp_templates"]);
    await contains("button:contains(Queue template)").click();
    expect(calls.at(-1)).toEqual(["action_whatsapp_template", {parameters: ["Customer"]}]);
});

test("customer inbox restores the selected stream without changing message destinations", () => {
    const item = {id: 2, group_key: "shared", streams: [{id: 1}, {id: 2}]};
    const workspace = {employeeId: 8, selectedStreams: new Map(), state: {detail: {id: 1}, reply: "Telegram", attachments: [], replyTo: null}, drafts: new Map()};
    SalesWorkspace.prototype.rememberDraft.call(workspace);
    expect(SalesWorkspace.prototype.preferredStream.call(workspace, item)).toBe(2);
    workspace.preferredStream = SalesWorkspace.prototype.preferredStream;
    workspace.select = id => id;
    expect(SalesWorkspace.prototype.selectCustomer.call(workspace, item)).toBe(2);
    expect(workspace.drafts.get(1).reply).toBe("Telegram");
    expect(workspace.drafts.has(2)).toBe(false);
});

for (const direction of ["ltr", "rtl"]) {
    test(`one customer row exposes two independent streams in ${direction}`, async () => {
        class GroupedHarness extends WhatsAppHarness {
            setup() {
                super.setup();
                this.direction = direction;
                this.state.inbox = [{id: 2, group_key: "shared", name: "Customer", channels: ["telegram", "whatsapp"], unread: 3,
                    streams: [{id: 1, provider: "telegram"}, {id: 2, provider: "whatsapp"}]}];
                this.state.detail.streams = [{id: 1, provider: "telegram", label: "Telegram", unread: 1}, {id: 2, provider: "whatsapp", label: "WhatsApp", unread: 2}];
            }
        }
        await mountWithCleanup(GroupedHarness);
        expect(".ab_conversation").toHaveCount(1);
        expect(".ab_channel_button").toHaveCount(2);
        expect(".ab_channel_button .badge").toHaveCount(2);
        expect(".ab_conversation .badge").toHaveText("3");
        expect(".ab_conversation.selected").toHaveCount(1);
    });
}
