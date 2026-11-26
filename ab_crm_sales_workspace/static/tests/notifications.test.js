import {expect, test, getFixture} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {user} from "@web/core/user";
import {registry} from "@web/core/registry";
import {makeMockEnv, patchWithCleanup} from "@web/../tests/web_test_helpers";
import {groupNotificationItems} from "@ab_crm_sales_workspace/session_service";
import {defineMailModels} from "@mail/../tests/mail_test_helpers";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

defineMailModels();

const entry = (id, customer, messages) => ({alert_key: `employee:${id}`, customer_group_key: customer,
    conversation_id: id, name: "Customer", message_ids: messages, latest_message_id: messages.at(-1),
    count: messages.length, unread_count: messages.length, provider: "whatsapp", preview: "Message"});

test("popup grouping keeps exact chats separate for the same customer", () => {
    const groups = groupNotificationItems([entry(1, "customer:8", [11]), entry(2, "customer:8", [21, 22]),
        entry(3, "conversation:3", [31]), entry(4, "conversation:4", [41])]);
    expect(groups).toHaveLength(4);
    expect(groups[0].count).toBe(1);
    expect(groups[0].conversations.map(item => item.conversation_id)).toEqual([1]);
});

test("closing and failed navigation never acknowledge; opening captures only that target", async () => {
    const visible = new Map();
    let nextId = 0;
    const notification = {add(message, options) {
        const id = ++nextId;
        const close = () => {
            if (!visible.has(id)) return;
            visible.delete(id);
            return options.onClose?.();
        };
        visible.set(id, {message, ...options, close});
        return close;
    }};
    const alerts = () => [...visible.values()].filter(item => item.className === "ab_chatter_notification");
    patchWithCleanup(sessionStorage, {getItem: () => null, setItem() {}, removeItem() {}});
    const env = await makeMockEnv();
    const broadcasts = [];
    let receiver;
    patchWithCleanup(window, {BroadcastChannel: class {constructor() { receiver = this; } postMessage(value) { broadcasts.push(value); }}});
    const acknowledged = [];
    const target = {kind: "order", uuid: "target-one"};
    let first = [11];
    const one = () => ({...entry(1, "customer:8", first), alert_key: "order:one", website_target: target});
    const two = {...entry(1, "customer:8", [21]), alert_key: "order:two", website_target: {kind: "order", uuid: "target-two"}};
    const orm = {async call(model, method, args, values) {
        if (method === "acknowledge_alert") {
            acknowledged.push(values);
            first = first.filter(id => !values.message_ids.includes(id));
            return true;
        }
        return {items: [...(first.length ? [one()] : []), two], cursor: 1, has_more: false};
    }};
    const service = registry.category("services").get("ab_chatter_session").start({bus: {trigger() {}}},
        {orm, notification, ab_chatter_feedback: env.services.ab_chatter_feedback, action: {async doAction() { throw new Error("Navigation failed"); }}});
    service.set({token: "test", employee_id: 8});
    await animationFrame();
    expect(alerts()).toHaveLength(2);
    expect(alerts()[0].buttons).toHaveLength(1);
    await alerts()[0].buttons[0].onClick();
    expect(acknowledged).toHaveLength(0);
    alerts()[0].close();
    await service.poll();
    expect(acknowledged).toHaveLength(0);
    expect(alerts()).toHaveLength(1);
    first = [11, 12];
    await service.poll();
    expect(alerts()).toHaveLength(2);
    const opening = alerts().find(item => item.message === "You have 2 unread messages");
    service.focusHandler = (item, token) => service.acknowledge(item, token);
    await opening.buttons[0].onClick();
    await animationFrame();
    await service.poll();
    expect(acknowledged).toHaveLength(1);
    expect(acknowledged[0].message_ids).toEqual([11, 12]);
    expect(acknowledged[0].target).toEqual(target);
    expect(alerts()).toHaveLength(1);
    expect(broadcasts.length > 0).toBe(true);
    receiver.onmessage({data: {employee: 8, company: user.activeCompany.id}});
    service.clear();
});

