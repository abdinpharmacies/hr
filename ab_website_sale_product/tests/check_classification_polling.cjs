const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../static/src/js/product_classification.js"), "utf8")
    .replace(/^import .*;$/gm, "")
    .replace("export class ProductClassification", "class ProductClassification");
const context = {
    Component: class {}, registry: { category: () => ({ add() {} }) },
    _t: value => value, clearTimeout() {}, setTimeout() {},
};
vm.createContext(context);
vm.runInContext(source + "\nglobalThis.Classification = ProductClassification;", context);

async function checkStaleResponse(rejectOlder) {
    const pending = [];
    const page = Object.create(context.Classification.prototype);
    Object.assign(page, {
        alive: true, refreshSequence: 0, runId: 1,
        state: { scope: "website", websiteId: 1, error: "", loading: true },
        orm: { call: () => new Promise((resolve, reject) => pending.push({ resolve, reject })) },
    });
    const older = page.refresh();
    const newer = page.refresh();
    pending[1].resolve({ website_id: 1, run: { id: 2, processed: 250 } });
    await newer;
    if (rejectOlder) pending[0].reject(new Error("Older network request failed"));
    else pending[0].resolve({ website_id: 1, run: { id: 1, processed: 0 } });
    await older;
    assert.equal(page.runId, 2);
    assert.equal(page.state.data.run.processed, 250);
    assert.equal(page.state.error, "");
    assert.equal(page.state.loading, false);
}

Promise.all([checkStaleResponse(false), checkStaleResponse(true)])
    .then(() => console.log("2 polling race checks passed"))
    .catch(error => { console.error(error); process.exitCode = 1; });
