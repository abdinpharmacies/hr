const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const handlers = new Map();
let mobile = true;
let destination = null;
class Element {
    constructor(key, value, selector = '') {
        this.dataset = key ? {[key]: value} : {};
        this.attributes = key ? {['data-' + key.replace(/[A-Z]/g, x => '-' + x.toLowerCase())]: value} : {};
        this.href = 'https://shop.test/ar/shop';
        this.selector = selector;
        this.active = false;
        this.classList = {toggle: (name, value) => {if (name === 'active') this.active = value;}};
    }
    hasAttribute(name) {return Object.hasOwn(this.attributes, name);}
    setAttribute(name, value) {this.attributes[name] = value;}
    removeAttribute(name) {delete this.attributes[name];}
    closest(selector) {return selector === 'a[href]' || selector === this.selector ? this : null;}
    matches(selector) {return this.selector === '.ab-storefront-filter-clear' && selector.includes(this.selector);}
    querySelector() {return null;}
}
const needs = ['', 'acne_treatment', 'sun_protection'].map(value => new Element('abNeed', value));
const save = new Element(null, null, '.ab-storefront-filter-apply');
const clear = new Element(null, null, '.ab-storefront-filter-clear');
const brand = new Element('abBrand', '8');
const elements = [...needs, save, clear, brand];
const dialog = {
    contains: el => elements.includes(el),
    querySelectorAll: selector => selector === '[data-ab-need]' ? needs : selector === '[data-ab-brand]' ? [brand] : [],
    querySelector: () => null,
    addEventListener: (name, handler) => handlers.set(name, handler),
};
const document = {
    readyState: 'complete',
    querySelector: () => dialog,
    addEventListener: (name, handler) => handlers.set(name, handler),
};
const window = {
    location: {href: 'https://shop.test/ar/shop/page/3?need=acne_treatment&brand=8&deal=discount&search=cream', origin: 'https://shop.test', assign: url => destination = new URL(url)},
    matchMedia: () => ({matches: mobile}),
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/src/js/shop_filter_draft.js'), 'utf8'), {document, window, Element, URL});
function click(target) {
    const event = {target, preventDefault() {this.prevented = true;}, stopPropagation() {}};
    handlers.get('click')(event);
    return event;
}
handlers.get('show.bs.offcanvas')();
assert.equal(needs[1].active, true);
assert.equal(needs[1].attributes['aria-current'], 'true');
assert.equal(needs[2].active, false);
click(needs[2]);
assert.equal(destination, null);
assert.equal(needs[2].active, true);
assert.equal(needs[1].active, false);
click(save);
assert.equal(destination.searchParams.get('need'), 'sun_protection');
assert.equal(destination.searchParams.get('brand'), '8');
assert.equal(destination.searchParams.get('deal'), 'discount');
assert.equal(destination.searchParams.get('search'), 'cream');
assert.equal(destination.pathname, '/ar/shop');
handlers.get('hidden.bs.offcanvas')();
assert.equal(needs[1].active, true);
assert.equal(needs[2].active, false);
handlers.get('show.bs.offcanvas')();
click(needs[0]);
click(save);
assert.equal(destination.searchParams.has('need'), false);
assert.equal(destination.searchParams.get('brand'), '8');
handlers.get('show.bs.offcanvas')();
click(clear);
click(save);
assert.equal(destination.searchParams.has('need'), false);
assert.equal(destination.searchParams.has('brand'), false);
assert.equal(destination.searchParams.has('deal'), false);
assert.equal(destination.searchParams.get('search'), 'cream');
mobile = false;
assert.equal(click(needs[2]).prevented, undefined);
console.log('PASS: 6 scenarios — URL selection, draft/save with pagination reset and filter preservation, cancel, all needs, clear filters, desktop navigation.');
