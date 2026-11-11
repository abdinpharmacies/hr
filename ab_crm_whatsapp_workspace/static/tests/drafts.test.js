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
    expect(".ab_attachment_menu").toHaveText(/WhatsApp templates/);
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
        expect(".ab_channel_button .badge").toHaveCount(0);
        expect(".ab_conversation .badge").toHaveText("3");
        expect(".ab_conversation.selected").toHaveCount(1);
    });
}

test("template picker offers all languages and explains unsupported layouts", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    env.services.dialog.add(WhatsAppTemplates, {conversationId: 1, call: async () => [
        {id: 1, name: "Arabic greeting", language: "ar", body: "Hello", parameters: [], unsupported_reason: "Unsupported header"},
        {id: 2, name: "English greeting", language: "en_US", body: "Hello", parameters: []},
    ]});
    await animationFrame();
    await animationFrame();
    expect(".ab_template_item").toHaveCount(2);
    await animationFrame();
    expect(".ab_template_editor .alert").toHaveCount(0);
    expect(".o_notification:contains(Unsupported header)").toHaveCount(1);
    expect("button:contains(Queue template)[disabled]").toHaveCount(1);
    await contains(".ab_template_list select").select("en_US");
    expect(".ab_template_item").toHaveCount(1);
    await contains(".ab_template_item").click();
    expect("button:contains(Queue template):not([disabled])").toHaveCount(1);
});

test("contact toolbar links the selected channel through the contact picker", async () => {
    const calls = [];
    class LinkHarness extends WhatsAppHarness {
        contacts(mode) { calls.push(mode); }
    }
    const workspace = await mountWithCleanup(LinkHarness);
    expect(".ab_contacts_header h3").toHaveText("Inbox");
    expect(".ab_contacts_header .ab_link_contact .fa-link").toHaveCount(1);
    expect(".ab_chat_header .ab_link_contact").toHaveCount(0);
    expect(".ab_link_contact").toHaveAttribute("aria-label", "Link to existing contact");
    expect(".ab_contact_tools button:contains(Link to existing contact)").toHaveCount(0);
    await contains(".ab_link_contact").click();
    expect(calls).toEqual(["link"]);
    workspace.state.busy = true;
    await animationFrame();
    expect(".ab_link_contact:disabled").toHaveCount(1);
    workspace.state.busy = false;
    workspace.state.detail = null;
    await animationFrame();
    expect(".ab_link_contact:disabled").toHaveCount(1);
    workspace.state.detail = {id: 2, name: "Customer", provider: "whatsapp", streams: [], messages: [], orders: []};
    await animationFrame();
    expect(".ab_link_contact:disabled").toHaveCount(0);
    expect(".ab_contact_tools").toHaveCount(0);
    expect(".ab_send svg").toHaveCount(1);
    expect(".ab_send").toHaveAttribute("aria-label", "Send message");
});

test("shared contacts render nested fields without identifying the sender", async () => {
    class CardsHarness extends WhatsAppHarness {
        setup() {
            super.setup();
            this.state.detail.messages = [{id: 1, body: "Contact shared", direction: "in", timestamp: "2026-11-09 12:00:00", status: "received", media: [], reactions: [],
                actions: {reply: {enabled: true}, react: {enabled: true}, reactions: []},
                contact_cards: [{name: {formatted_name: "Third party"}, phones: [{phone: "+201000000001"}], emails: [{email: "card@example.invalid"}],
                    addresses: [{street: "Street", city: "Cairo"}], org: {company: "Example", title: "Manager"}}]}];
        }
    }
    await mountWithCleanup(CardsHarness);
    expect(".ab_shared_contact").toHaveText(/Third party/);
    expect(".ab_shared_contact").toHaveText(/Street, Cairo/);
    expect(".ab_shared_contact").toHaveText(/Example · Manager/);
    expect(".ab_contact_title h3").toHaveText("Customer");
});

for (const direction of ["ltr", "rtl"]) {
    test(`two WhatsApp numbers use one channel chooser in ${direction}`, async () => {
        const selected = [];
        class MultiNumberHarness extends WhatsAppHarness {
            setup() {
                super.setup();
                this.direction = direction;
                this.state.detail.streams = [
                    {id: 2, provider: "whatsapp", destination: "+201014763233", label: "Business inbox", unread: 2},
                    {id: 3, provider: "whatsapp", destination: "+201012345678", label: "Business inbox", unread: 1},
                    {id: 4, provider: "telegram", destination: "verified-account", label: "Telegram", unread: 0},
                ];
            }
            select(id, channel) { selected.push([id, channel]); }
        }
        await mountWithCleanup(MultiNumberHarness);
        expect(".ab_channel_button").toHaveCount(2);
        await contains('.ab_channel_button[data-channel="whatsapp"]').click();
        expect(".ab_channel_chooser button").toHaveCount(2);
        expect(".ab_channel_chooser").toHaveText(/201014763233/);
        await contains(".ab_channel_chooser button:last").click();
        expect(selected).toEqual([[3, true]]);
        await contains('.ab_channel_button[data-channel="telegram"]').click();
        expect(selected).toEqual([[3, true], [4, true]]);
    });
}


test("unlink is available only for grouped conversations and preserves the draft", async () => {
    const calls = [];
    class UnlinkHarness extends WhatsAppHarness {
        setup() {
            super.setup();
            this.drafts = new Map();
            this.state.detail.contact = {id: 7, can_manage: true};
            this.state.detail.streams = [{id: 2, provider: "whatsapp"}];
            this.state.reply = "Keep draft";
            this.state.attachments = [{name: "keep.pdf"}];
        }
        async call(model, method, args) {
            calls.push([method, args]);
            return {fingerprint: "group-snapshot", conversation_ids: [1, 2, 3]};
        }
        async refresh() {
            this.state.detail.contact = false;
            this.state.detail.streams = [{id: 2, provider: "whatsapp"}];
        }
    }
    const workspace = await mountWithCleanup(UnlinkHarness);
    expect('.ab_unlink_contact').toHaveCount(0);
    expect('button:contains(Consolidate duplicate contact)').toHaveCount(0);
    workspace.state.detail.streams.push({id: 1, provider: "telegram"}, {id: 3, provider: "whatsapp"});
    await animationFrame();
    expect('.ab_contacts_header .ab_unlink_contact:not(:disabled)').toHaveCount(1);
    workspace.state.busy = true;
    await animationFrame();
    expect('.ab_unlink_contact:disabled').toHaveCount(1);
    workspace.state.busy = false;
    workspace.state.channelChooser = "whatsapp";
    await animationFrame();
    await contains('.ab_unlink_contact').click();
    expect(calls).toEqual([
        ["action_preview_customer_unlink", [[2], 7]],
        ["action_unlink_customer", [[2], 7, "group-snapshot"]],
    ]);
    expect(workspace.drafts.get(2).reply).toBe("Keep draft");
    expect(workspace.drafts.get(2).attachments).toEqual([{name: "keep.pdf"}]);
    expect(workspace.state.channelChooser).toBe(null);
    expect(workspace.state.detail.id).toBe(2);
    expect('.ab_unlink_contact').toHaveCount(0);
});
