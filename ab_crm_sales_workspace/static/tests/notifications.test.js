import {expect, test} from "@odoo/hoot";
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

test("popup grouping keeps all conversations and isolates unlinked senders", () => {
    const groups = groupNotificationItems([entry(1, "customer:8", [11]), entry(2, "customer:8", [21, 22]),
        entry(3, "conversation:3", [31]), entry(4, "conversation:4", [41])]);
    expect(groups).toHaveLength(3);
    expect(groups[0].count).toBe(3);
    expect(groups[0].conversations.map(item => item.conversation_id)).toEqual([1, 2]);
});

test("popup pages group together and dismissal captures exact IDs while arrivals remain", async () => {
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
    const events = [];
    let receiver;
    patchWithCleanup(window, {BroadcastChannel: class {constructor() { receiver = this; } postMessage(value) { broadcasts.push(value); }}});
    const acknowledged = [];
    let first = [11];
    let second = [21];
    let release;
    const orm = {async call(model, method, args, values) {
        if (method === "acknowledge_alert") {
            acknowledged.push([values.conversation_id, [...values.message_ids]]);
            if (values.conversation_id === 1) {
                await new Promise(resolve => { release = resolve; });
                first = first.filter(id => !values.message_ids.includes(id));
            } else second = second.filter(id => !values.message_ids.includes(id));
            return true;
        }
        return values.after_id ? {items: second.length ? [entry(2, "customer:8", second)] : [], cursor: 2, has_more: false}
            : {items: first.length ? [entry(1, "customer:8", first)] : [], cursor: 1, has_more: true};
    }};
    const service = registry.category("services").get("ab_chatter_session").start({bus: {trigger(event) { events.push(event); }}},
        {orm, notification, ab_chatter_feedback: env.services.ab_chatter_feedback, action: {async doAction() { throw new Error("Navigation failed"); }}});
    service.set({token: "test", employee_id: 8});
    await animationFrame();
    expect(alerts()).toHaveLength(1);
    expect(alerts()[0].sticky).toBe(true);
    expect(alerts()[0].buttons).toHaveLength(2);
    await alerts()[0].buttons[0].onClick();
    expect(alerts()).toHaveLength(1);
    expect(acknowledged).toHaveLength(0);
    const dismiss = alerts()[0].close();
    first = [11, 12];
    release();
    await dismiss;
    await animationFrame();
    await service.poll();
    expect(acknowledged).toEqual([[1, [11]], [2, [21]]]);
    expect(alerts()).toHaveLength(1);
    expect(alerts()[0].message).toInclude("1 pending messages");
    service.focusHandler = (item, token) => service.acknowledge(item, token);
    const opening = alerts()[0].buttons[0].onClick();
    release();
    await opening;
    await animationFrame();
    await service.poll();
    expect(alerts()).toHaveLength(0);
    expect(acknowledged.at(-1)).toEqual([1, [12]]);
    expect(broadcasts.length > 0).toBe(true);
    const count = events.length;
    receiver.onmessage({data: {employee: 99, company: user.activeCompany.id}});
    receiver.onmessage({data: {employee: 8, company: -1}});
    expect(events.length).toBe(count);
    receiver.onmessage({data: {employee: 8, company: user.activeCompany.id}});
    expect(events.at(-1)).toBe("AB_CHATTER_UNREAD");
    service.clear();
});

test("hidden, unfocused, search and history views never advance reads", async () => {
    const calls = [];
    const workspace = {state: {loggedIn: true}, call: (...args) => calls.push(args)};
    for (const state of [{visibilityState: "hidden", focus: true}, {visibilityState: "visible", focus: false},
        {visibilityState: "visible", focus: true, searchOpen: true}, {visibilityState: "visible", focus: true, historyContext: true}]) {
        patchWithCleanup(document, {get visibilityState() { return state.visibilityState; }, hasFocus: () => state.focus});
        Object.assign(workspace.state, {searchOpen: !!state.searchOpen, historyContext: !!state.historyContext});
        await SalesWorkspace.prototype.acknowledgeVisible.call(workspace);
    }
    expect(calls).toHaveLength(0);
});


test("loading older history suspends automatic read advancement", async () => {
    const workspace = {state: {detail: {id: 1, messages: [{id: 20}]}}, navigationVersion: 0,
        run: callback => callback(), call: async () => ({id: 1, has_older: false, messages: [{id: 10}]})};
    await SalesWorkspace.prototype.olderMessages.call(workspace);
    expect(workspace.state.historyContext).toBe(true);
    expect(workspace.state.detail.messages.map(message => message.id)).toEqual([10, 20]);
});
