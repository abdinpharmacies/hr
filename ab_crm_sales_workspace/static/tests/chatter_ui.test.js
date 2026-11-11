import {expect, test, getFixture} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {Component, useRef, useState, xml} from "@odoo/owl";
import {contains, makeMockEnv, mountWithCleanup, patchWithCleanup} from "@web/../tests/web_test_helpers";
import {MainComponentsContainer} from "@web/core/main_components_container";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {SavedReplies} from "@ab_crm_sales_workspace/templates";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";
import {MessageActions, MessageMedia, formatMediaSize} from "@ab_crm_sales_workspace/message";

defineMailModels();

async function templates(items = [{id: 1, name: "Greeting", body: "Hello {{customer}}"}]) {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    let savedId = 2;
    const calls = [];
    env.services.dialog.add(SavedReplies, {conversation: {id: 1, name: "Customer", phone: "123", provider: "telegram"},
        insert: text => calls.push(["insert", text]), call: async (model, method, args, kwargs) => {
            calls.push([method, args, kwargs]);
            if (method === "save_template") {
                const id = kwargs.template_id || savedId++;
                items = items.filter(item => item.id !== id);
                if (kwargs.active) items.push({id, name: args[1], body: args[2]});
                return {items, can_manage: true, selected_id: kwargs.active ? id : false};
            }
            return {items, can_manage: true};
        }});
    await animationFrame();
    await animationFrame();
    return calls;
}

test("saved replies select first, search, create once, refresh selection and archive", async () => {
    const calls = await templates();
    expect(".ab_template_preview").toHaveText("Hello Customer");
    await contains(".ab_template_list input").edit("missing");
    expect(".ab_template_item").toHaveCount(0);
    await contains(".ab_template_list input").edit("");
    await contains("button:contains(New saved reply)").click();
    await contains(".ab_template_editor input:first").edit("New greeting");
    await contains(".ab_template_editor textarea").edit("New body");
    await contains("button:contains(Save template)").click();
    await contains(".ab_template_editor textarea").edit("Updated body");
    await contains("button:contains(Save template)").click();
    expect(calls.filter(call => call[0] === "save_template").map(call => call[2].template_id)).toEqual([false, 2]);
    await contains("button:contains(Refresh)").click();
    expect(".ab_template_item.active").toHaveText("New greeting\nUpdated body");
    await contains(".ab_template_editor textarea").edit("Discard on archive");
    await contains("button:contains(Archive template)").click();
    await contains("button:contains(Discard):last").click();
    expect(calls.filter(call => call[0] === "save_template").at(-1)[1][2]).toBe("Updated body");
    expect(".ab_template_item.active").toHaveCount(0);
    expect(".ab_template_editor textarea").toHaveValue("");
});

test("unsaved reply edits offer keep or discard, including dialog dismissal", async () => {
    await templates();
    await contains(".ab_template_editor textarea").edit("Unsaved");
    await contains("button:contains(Refresh)").click();
    expect(".o_dialog:last").toHaveText(/Discard your unsaved/);
    await contains("button:contains(Keep editing)").click();
    expect(".ab_template_editor textarea").toHaveValue("Unsaved");
    await contains(".ab_template_dialog .btn-close").click();
    await contains("button:contains(Keep editing)").click();
    expect(".ab_template_dialog").toHaveCount(1);
    await contains("button:contains(Refresh)").click();
    await contains("button:contains(Discard):last").click();
    expect(".ab_template_editor textarea").toHaveValue("Hello {{customer}}");
});

test("saved reply insertion requires nonblank values and never sends", async () => {
    const calls = await templates([{id: 1, name: "Parameter", body: "Hello {{value}}"}]);
    expect("button:contains(Insert into composer)[disabled]").toHaveCount(1);
    await contains(".ab_template_editor input:last").edit("   ");
    expect("button:contains(Insert into composer)[disabled]").toHaveCount(1);
    await contains(".ab_template_editor input:last").edit("World");
    await contains("button:contains(Insert into composer)").click();
    expect(calls.map(call => call[0])).toEqual(["workspace_templates", "insert"]);
    expect(calls.at(-1)[1]).toBe("Hello World");
});

class MenuHarness extends Component {
    static template = xml`<article tabindex="-1"><MessageActions message="message" reply="action" react="action" copy="action" preview="action" retry="action"/><p>Message text</p><a href="#">Link</a><textarea/><div contenteditable="plaintext-only">Editable</div></article>`;
    static components = {MessageActions};
    static props = ["*"];
    message = {body: "Message text", media: [], actions: {reply: {enabled: true}, react: {enabled: true}, reactions: ["👍", "❤", "👎"]}};
    action() {}
}

