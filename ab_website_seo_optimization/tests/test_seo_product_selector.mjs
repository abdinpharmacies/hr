import fs from 'node:fs';
import assert from 'node:assert/strict';
const source = fs.readFileSync(new URL('../static/src/js/seo_product_selector.js', import.meta.url), 'utf8')
    .replace(/^import .*;\n/gm, '').replace('export class ', 'class ');
let services;
class Many2OneField {
    get m2oProps() {
        return { update: (value) => this.updated.push(value), domain: () => [['active', '=', true]] };
    }
}
class ConfirmationDialog {}
class SelectCreateDialog {}
const registry = { category: () => ({ add() {} }) };
const Selector = new Function('Many2OneField', 'useService', 'registry', 'buildM2OFieldDescription', '_t', 'ConfirmationDialog', 'SelectCreateDialog', source + '\nreturn SeoProductSelector;')(
    Many2OneField, (name) => services[name], registry, (component) => ({ component }), (value) => value, ConfirmationDialog, SelectCreateDialog);
function selector(action) {
    const dialogs = [], actions = [], calls = [];
    services = {
        orm: { call: async (...args) => { calls.push(args); return action; }, read: async () => [{ id: 22, display_name: 'New product' }] },
        dialog: { add: (component, props) => dialogs.push({ component, props }) },
        action: { doAction: async (value) => actions.push(value) },
    };
    const field = new Selector();
    field.props = { name: 'product_template_id', record: { data: {}, resId: false }, context: { ab_seo_website_id: 3 } };
    field.updated = [];
    field.setup();
    return { field, dialogs, actions, calls };
}
const existingAction = { res_id: 7, res_model: 'ab.product.seo', type: 'ir.actions.act_window' };
let test = selector(false);
await test.field.selectProduct({ id: 22, display_name: 'New product' });
assert.equal(test.field.updated.length, 1);
assert.equal(test.dialogs.length, 0);
test = selector(existingAction);
await test.field.selectProduct({ id: 21, display_name: 'Prepared product' });
assert.equal(test.field.updated.length, 0);
assert.equal(test.dialogs[0].component, ConfirmationDialog);
assert.equal(test.calls[0][3].context.ab_seo_website_id, 3);
await test.dialogs[0].props.confirm();
assert.deepEqual(test.actions, [existingAction]);
test = selector(existingAction);
await test.field.selectProduct({ id: 21 });
test.dialogs[0].props.cancel();
assert.equal(test.dialogs[1].component, SelectCreateDialog);
assert.equal(test.dialogs[1].props.context.search_default_ab_without_seo_content, 1);
assert.equal(test.dialogs[1].props.noCreate, true);
assert.equal(test.field.updated.length, 0);
test = selector(existingAction);
await test.field.selectProduct({ id: 21 });
test.dialogs[0].props.dismiss();
assert.equal(test.dialogs.length, 1);
assert.equal(test.actions.length, 0);
test = selector(existingAction);
test.field.props.record.resId = 7;
await test.field.selectProduct({ id: 21 });
assert.equal(test.field.updated.length, 1);
assert.equal(test.dialogs.length, 0);
test = selector(false);
await test.field.selectProduct(false);
assert.equal(test.calls.length, 0);
assert.deepEqual(test.field.updated, [false]);
test = selector(false);
test.field.openProductList();
await test.dialogs[0].props.onSelected([22]);
assert.equal(test.field.updated[0].id, 22);
test = selector(false);
let resolve;
test.field.orm.call = () => new Promise((done) => { resolve = done; });
const pending = test.field.selectProduct({ id: 21 });
await test.field.selectProduct(false);
resolve(existingAction);
await pending;
assert.equal(test.dialogs.length, 0);
console.log('8 selector behavior checks passed');
