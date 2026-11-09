import {expect, test, getFixture} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {useState, useRef, xml} from "@odoo/owl";
import {mountWithCleanup, patchWithCleanup, contains, makeMockEnv, mockService} from "@web/../tests/web_test_helpers";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {user} from "@web/core/user";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";
import {MessagePreview, messageDate, compactUpdateTime, visibleMessageId} from "@ab_crm_sales_workspace/message";

defineMailModels();

const statuses = ["waiting", "sending", "retrying", "sent", "delivered", "read", "failed", "retry_failed", "uncertain"];
function message(id, status, direction = "out") {
    return {id, status, direction, body: "Hello مرحبا 123\nSecond line", timestamp: "2026-11-07 12:00:00", media: [], reactions: [],
        actions: {reply: {enabled: true, reason: ""}, react: {enabled: true, reason: ""}, reactions: ["👍", "❤", "👎"],
            edit: {enabled: false, reason: "Unsupported edit"}, delete: {enabled: false, reason: "Unsupported delete"}}};
}
class ChatterHarness extends SalesWorkspace {
    setup() {
        this.direction = "ltr";
        this.messagesRef = useRef("messages"); this.replyRef = useRef("reply"); this.filesRef = useRef("files");
        this.state = useState({loggedIn: true, inbox: [], contacts: [], attachments: [], reply: "", employee: "Agent", inboxQuery: "",
            detail: {id: 1, name: "Customer", phone: "+201012345678", can_send: true, owned: true, provider: "telegram", streams: [],
                messages: [...statuses.map((status, index) => message(index + 1, status)), message(10, "received", "in")], orders: []}});
    }
}

test("UTC timestamps use the Odoo user timezone", () => {
    patchWithCleanup(user, {context: {...user.context, tz: "Asia/Dubai"}});
    expect(messageDate("2026-11-07 23:30:00").hour).toBe(3);
    expect(messageDate("2026-11-07 23:30:00").day).toBe(8);
});

test("all receipt states render on outgoing bubbles only", async () => {
    await mountWithCleanup(ChatterHarness);
    expect(".ab_message.out .ab_receipt").toHaveCount(9);
    expect(".ab_message.in .ab_receipt").toHaveCount(0);
    expect(".ab_receipt.status-sent path").toHaveCount(1);
    expect(".ab_receipt.status-delivered path").toHaveCount(2);
    expect(".ab_receipt.status-read path").toHaveCount(2);
    expect(".ab_message time[title]").toHaveCount(10);
    expect(".ab_day_separator").toHaveCount(1);
    expect(".ab_message_search").toHaveCount(0);
});

test("message menu hides unsupported mutations and restores focus", async () => {
    await mountWithCleanup(ChatterHarness);
    getFixture().querySelector(".ab_crm_sales_workspace").style.height = "700px";
    getFixture().querySelector(".ab_message_menu").focus();
    await animationFrame();
    await contains(".ab_message_menu:first").click();
    expect(".ab_chatter_message_menu button:disabled").toHaveCount(0);
    expect(".ab_chatter_message_menu").toHaveText("Reply\nReact\nCopy");
    await contains(".ab_chatter_message_menu").press("Escape");
    expect(".ab_chatter_message_menu").toHaveCount(0);
    expect(".ab_message_menu:first").toBeFocused();
});

test("read position requires visible tab, unobscured container and visible message bottom", () => {
    const fixture = getFixture();
    fixture.innerHTML = '<div class="stream"><article data-message-id="1"></article><article data-message-id="2"></article></div>';
    const stream = fixture.querySelector(".stream");
    patchWithCleanup(stream, {getBoundingClientRect: () => ({top: 0, bottom: 100, left: 0, right: 100})});
    patchWithCleanup(stream.children[0], {getBoundingClientRect: () => ({top: 10, bottom: 80, left: 0, right: 80})});
    patchWithCleanup(stream.children[1], {getBoundingClientRect: () => ({top: 90, bottom: 130, left: 0, right: 80})});
    patchWithCleanup(document, {get visibilityState() { return "visible"; }});
    expect(visibleMessageId(stream)).toBe(1);
    document.body.classList.add("modal-open");
    expect(visibleMessageId(stream)).toBe(null);
    document.body.classList.remove("modal-open");
    patchWithCleanup(document, {get visibilityState() { return "hidden"; }});
    expect(visibleMessageId(stream)).toBe(null);
});

