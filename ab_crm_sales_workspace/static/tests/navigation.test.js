import {expect, test} from "@odoo/hoot";
import {SalesWorkspace} from "@ab_crm_sales_workspace/workspace";

function workspace() {
    return Object.assign(Object.create(SalesWorkspace.prototype), {
        navigationVersion: 0, drafts: new Map(), selectedStreams: new Map(),
        state: {token: 'session', detail: {id: 1, provider: 'telegram', can_send: true},
            reply: 'draft', attachments: [], replyTo: null, inbox: []},
        stopRecording() {}, clearSearch() {},
    });
}

function deferred() {
    let resolve;
    const promise = new Promise(done => { resolve = done; });
    return {promise, resolve};
}

test('rapid channel switches ignore superseded replies and preserve the original draft', async () => {
    const view = workspace();
    const first = deferred();
    const second = deferred();
    view.call = (model, method, args) => args[1] === 2 ? first.promise : second.promise;
    const pendingFirst = view.select(2, true);
    expect(view.state.detail.id).toBe(1);
    expect(view.state.navigating).toBe(true);
    expect(Boolean(view.sendDisabledReason)).toBe(true);
    const pendingSecond = view.select(3, true);
    second.resolve({id: 3, provider: 'telegram'});
    await pendingSecond;
    first.resolve({id: 2, provider: 'whatsapp'});
    await pendingFirst;
    expect(view.state.detail.id).toBe(3);
    expect(view.state.navigating).toBe(false);
    expect(view.drafts.get(1).reply).toBe('draft');
});

test('session replacement invalidates pending channel navigation', async () => {
    const view = workspace();
    const pending = deferred();
    view.call = () => pending.promise;
    const selection = view.select(2, true);
    view.state.token = 'replacement';
    pending.resolve({id: 2, provider: 'whatsapp'});
    await selection;
    expect(view.state.detail.id).toBe(1);
    expect(view.state.navigating).toBe(false);
});

test('background refresh and read acknowledgements skip channel transitions', async () => {
    const view = workspace();
    view.state.navigating = true;
    let calls = 0;
    view.call = () => { calls++; };
    await view.refresh();
    await view.acknowledgeVisible();
    expect(calls).toBe(0);
});


test('failed channel loading clears the indicator and keeps a retryable draft', async () => {
    const view = workspace();
    view.feedback = {report() {}};
    view.call = async () => { throw new Error('offline'); };
    await view.select(2, true);
    expect(view.state.navigating).toBe(false);
    expect(view.state.detail.id).toBe(1);
    expect(view.state.reply).toBe('draft');
    view.call = async () => ({id: 2, provider: 'whatsapp'});
    await view.select(2, true);
    expect(view.state.detail.id).toBe(2);
});


test('history actions cannot supersede a pending channel switch or strand its spinner', async () => {
    const view = workspace();
    const pending = deferred();
    view.call = () => pending.promise;
    const selection = view.select(2, true);
    const version = view.navigationVersion;
    await view.olderMessages();
    await view.openQuote({id: 1, available: true});
    await view.jumpLatest();
    expect(view.navigationVersion).toBe(version);
    pending.resolve({id: 2, provider: 'whatsapp'});
    await selection;
    expect(view.state.detail.id).toBe(2);
    expect(view.state.navigating).toBe(false);
});

test('shared channel timelines open directly and remember the approved destination', async () => {
    const view = workspace();
    view.lastChannelStreams = new Map([['website', 2]]);
    const selections = [];
    view.select = async (...args) => selections.push(args);
    const group = {provider: 'website', streams: [{id: 2, shared_timeline: true}, {id: 3, shared_timeline: true}]};
    await view.openChannel(group);
    expect(selections).toEqual([[2, true]]);
    view.lastChannelStreams.set('website', 99);
    await view.openChannel(group);
    expect(selections.at(-1)).toEqual([3, true]);
});

test('active shared timelines and separate accounts retain their destination chooser', () => {
    const view = workspace();
    view.select = () => { throw new Error('Unexpected navigation'); };
    view.openChannel({provider: 'telegram', streams: [{id: 1}, {id: 2}]});
    expect(view.state.channelChooser).toBe('telegram');
    view.state.detail.provider = 'website';
    view.openChannel({provider: 'website', streams: [{id: 2, shared_timeline: true}, {id: 3, shared_timeline: true}]});
    expect(view.state.channelChooser).toBe('website');
});