test("hidden, unfocused and search views never advance reads while history views do", async () => {
    const calls = [];
    document.body.classList.remove("modal-open");
    const fixture = getFixture();
    fixture.innerHTML = '<div class="stream"><article data-message-id="20"></article></div>';
    const stream = fixture.querySelector(".stream");
    patchWithCleanup(stream, {getBoundingClientRect: () => ({top: 0, bottom: 100, left: 0, right: 100})});
    patchWithCleanup(stream.children[0], {getBoundingClientRect: () => ({top: 10, bottom: 90, left: 0, right: 80})});
    const view = {visibilityState: "visible", focus: true};
    patchWithCleanup(document, {get visibilityState() { return view.visibilityState; }, hasFocus: () => view.focus});
    const focusHandler = () => {};
    const workspace = {
        state: {loggedIn: true, token: "test", detail: {id: 1, unread_count: 1, messages: [{id: 20, direction: "in"}]}, firstUnread: 20, inbox: []},
        draftKey: id => id, selectedStream: () => null, acknowledged: new Map(), readVersion: 0, messagesRef: {el: stream}, focusHandler,
        acknowledgeRead: SalesWorkspace.prototype.acknowledgeRead,
        applyReadPosition: SalesWorkspace.prototype.applyReadPosition,
        chatterSession: {focusHandler, unreadChanged() {}},
        call: (...args) => calls.push(args),
    };
    for (const state of [{visibilityState: "hidden", focus: true}, {visibilityState: "visible", focus: false},
        {visibilityState: "visible", focus: true, searchOpen: true}]) {
        Object.assign(view, state);
        workspace.state.searchOpen = !!state.searchOpen;
        await SalesWorkspace.prototype.acknowledgeVisible.call(workspace);
    }
    expect(calls).toHaveLength(0);
    Object.assign(view, {visibilityState: "visible", focus: true});
    workspace.state.searchOpen = false;
    workspace.state.historyContext = true;
    await SalesWorkspace.prototype.acknowledgeVisible.call(workspace);
    expect(calls).toEqual([["ab_crm_conversation", "workspace_acknowledge", [[1], 20]]]);
    expect(workspace.state.firstUnread).toBe(false);
    expect(workspace.state.detail.unread_count).toBe(0);
});


test("loading older history suspends automatic read advancement", async () => {
    const workspace = {state: {detail: {id: 1, messages: [{id: 20}]}}, navigationVersion: 0,
        run: callback => callback(), call: async () => ({id: 1, has_older: false, messages: [{id: 10}]})};
    await SalesWorkspace.prototype.olderMessages.call(workspace);
    expect(workspace.state.historyContext).toBe(true);
    expect(workspace.state.detail.messages.map(message => message.id)).toEqual([10, 20]);
});

test("notification snapshots coalesce requests and discard replaced employee results", async () => {
    patchWithCleanup(sessionStorage, {getItem: () => null, setItem() {}, removeItem() {}});
    const env = await makeMockEnv();
    let release;
    let calls = 0;
    const added = [];
    const listeners = new Map();
    const subscriptions = new Map();
    const service = registry.category("services").get("ab_chatter_session").start({bus: {trigger() {}}}, {
        orm: {async call(model, method) {
            expect(method).toBe("notifications_v2");
            calls++;
            await new Promise(resolve => { release = resolve; });
            return {items: [entry(1, "customer:8", [11])], cursor: 11, has_more: false};
        }},
        notification: {add: (...values) => { added.push(values); return () => {}; }},
        ab_chatter_feedback: env.services.ab_chatter_feedback,
        action: {},
        bus_service: {subscribe: (name, callback) => subscriptions.set(name, callback),
            addEventListener: (name, callback) => listeners.set(name, callback)},
    });
    service.set({token: "old-employee", employee_id: 8});
    await animationFrame();
    await service.poll();
    await service.poll();
    expect(calls).toBe(1);
    expect(subscriptions.has("ab_chatter.invalidate")).toBe(true);
    expect(listeners.has("BUS:RECONNECT")).toBe(true);
    service.clear();
    release();
    await animationFrame();
    expect(added).toHaveLength(0);
    expect(service.current).toBe(null);
});

test('targeted invalidations replace only affected conversations and overflow reconciles all', async () => {
    patchWithCleanup(sessionStorage, {getItem: () => null, setItem() {}, removeItem() {}});
    const env = await makeMockEnv();
    const visible = new Map();
    const requests = [];
    let invalidate;
    let changed = false;
    const service = registry.category('services').get('ab_chatter_session').start({bus: {trigger() {}}}, {
        orm: {async call(model, method, args, values) {
            requests.push(values);
            return {items: values.conversation_ids ? [] : [entry(2, 'two', [22]), ...(changed ? [] : [entry(1, 'one', [11])])],
                cursor: 22, has_more: false};
        }},
        notification: {add(text, options) {
            const key = visible.size + Math.random();
            visible.set(key, options);
            return () => visible.delete(key);
        }},
        ab_chatter_feedback: env.services.ab_chatter_feedback, action: {},
        bus_service: {subscribe: (name, callback) => { invalidate = callback; }, addEventListener() {}},
    });
    service.set({token: 'targeted', employee_id: 8});
    await animationFrame();
    expect(visible.size).toBe(2);
    changed = true;
    invalidate({company_id: user.activeCompany.id, employee_id: 8, conversation_ids: [1], categories: ['unread']});
    await new Promise(resolve => setTimeout(resolve, 80));
    await animationFrame();
    expect(requests.at(-1).conversation_ids).toEqual([1]);
    expect(visible.size).toBe(1);
    invalidate({company_id: user.activeCompany.id, employee_id: 8, conversation_ids: [1], overflow: true});
    await new Promise(resolve => setTimeout(resolve, 80));
    await animationFrame();
    expect(requests.at(-1).conversation_ids).toBe(undefined);
    expect(visible.size).toBe(1);
    service.clear();
});