test("clipboard rejection becomes visible feedback", async () => {
    await makeMockEnv();
    patchWithCleanup(navigator, {clipboard: {writeText: async () => { throw new Error("Denied"); }}});
    const workspace = {state: {}};
    await SalesWorkspace.prototype.copy.call(workspace, {body: "caption"});
    expect(String(workspace.state.error)).toBe("Couldn’t copy the message. Check clipboard permissions.");
});

test("channel selection preserves separate drafts and attachments", async () => {
    const attachment = {url: "blob:test"};
    const workspace = {state: {detail: {id: 1}, searchResults: [{id: 5, body: "Previous conversation"}], reply: "first", attachments: [attachment], replyTo: {id: 4}},
        drafts: new Map([[2, {reply: "second", attachments: []}]]), navigationVersion: 0,
        stopRecording() {}, clearSearch: SalesWorkspace.prototype.clearSearch, rememberDraft: SalesWorkspace.prototype.rememberDraft,
        run: async callback => callback(), call: async (model, method, args) => {
            expect(method).toBe("workspace_channel"); expect(args).toEqual([[1], 2]);
            return {id: 2, phone: "", candidates: []};
        }};
    await SalesWorkspace.prototype.select.call(workspace, 2, true);
    expect(workspace.state.reply).toBe("second");
    expect(workspace.state.searchResults).toEqual([]);
    expect(workspace.drafts.get(1).attachments).toEqual([attachment]);
    expect(workspace.drafts.get(1).replyTo.id).toBe(4);
});

test("stale channel response cannot replace a newer conversation", async () => {
    let resolve;
    const workspace = {state: {detail: {id: 1}, attachments: []}, navigationVersion: 0,
        stopRecording() {}, rememberDraft() {}, run: async callback => callback(),
        call: () => new Promise(done => { resolve = done; })};
    const selection = SalesWorkspace.prototype.select.call(workspace, 2, true);
    workspace.navigationVersion++;
    resolve({id: 2}); await selection;
    expect(workspace.state.detail.id).toBe(1);
});

test("unsupported reaction is never submitted", () => {
    const workspace = {conversationAction: () => { throw new Error("Unexpected send"); }};
    SalesWorkspace.prototype.react.call(workspace, message(1, "sent"), "😀");
    const denied = message(2, "sent"); denied.actions.react.enabled = false;
    SalesWorkspace.prototype.react.call(workspace, denied, "👍");
    expect(true).toBe(true);
});

test("download failures produce feedback without opening a viewer", async () => {
    await makeMockEnv();
    const workspace = {state: {}, navigationVersion: 1,
        call: async () => { throw new Error("Unavailable"); },
        run: async callback => { try { await callback(); } catch (error) { workspace.state.error = error.message; } }};
    await SalesWorkspace.prototype.preview.call(workspace, {id: 1}, true);
    expect(workspace.state.error).toBe("Couldn’t download the attachment. Try again.");
});

test("denied quote resolution displays the unavailable fallback", async () => {
    const quote = {id: 3, available: true};
    const workspace = {state: {detail: {id: 1}}, navigationVersion: 0,
        run: async callback => callback(), call: async () => { throw new Error("Access denied"); }};
    await SalesWorkspace.prototype.openQuote.call(workspace, quote);
    expect(quote.available).toBe(false);
});

