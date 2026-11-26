import {expect, test} from "@odoo/hoot";
import {animationFrame} from "@odoo/hoot-mock";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

function workspace() {
    const view = Object.create(SalesWorkspace.prototype);
    Object.assign(view, {navigationVersion: 1, contactsLoaded: true, state: {
        token: 'test', detail: {id: 1, message_cursor: 1, messages: [{id: 1, body: 'Old'}]},
        inbox: [], reply: 'Unsent', attachments: [{name: 'Unsent attachment'}], phone: '',
    }});
    return view;
}

test('active chat renders before a blocked inbox and coalesces duplicate events', async () => {
    const view = workspace();
    let releaseInbox;
    let releaseActive;
    let activeCalls = 0;
    let inboxCalls = 0;
    view.loadCustomerInbox = () => {
        inboxCalls++;
        return new Promise(resolve => { releaseInbox = () => resolve({items: [], has_more: false}); });
    };
    view.call = async (model, method) => {
        expect(method).toBe('workspace_updates');
        activeCalls++;
        if (activeCalls === 1) await new Promise(resolve => { releaseActive = resolve; });
        return {id: 1, owned: true, message_cursor: 2, messages: [{id: 2, body: 'New'}], changed_messages: []};
    };
    const first = view.refresh();
    const second = view.refresh();
    view.refresh();
    expect(activeCalls).toBe(1);
    expect(inboxCalls).toBe(1);
    releaseActive();
    await animationFrame();
    expect(view.state.detail.messages.map(message => message.id)).toEqual([1, 2]);
    expect(activeCalls).toBe(2);
    expect(view.state.reply).toBe('Unsent');
    releaseInbox();
    await animationFrame();
    expect(inboxCalls).toBe(2);
    releaseInbox();
    await Promise.all([first, second]);
});

test('incremental refresh drains bursts across rendering frames and ignores stale targets', async () => {
    const view = workspace();
    const cursors = [];
    view.call = async (model, method, args, values) => {
        cursors.push(values.after_id);
        return {id: 1, owned: true, message_cursor: values.after_id + 50,
            has_more_updates: cursors.length < 3,
            messages: Array.from({length: 50}, (_, index) => ({id: values.after_id + index + 1}))};
    };
    const pending = view.refreshActive();
    await animationFrame();
    await animationFrame();
    await animationFrame();
    await pending;
    expect(cursors).toEqual([1, 51, 101]);
    expect(view.state.detail.messages).toHaveLength(151);
    let release;
    view.call = () => new Promise(resolve => { release = resolve; });
    const stale = view.refreshActive();
    view.navigationVersion++;
    view.state.detail = {id: 2, messages: []};
    release({id: 1, owned: true, messages: [{id: 999}]});
    await stale;
    expect(view.state.detail).toEqual({id: 2, messages: []});
});

test('visible refresh caps work independently of loaded history', () => {
    const view = workspace();
    view.state.detail.messages = Array.from({length: 1000}, (_, index) => ({id: index + 1}));
    expect(view.visibleMessageIds()).toHaveLength(50);
    expect(view.visibleMessageIds()[0]).toBe(951);
});

test('a completed submission cannot clear a replacement employee composer', async () => {
    const view = workspace();
    Object.defineProperty(view, 'sendDisabledReason', {value: ''});
    view.run = callback => callback();
    view.call = () => new Promise(resolve => { view.finishSubmission = resolve; });
    view.clearAttachments = () => { throw new Error('Replacement draft was cleared'); };
    const send = view.send();
    view.state.token = 'replacement';
    view.state.reply = 'Replacement draft';
    view.navigationVersion++;
    view.finishSubmission(1);
    await send;
    expect(view.state.reply).toBe('Replacement draft');
    expect(view.state.attachments).toEqual([{name: 'Unsent attachment'}]);
});

test('reply submission waits for its existing read request without duplicating sends', async () => {
    const view = workspace();
    Object.defineProperty(view, 'sendDisabledReason', {value: ''});
    view.run = callback => callback();
    view.clearAttachments = () => { view.state.attachments = []; };
    view.refresh = async () => {};
    let finishRead;
    view.readPromise = new Promise(resolve => { finishRead = resolve; });
    let calls = 0;
    view.call = async () => { calls++; return 1; };
    const submitted = view.send();
    expect(calls).toBe(0);
    finishRead(true);
    await submitted;
    expect(calls).toBe(1);
    expect(view.state.reply).toBe('');
});

test('a stalled read request cannot prevent a queued reply indefinitely', async () => {
    const view = workspace();
    Object.defineProperty(view, 'sendDisabledReason', {value: ''});
    view.run = callback => callback();
    view.clearAttachments = () => { view.state.attachments = []; };
    view.refresh = async () => {};
    view.readPromise = new Promise(() => {});
    let calls = 0;
    view.call = async () => { calls++; return 1; };
    await view.send();
    expect(calls).toBe(1);
    expect(view.state.reply).toBe('');
});