test("pointer and keyboard menus stay in viewport, restore focus and respect native exceptions", async () => {
    await mountWithCleanup(MenuHarness);
    const article = getFixture().querySelector("article");
    const context = (element, options = {}) => element.dispatchEvent(new MouseEvent("contextmenu", {bubbles: true, cancelable: true, clientX: window.innerWidth - 1, clientY: window.innerHeight - 1, ...options}));
    expect(context(article.querySelector("textarea"))).toBe(true);
    expect(context(article.querySelector("a"))).toBe(true);
    expect(context(article.querySelector("[contenteditable]"))).toBe(true);
    expect(context(article, {shiftKey: true})).toBe(true);
    const selection = window.getSelection();
    const range = document.createRange(); range.selectNodeContents(article.querySelector("p")); selection.addRange(range);
    expect(context(article)).toBe(true); selection.removeAllRanges();
    expect(context(article)).toBe(false);
    await animationFrame();
    const bounds = getFixture().querySelector(".ab_context_menu").getBoundingClientRect();
    expect(bounds.right <= window.innerWidth).toBe(true); expect(bounds.bottom <= window.innerHeight).toBe(true);
    await contains(".ab_context_menu button:first").press("Escape");
    expect(article).toBeFocused();
    article.style.direction = "rtl";
    article.dispatchEvent(new KeyboardEvent("keydown", {bubbles: true, cancelable: true, key: "F10", shiftKey: true}));
    await animationFrame();
    expect(".ab_context_menu").toHaveCount(1);
    await contains(".ab_context_menu button:first").press("Escape");
    expect(article).toBeFocused();
    await contains(".ab_message_menu").click();
    await contains("textarea").click();
    expect(".ab_context_menu").toHaveCount(0);
});

test("all twelve composer emojis replace selection and restore caret", async () => {
    const input = document.createElement("textarea"); getFixture().append(input);
    for (const emoji of ["😀", "😂", "😍", "👍", "🙏", "🔥", "✅", "🎉", "❤️", "😢", "😮", "👏"]) {
        input.value = "abc"; input.setSelectionRange(1, 2);
        const workspace = {replyRef: {el: input}, state: {reply: "abc", emoji: true}};
        SalesWorkspace.prototype.insertEmoji.call(workspace, emoji);
        input.value = workspace.state.reply;
        SalesWorkspace.prototype.restoreComposerCaret.call(workspace);
        expect(workspace.state.reply).toBe(`a${emoji}c`);
        expect(input.selectionStart).toBe(1 + emoji.length);
        expect(input.selectionEnd).toBe(input.selectionStart);
        expect(workspace.state.emoji).toBe(false);
    }
});

test("search pages newest first, ignores stale responses and clearing preserves timeline and draft", async () => {
    let resolve;
    const timeline = [{id: 80}];
    const workspace = {state: {detail: {id: 1, messages: timeline}, searchQuery: "needle", searchResults: [], reply: "Draft"}, navigationVersion: 1,
        call: async (model, method, args, kwargs) => { expect(kwargs.query).toBe("needle"); return {messages: [{id: 2}, {id: 4}], has_older: true}; }};
    await SalesWorkspace.prototype.searchMessages.call(workspace);
    expect(workspace.state.searchResults.map(row => row.id)).toEqual([4, 2]);
    workspace.call = async (model, method, args, kwargs) => { expect(kwargs.before_id).toBe(2); return {messages: [{id: 1}], has_older: false}; };
    await SalesWorkspace.prototype.searchMessages.call(workspace, true);
    expect(workspace.state.searchResults.map(row => row.id)).toEqual([4, 2, 1]);
    workspace.call = () => new Promise(done => { resolve = done; });
    const pending = SalesWorkspace.prototype.searchMessages.call(workspace);
    SalesWorkspace.prototype.clearSearch.call(workspace);
    resolve({messages: [{id: 999}], has_older: false}); await pending;
    expect(workspace.state.searchResults).toEqual([]);
    expect(workspace.state.detail.messages).toBe(timeline);
    expect(workspace.state.reply).toBe("Draft");
});