test("closing the attachment viewer releases its object URL", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const url = URL.createObjectURL(new Blob([Uint8Array.from(atob("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jvXcAAAAASUVORK5CYII="), character => character.charCodeAt(0))], {type: "image/png"}));
    const revoke = URL.revokeObjectURL.bind(URL);
    patchWithCleanup(URL, {revokeObjectURL: value => { expect.step(value); revoke(value); }});
    const close = env.services.dialog.add(MessagePreview, {url, media: {name: "pixel.png", kind: "image", mimetype: "image/png"}});
    await animationFrame();
    expect(".ab_chatter_media_viewer img").toHaveCount(1);
    close();
    await animationFrame();
    expect.verifySteps([url]);
});

test("compact update time uses local day, recent weekday and older date", () => {
    patchWithCleanup(user, {context: {...user.context, tz: "Asia/Dubai"}});
    const now = luxon.DateTime.fromISO("2026-11-08T12:00:00", {zone: "Asia/Dubai"});
    expect(compactUpdateTime("2026-11-08 05:51:00", now)).toBe("9:51 AM");
    expect(compactUpdateTime("2026-11-07 05:51:00", now)).toBe("Sat");
    expect(compactUpdateTime("2026-11-01 05:51:00", now)).toBe("Nov 1");
    expect(compactUpdateTime("2026-11-07 23:30:00", now)).toBe("3:30 AM");
});

test("compact header uses icon channels and no redundant helper lines", async () => {
    const component = await mountWithCleanup(ChatterHarness);
    component.state.detail.streams = [{id: 1, provider: "telegram", label: "Bot"}, {id: 2, provider: "whatsapp", label: "Phone"}];
    component.state.detail.last_update_at = "2026-11-07 12:00:00";
    await animationFrame();
    expect(".ab_contact_title time").toHaveCount(1);
    expect(".ab_channel_button").toHaveCount(2);
    expect(".ab_channel_button.active .ab_channel_led").toHaveCount(1);
    expect(".ab_channel_button").toHaveText("");
    expect(".ab_latest_status").toHaveCount(0);
    expect(".ab_composer small[role='status']").toHaveCount(0);
});

test("failed bubbles use an accessible inline retry and retain the message element", async () => {
    const component = await mountWithCleanup(ChatterHarness);
    const failed = component.state.detail.messages.find(row => row.status === "failed");
    failed.explanation = "This attachment couldn’t be sent. Choose another file.";
    failed.retry_operation_id = 70;
    patchWithCleanup(component, {retry: async row => { expect.step(String(row.id)); row.status = "retrying"; row.retry_operation_id = false; }});
    await animationFrame();
    const element = getFixture().querySelector(`[data-message-id='${failed.id}']`);
    expect(".ab_message_explanation").toHaveCount(0);
    expect(".can_retry[aria-label='Retry sending']").toHaveCount(1);
    expect(".ab_receipt.status-uncertain.can_retry").toHaveCount(0);
    await contains(".can_retry[aria-label='Retry sending']").click();
    expect.verifySteps([String(failed.id)]);
    expect(getFixture().querySelector(`[data-message-id='${failed.id}']`)).toBe(element);
    expect(".ab_receipt.status-retrying").toHaveCount(2);
});

test("retry updates the existing operation and an older loaded message", async () => {
    const row = message(1, "failed"); row.retry_operation_id = 73;
    const workspace = {state: {detail: {id: 5, messages: [row, message(90, "sent")] }}, navigationVersion: 1,
        run: async callback => callback(), refresh: async () => {},
        refreshMessage: SalesWorkspace.prototype.refreshMessage,
        call: async (model, method, args) => {
            expect.step(method);
            if (method === "action_retry") expect(args).toEqual([[73]]);
            else return {messages: [{...row, status: "retrying"}]};
        }};
    await SalesWorkspace.prototype.retry.call(workspace, row);
    expect.verifySteps(["action_retry", "workspace_detail"]);
    expect(workspace.state.detail.messages.map(row => row.id)).toEqual([1, 90]);
    expect(workspace.state.detail.messages[0].status).toBe("retrying");
});

