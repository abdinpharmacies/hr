const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require(process.env.AB_JSDOM_PATH || 'jsdom');
const root = path.resolve(__dirname, '..');
const fixtureDirectory = process.env.AB_BRANCH_FIXTURES;
assert.ok(fixtureDirectory, 'AB_BRANCH_FIXTURES must contain rendered ar.html and en.html');
const source = fs.readFileSync(path.join(root, 'static/src/js/branches.js'), 'utf8')
    .replace(/^import .*;\n/gm, '').replace('export class AbBranchLocator', 'class AbBranchLocator');
let checks = 0;
const check = (condition, label) => { assert.ok(condition, label); checks++; };

async function createLocator(language, mobile = false, failAssets = false) {
    const dom = new JSDOM(fs.readFileSync(path.join(fixtureDirectory, `${language}.html`), 'utf8'), {
        url: 'https://example.test/branches', runScripts: 'outside-only', pretendToBeVisual: true,
    });
    const w = dom.window;
    w.matchMedia = () => Object.assign(new w.EventTarget(), { matches: mobile });
    w.ResizeObserver = class { observe() {} disconnect() {} };
    w.HTMLDialogElement.prototype.show = function () { this.open = true; this.dataset.mode = 'side'; };
    w.HTMLDialogElement.prototype.showModal = function () { this.open = true; this.dataset.mode = 'sheet'; };
    w.HTMLDialogElement.prototype.close = function () { this.open = false; };
    const translations = language === 'ar' ? JSON.parse(fs.readFileSync(path.join(fixtureDirectory, 'ar_terms.json'), 'utf8')) : {};
    w._t = (value, ...args) => {
        let translated = translations[value] || value;
        for (const arg of args) translated = translated.replace('%s', arg);
        return translated;
    };
    w.Interaction = class {};
    w.registry = { category: () => ({ add() {} }) };
    w.loadCSS = async () => {};
    w.loadJS = async (url) => {
        if (failAssets) throw Error('Simulated offline assets');
        w.eval(fs.readFileSync(path.join(root, url.replace('/ab_ecommerce_storefront/', '')), 'utf8'));
    };
    w.eval(`${source}\nwindow.Locator = AbBranchLocator;`);
    const locator = new w.Locator();
    locator.el = w.document.querySelector('[data-ab-branches]');
    locator.start();
    for (let i = 0; i < 20 && !locator.map && !locator.el.classList.contains('is-map-unavailable'); i++) {
        await new Promise(resolve => setImmediate(resolve));
    }
    return { locator, w, close() { locator.destroy(); dom.window.close(); } };
}

(async () => {
    for (const language of ['ar', 'en']) {
        const { locator: l, w, close } = await createLocator(language);
        check(l.branches.length === 42, `${language}: 42 branches`);
        check(new Set(l.branches.map(b => b.region)).size === 9, `${language}: nine regions`);
        check(Boolean(l.map && l.clusters), `${language}: real Leaflet and markercluster initialize`);
        check(l.clusters.getLayers().length === 42, `${language}: all map markers present`);
        check(l.branches.every(b => b.marker.options.icon.options.html.querySelector('img')), `${language}: branded markers`);
        l.region.value = 'cairo'; l.filter();
        check(l.visible.length === 4 && l.clusters.getLayers().length === 4, `${language}: governorate filters cards and map`);
        l.region.value = ''; l.search.value = 'Kawthar'; l.filter();
        check(l.visible.length === 2, `${language}: English search`);
        if (language === 'ar') {
            l.search.value = 'الأقصر'; l.filter();
            check(l.visible.length === 0, 'Arabic unmatched area');
            l.search.value = 'الكوثر'; l.filter();
            check(l.visible.length === 2, 'Arabic branch search');
            l.search.value = 'اسوان'; l.filter();
            check(l.visible.filter(b => b.region === 'aswan').length === 3, 'Arabic normalization');
        }
        l.search.value = 'no-such-branch'; l.filter();
        check(!l.el.querySelector('[data-branch-empty]').hidden && l.clusters.getLayers().length === 0, `${language}: empty state`);
        l.search.value = ''; l.filter();
        const branch = l.branches[0];
        l.selectBranch(branch);
        check(l.profile.open && l.profile.dataset.mode === 'side', `${language}: desktop side profile`);
        check(l.el.querySelector('.ab-branches-results').inert, `${language}: covered list cannot receive focus`);
        check(l.profile.querySelector('[data-profile-address]').textContent === branch.address, `${language}: correct profile address`);
        check(l.profile.querySelector('[data-profile-directions]').href.endsWith(branch.coords.join(',')), `${language}: exact navigation coordinates`);
        check(w.location.hash.includes(branch.id), `${language}: shareable branch link`);
        w.document.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Escape' }));
        check(!l.profile.open && !w.location.hash, `${language}: Escape closes profile`);
        check(!l.el.querySelector('.ab-branches-results').inert, `${language}: closing restores list access`);
        w.location.hash = '#branch=cairo-heliopolis'; l.openHash();
        check(l.selected.id === 'cairo-heliopolis', `${language}: deep link selects branch`);
        l.region.value = 'sohag'; l.filter();
        check(!l.profile.open && l.visible.length === 15, `${language}: filter closes excluded branch`);
        Object.defineProperty(w, 'isSecureContext', { configurable: true, value: false });
        l.locate();
        check(!l.status.hidden && l.status.textContent.includes('HTTPS'), `${language}: insecure location has useful feedback`);
        Object.defineProperty(w, 'isSecureContext', { value: true });
        w.navigator.geolocation = { getCurrentPosition(success) { success({ coords: { latitude: 30.1082222, longitude: 31.3372222 } }); } };
        l.locate();
        check(l.selected.id === 'cairo-heliopolis' && l.branches[0].distance === 0, `${language}: nearest branch sorted correctly`);
        check(l.list.firstElementChild.dataset.branchId === 'cairo-heliopolis', `${language}: nearby order reflected in DOM`);
        w.navigator.geolocation = { getCurrentPosition(success, error) { error({ code: 1 }); } };
        l.locate();
        check(!l.el.querySelector('[data-branch-near]').disabled && !l.status.hidden, `${language}: permission denial resets control`);
        close();
        check(!w.document?.body?.classList.contains('ab-branch-sheet-open'), `${language}: cleanup`);
    }
    const mobile = await createLocator('ar', true);
    mobile.locator.selectBranch(mobile.locator.branches[0]);
    check(mobile.locator.profile.dataset.mode === 'sheet', 'Mobile opens modal bottom sheet');
    check(mobile.w.document.body.classList.contains('ab-branch-sheet-open'), 'Mobile locks background scrolling');
    mobile.locator.closeProfile();
    check(!mobile.w.document.body.classList.contains('ab-branch-sheet-open'), 'Mobile restores scrolling');
    mobile.locator.setView('list');
    check(mobile.locator.workspace.dataset.view === 'list', 'Mobile list switch');
    mobile.close();
    const offline = await createLocator('en', false, true);
    check(offline.locator.el.classList.contains('is-map-unavailable'), 'Map load failure falls back to list');
    check(offline.locator.workspace.dataset.view === 'list' && offline.locator.visible.length === 42, 'Offline retains all branch data');
    offline.locator.selectBranch(offline.locator.branches[0]);
    check(offline.locator.profile.open, 'Profiles still work when map fails');
    offline.close();
    console.log(`${checks} branch interaction assertions passed (JSDOM; visual layout is not simulated).`);
})().catch(error => { console.error(error); process.exitCode = 1; });