test("search context navigation fetches one context without changing draft or unread boundary", async () => {
    const workspace = {state: {detail: {id: 1, messages: [{id: 99}]}, reply: "Draft", firstUnread: 10}, navigationVersion: 0,
        run: async action => action(), call: async (model, method) => { expect(method).toBe("workspace_reply"); return {available: true, messages: [{id: 10}], has_older: true}; }};
    await SalesWorkspace.prototype.openQuote.call(workspace, {id: 10, available: true});
    expect(workspace.state.detail.messages).toEqual([{id: 10}]);
    expect(workspace.state.firstUnread).toBe(10);
    expect(workspace.state.reply).toBe("Draft");
    expect(workspace.pendingQuoteFocus.id).toBe(10);
});

test("file sizes are formatted and private thumbnail URLs are released", async () => {
    expect(formatMediaSize(1024)).toBe("1.0 KB");
    expect(formatMediaSize(1048576)).toBe("1.0 MB");
    let intersect;
    patchWithCleanup(window, {IntersectionObserver: class { constructor(callback) { intersect = callback; } observe() {} disconnect() {} }});
    const revoke = URL.revokeObjectURL.bind(URL);
    patchWithCleanup(URL, {revokeObjectURL: url => { expect.step("released"); revoke(url); }});
    class MediaHarness extends Component {
        static template = xml`<MessageMedia t-if="state.visible" media="media" call="call" preview="preview"/>`;
        static components = {MessageMedia};
        static props = ["*"];
        setup() { this.state = useState({visible: true}); }
        media = {id: 1, kind: "image", state: "ready", name: "Private.png", size: 1024};
        async call(model, method) { expect.step(method); return {data: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jvXcAAAAASUVORK5CYII=", mimetype: "image/png"}; }
        preview() {}
    }
    const component = await mountWithCleanup(MediaHarness);
    expect.verifySteps([]);
    intersect([{isIntersecting: true}]); await animationFrame();
    expect.verifySteps(["download"]);
    expect(".ab_thumbnail img").toHaveCount(1);
    component.state.visible = false; await animationFrame();
    expect.verifySteps(["released"]);
});

test("thumbnail completion after unmount creates no object URL", async () => {
    let intersect, resolve;
    patchWithCleanup(window, {IntersectionObserver: class { constructor(callback) { intersect = callback; } observe() {} disconnect() {} }});
    patchWithCleanup(URL, {createObjectURL: () => { throw new Error("Unexpected URL after unmount"); }});
    class PendingMedia extends Component {
        static template = xml`<MessageMedia t-if="state.visible" media="media" call="call" preview="preview"/>`;
        static components = {MessageMedia};
        static props = ["*"];
        setup() { this.state = useState({visible: true}); }
        media = {id: 2, kind: "image", state: "ready", name: "Pending.png"};
        call() { return new Promise(done => { resolve = done; }); }
        preview() {}
    }
    const component = await mountWithCleanup(PendingMedia);
    intersect([{isIntersecting: true}]);
    component.state.visible = false; await animationFrame();
    resolve({data: "eA==", mimetype: "image/png"}); await animationFrame();
    expect(".ab_thumbnail").toHaveCount(0);
});

test("unauthorized template editor stays read only and load failure can refresh", async () => {
    const env = await makeMockEnv();
    await mountWithCleanup(MainComponentsContainer);
    let failed = true;
    env.services.dialog.add(SavedReplies, {conversation: {id: 1, name: "Customer", phone: "123"}, insert() {}, call: async () => {
        if (failed) throw new Error("Load failed");
        return {items: [{id: 1, name: "Reply", body: "Read only"}], can_manage: false};
    }});
    await animationFrame(); await animationFrame();
    expect(".ab_template_dialog [role=alert]").toHaveCount(0);
    expect(".o_notification:contains(Load failed)").toHaveCount(1);
    failed = false;
    await contains("button:contains(Refresh)").click();
    expect(".ab_template_preview").toHaveText("Read only");
    expect("button:contains(New saved reply)").toHaveCount(0);
    expect("button:contains(Save template)").toHaveCount(0);
    expect(".ab_template_editor textarea").toHaveCount(0);
});

test("jump to latest ignores stale polling epoch and preserves the captured unread marker", async () => {
    const workspace = {navigationVersion: 4, state: {detail: {id: 1}, firstUnread: 2, historyContext: true},
        run: async action => action(), call: async () => ({id: 1, messages: [{id: 99}], unread_count: 0})};
    await SalesWorkspace.prototype.jumpLatest.call(workspace);
    expect(workspace.navigationVersion).toBe(5);
    expect(workspace.state.firstUnread).toBe(2);
    expect(workspace.state.historyContext).toBe(false);
    expect(workspace.resetScroll).toBe(true);
});