test("preview has channel styling and a download action", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    const url = URL.createObjectURL(new Blob(["preview"], {type: "audio/ogg"}));
    const close = env.services.dialog.add(MessagePreview, {url, provider: "whatsapp", media: {name: "voice.ogg", kind: "audio", mimetype: "audio/ogg"}});
    await animationFrame();
    expect(".ab_chatter_preview_dialog.channel-whatsapp").toHaveCount(1);
    expect(".ab_preview_download[download='voice.ogg']").toHaveCount(1);
    close();
});

test("retry warning changes on keyboard focus and channel colors remain scoped", async () => {
    const component = await mountWithCleanup(ChatterHarness);
    const failed = component.state.detail.messages.find(row => row.status === "failed");
    failed.retry_operation_id = 71;
    await animationFrame();
    const chat = getFixture().querySelector(".ab_chat");
    expect(getComputedStyle(chat).getPropertyValue("--ab-channel").trim()).toBe("#258bbd");
    const warning = getFixture().querySelector(".can_retry .ab_warning_icon");
    const retry = getFixture().querySelector(".can_retry .ab_retry_icon");
    expect(getComputedStyle(retry).display).toBe("none");
    getFixture().querySelector(".can_retry").focus();
    await animationFrame();
    expect(getComputedStyle(warning).display).toBe("none");
    expect(getComputedStyle(retry).display).not.toBe("none");
    component.state.detail.provider = "whatsapp";
    await animationFrame();
    expect(getComputedStyle(chat).getPropertyValue("--ab-channel").trim()).toBe("#239b68");
});

for (const direction of ["ltr", "rtl"]) {
    test(`conversation opens at latest after mount and delayed navigation in ${direction}`, async () => {
        mockService("ab_chatter_session", {current: {token: "test"}, workspaceDrafts: new Map()});
        let resolveDetail;
        const detail = id => ({id, phone: "", owned: true, messages: Array.from({length: 50}, (_, index) => ({id: id * 100 + index})), has_older: true});
        class ScrollHarness extends SalesWorkspace {
            static template = xml`<div t-att-dir="direction"><span t-esc="state.busy"/><div t-ref="messages" style="height: 120px; overflow-y: auto" t-on-scroll="updateScroll"><div t-foreach="state.detail?.messages || []" t-as="message" t-key="message.id" t-att-data-message-id="message.id" style="height: 40px" t-esc="message.id"/></div></div>`;
            setup() { super.setup(); this.direction = direction; }
            async call(model, method, args, kwargs = {}) {
                if (method === "bootstrap") return {session: {employee_id: 1, employee: "Agent"}};
                if (method === "workspace_customer_inbox") return {items: [{id: 1, group_key: "test", streams: [{id: 1}]}], has_more: false};
                if (method === "contact_search") return {contacts: []};
                if (method === "workspace_detail" && args[0][0] === 1) return {...detail(1), messages: kwargs.after_id ? [] : detail(1).messages};
                if (["workspace_detail", "workspace_channel"].includes(method)) return new Promise(resolve => { resolveDetail = resolve; });
            }
        }
        const workspace = await mountWithCleanup(ScrollHarness);
        const element = workspace.messagesRef.el;
        const atLatest = () => Math.abs(element.scrollHeight - element.clientHeight - element.scrollTop) < 2;
        expect(element.scrollHeight > element.clientHeight).toBe(true);
        expect(atLatest()).toBe(true);
        for (const [id, channel] of [[2, false], [3, true]]) {
            element.scrollTop = 0;
            workspace.updateScroll();
            const pending = workspace.select(id, channel);
            await animationFrame();
            expect(element.scrollTop).toBe(0);
            resolveDetail(detail(id));
            await pending;
            await animationFrame();
            expect(workspace.state.detail.id).toBe(id);
            expect(atLatest()).toBe(true);
            element.scrollTop = 80;
            workspace.state.reply = "Draft";
            await animationFrame();
            expect(element.scrollTop).toBe(80);
        }
    });
}
