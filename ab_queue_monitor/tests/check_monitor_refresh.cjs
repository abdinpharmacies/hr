const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

let Monitor;
let now = 100000;
let tick;
let unmount;
let removed = false;
let cleared = false;
const requests = [];
const document = {
    hidden: false,
    addEventListener() {},
    removeEventListener() { removed = true; },
};
const services = {
    orm: { call: () => new Promise((resolve, reject) => requests.push({ resolve, reject })) },
};
const source = fs.readFileSync(path.join(__dirname, "../static/src/monitor.js"), "utf8")
    .replace(/^import .*;\n/gm, "").replace("export class QueueMonitor", "class QueueMonitor");
vm.runInNewContext(source, {
    Component: class {}, Dialog: class {},
    registry: { category: () => ({ add: (key, value) => { Monitor = value; } }) },
    useService: name => services[name], useState: state => state,
    onWillStart() {}, onWillUnmount: callback => { unmount = callback; },
    setInterval: callback => { tick = callback; return 1; },
    clearInterval: () => { cleared = true; }, document,
    Date: { now: () => now }, _t: text => text,
    deserializeDateTime: value => value, formatDateTime: value => value,
});
const result = () => ({ rows: [], runner: {}, refreshed_at: "2026-10-06 10:00:00" });

(async () => {
    const monitor = new Monitor();
    monitor.props = { action: {} };
    monitor.setup();
    await new Promise(setImmediate);
    monitor.state.loading = false;
    tick();
    assert.equal(requests.length, 1);
    now += 40000;
    tick();
    assert.equal(requests.length, 1);
    requests[0].resolve(result());
    await new Promise(setImmediate);
    assert.equal(monitor.stale, false);
    document.hidden = true;
    now += 100000;
    tick();
    assert.equal(requests.length, 1);
    assert.equal(monitor.stale, true);
    document.hidden = false;
    monitor.state.autoRefresh = false;
    tick();
    assert.equal(requests.length, 1);
    monitor.state.autoRefresh = true;
    monitor.state.busy = true;
    tick();
    assert.equal(requests.length, 1);
    monitor.state.busy = false;
    tick();
    assert.equal(requests.length, 2);
    requests[1].reject({ data: { message: "offline" } });
    await new Promise(setImmediate);
    assert.equal(monitor.state.error, "offline");
    assert.equal(monitor.stale, true);
    now += 10000;
    tick();
    assert.equal(requests.length, 2);
    now += 20000;
    tick();
    assert.equal(requests.length, 3);
    requests[2].resolve(result());
    await new Promise(setImmediate);
    assert.equal(monitor.stale, false);
    assert.equal(monitor.state.error, "");
    const older = monitor.refresh();
    const newer = monitor.refresh();
    requests[4].resolve(result());
    await newer;
    requests[3].reject({ data: { message: "obsolete error" } });
    await older;
    assert.equal(monitor.state.error, "");
    unmount();
    assert.ok(cleared && removed);
    now += 100000;
    tick();
    assert.equal(requests.length, 5);
    console.log("PASS: refresh timing, overlap, hidden tab, disabled refresh, discovery pause, staleness, retry spacing, recovery, response ordering and cleanup");
})().catch(error => { console.error(error); process.exitCode = 1; });
