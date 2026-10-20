from unittest.mock import patch

from lxml import html
from werkzeug.test import EnvironBuilder

from odoo import fields
from odoo.exceptions import AccessError
from odoo.http import Request, Response, root
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase
from odoo.addons.website_sale.tests.common import MockRequest

from ..controllers.catalog import AbStorefrontCatalog


@tagged("post_install", "-at_install")
class TestStorefrontCatalogCache(TransactionCase):
    def setUp(self):
        super().setUp()
        self.website = self.env.ref("website.default_website")
        self.public = self.website.with_user(self.website.user_id).with_context(
            website_id=self.website.id, lang="en_US", allowed_company_ids=self.website.company_id.ids,
        )
        self.env.registry.clear_cache()

    def test_category_cache_reused_without_queries(self):
        self.public._ab_storefront_category_rows()
        before = self.cr.sql_log_count
        self.public._ab_storefront_category_rows()
        self.assertEqual(self.cr.sql_log_count, before)

    def test_category_name_and_order_invalidated(self):
        before = self.public._ab_storefront_category_rows()
        self.assertTrue(before)
        category = self.env["product.public.category"].browse(before[0][0])
        category.write({"name": "Catalog cache renamed", "sequence": -1000})
        after = self.public._ab_storefront_category_rows()
        self.assertEqual(after[0][0], category.id)
        self.assertEqual(after[0][3], "Catalog cache renamed")

    def test_publication_changes_category_visibility(self):
        category = self.env["product.public.category"].create({"name": "Cache publication", "website_id": self.website.id})
        product = self.env["product.template"].create({
            "name": "Cache publication product", "sale_ok": True, "is_published": True,
            "website_id": self.website.id, "public_categ_ids": [fields.Command.set(category.ids)],
        })
        self.assertIn(category.id, [row[0] for row in self.public._ab_storefront_category_rows()])
        product.is_published = False
        self.assertNotIn(category.id, [row[0] for row in self.public._ab_storefront_category_rows()])

    def test_website_and_user_isolation(self):
        other = self.env["website"].create({"name": "Catalog other website", "company_id": self.website.company_id.id})
        category = self.env["product.public.category"].create({"name": "Other website category", "website_id": other.id})
        self.env["product.template"].create({
            "name": "Other website product", "sale_ok": True, "is_published": True,
            "website_id": other.id, "public_categ_ids": [fields.Command.set(category.ids)],
        })
        self.assertNotIn(category.id, [row[0] for row in self.public._ab_storefront_category_rows()])
        with self.assertRaises(AccessError):
            category.with_user(self.website.user_id).write({"name": "Forbidden"})

    def test_language_cache_isolation(self):
        english = self.public._ab_storefront_category_rows()
        arabic = self.public.with_context(lang="ar_001")._ab_storefront_category_rows()
        self.assertEqual({row[0] for row in english}, {row[0] for row in arabic})
        self.assertNotEqual({row[0]: row[3] for row in english}, {row[0]: row[3] for row in arabic})
        self.assertEqual(english, self.public._ab_storefront_category_rows())

    def test_category_translation_editor_invalidates_cache(self):
        arabic = self.public.with_context(lang="ar_001")
        before = arabic._ab_storefront_category_rows()
        category = self.env["product.public.category"].browse(before[0][0])
        category.update_field_translations("name", {"ar_001": "قسم اختبار الكاش"})
        after = dict((row[0], row[3]) for row in arabic._ab_storefront_category_rows())
        self.assertEqual(after[category.id], "قسم اختبار الكاش")

    def test_context_scope_tracks_customer_pricelist_and_warehouse(self):
        controller = AbStorefrontCatalog()
        with MockRequest(self.public.env, website=self.public) as req:
            original = controller._ab_catalog_scope()
            pricelist = self.env["product.pricelist"].create({"name": "Catalog scope pricelist"})
            req.pricelist = pricelist
            changed = controller._ab_catalog_scope()
            self.assertNotEqual(original, changed)
            req.env = self.env
            self.assertNotEqual(changed, controller._ab_catalog_scope())
            warehouse = self.env["stock.warehouse"].create({
                "name": "Catalog scope warehouse", "code": "CSC", "company_id": self.website.company_id.id,
            })
            before_warehouse = controller._ab_catalog_scope()
            self.website.warehouse_id = warehouse
            self.assertNotEqual(before_warehouse, controller._ab_catalog_scope())

    def test_uncommitted_rows_do_not_enter_shared_cache(self):
        before = self.public._ab_storefront_category_rows()
        category = self.env["product.public.category"].browse(before[0][0])
        with self.assertRaises(ValueError), self.cr.savepoint():
            category.name = "Uncommitted category"
            with patch.object(type(self.public), "_ab_storefront_category_rows_cached") as cached:
                self.assertIn("Uncommitted category", [row[3] for row in self.public._ab_storefront_category_rows()])
                cached.assert_not_called()
            raise ValueError("rollback")
        self.assertEqual(before, self.public._ab_storefront_category_rows())

    def render(self, page=0, headers=None, params=None):
        params = params or {}
        path = "/shop" if not page else f"/shop/page/{page}"
        env = self.public.env
        with MockRequest(env, website=self.public, path=path, context=env.context, routing=False) as req:
            req.httprequest = EnvironBuilder(path=path, base_url="http://localhost", headers=headers).get_request()
            req.httprequest.app = root
            req.params = params.copy()
            req.session["force_website_id"] = False
            req.session.sid = "0" * 64
            req.is_frontend = True
            req.is_frontend_multilang = True
            req.debug = ""
            req.csrf_token = lambda *args, **kwargs: "catalog-test-token"
            req.render = lambda template, qcontext=None, **kwargs: Response(template=template, qcontext=qcontext, uid=env.uid)
            req.make_response = lambda *args, **kwargs: Request.make_response(req, *args, **kwargs)
            req.make_json_response = lambda *args, **kwargs: Request.make_json_response(req, *args, **kwargs)
            env["ir.http"].routing_map()
            root.get_db_router.return_value.bind.return_value.build.return_value = path
            return AbStorefrontCatalog.shop.__wrapped__(AbStorefrontCatalog(), page=page, **params)

    def test_ssr_and_live_batch_are_equivalent(self):
        response = self.render()
        document = html.fromstring(response.get_data())
        grid = document.xpath("//*[@id='products_grid']")[0]
        self.assertTrue(grid.xpath(".//input[@name='product_template_id']"))
        headers = {"X-Ab-Catalog-Page": "1", "X-Ab-Catalog-Scope": grid.get("data-ab-catalog-scope")}
        partial = self.render(headers=headers)
        self.assertIn("no-store", partial.headers["Cache-Control"])
        fresh = html.fromstring(partial.get_json()["grid"])
        for expression in (".//input[@name='product_template_id']/@value", ".//*[contains(@class,'ab-storefront-product-price')]//text()"):
            self.assertEqual(grid.xpath(expression), fresh.xpath(expression))

    def test_only_static_content_is_omitted_on_cache_hit(self):
        document = html.fromstring(self.render().get_data())
        scope = document.xpath("//*[@id='products_grid']/@data-ab-catalog-scope")[0]
        keys = document.xpath("//*[@data-ab-catalog-key]/@data-ab-catalog-key")
        data = self.render(headers={"X-Ab-Catalog-Page": "1", "X-Ab-Catalog-Scope": scope, "X-Ab-Catalog-Known": ','.join(keys)}).get_json()
        grid = html.fromstring(data["grid"])
        self.assertEqual(len(keys), len(grid.xpath("//*[@data-ab-catalog-cached]")))
        self.assertTrue(grid.xpath("//*[contains(@class,'ab-storefront-sale-price')]/text()"))
        self.assertTrue(grid.xpath("//input[@name='csrf_token']/@value"))

    def test_forged_context_and_invalid_cache_headers(self):
        mismatch = self.render(headers={"X-Ab-Catalog-Page": "1", "X-Ab-Catalog-Scope": "another customer"})
        self.assertEqual(mismatch.get_json(), {"reload": True})
        invalid = self.render(headers={"X-Ab-Catalog-Page": "1", "X-Ab-Catalog-Known": "invalid"})
        self.assertEqual(invalid.status_code, 400)

    def test_pagination_and_offers_stay_live(self):
        first = html.fromstring(self.render().get_data())
        second = html.fromstring(self.render(page=2).get_data())
        expression = "//*[@id='products_grid']//input[@name='product_template_id']/@value"
        self.assertNotEqual(first.xpath(expression), second.xpath(expression))
        response = self.render(params={"deal": "discount"})
        self.assertEqual(response.status_code, 200)
        for product in response.qcontext["products"]:
            price = response.qcontext["get_product_prices"](product)
            self.assertTrue(price.get("ab_offer") or price.get("base_price", 0) > price["price_reduce"])

    def test_live_prices_and_availability_are_not_cached(self):
        product = self.env["product.template"].create({
            "name": "Catalog freshness fixture", "sale_ok": True, "is_published": True,
            "website_id": self.website.id, "list_price": 17,
        })
        params = {"search": product.name}
        initial = html.fromstring(self.render(params=params).get_data(as_text=True))
        headers = {
            "X-Ab-Catalog-Page": "1",
            "X-Ab-Catalog-Scope": initial.xpath("//*[@id='products_grid']/@data-ab-catalog-scope")[0],
            "X-Ab-Catalog-Known": ','.join(initial.xpath("//*[@data-ab-catalog-key]/@data-ab-catalog-key")),
        }
        product.list_price = 29
        with patch.object(type(self.env["product.product"]), "_is_sold_out", return_value=True):
            refreshed = html.fromstring(self.render(params=params, headers=headers).get_json()["grid"])
        price_path = "//*[contains(@class,'ab-storefront-sale-price')]//text()"
        self.assertNotEqual(initial.xpath(price_path), refreshed.xpath(price_path))
        self.assertTrue(refreshed.xpath("//*[contains(@class,'ab-storefront-product-card-unavailable')]"))
        self.assertFalse(refreshed.xpath("//input[@name='add_qty']"))


@tagged("post_install", "-at_install")
class TestStorefrontCatalogBrowser(HttpCase):
    def test_background_refresh_releases_loading_state(self):
        self.browser_js('/ar/shop', """
            (async () => {
                const assert = (condition, message) => { if (!condition) throw new Error(message); };
                const now = Date.now;
                const fetchPage = window.fetch;
                let offset = 0;
                const requests = [];
                const wait = async (condition) => {
                    const end = now() + 25000;
                    while (!condition()) {
                        if (now() > end) throw new Error('Catalog refresh timeout');
                        await new Promise(resolve => setTimeout(resolve, 50));
                    }
                };
                const idle = () => !document.querySelector('#products_grid[inert], #products_grid[aria-busy="true"], #products_grid.ab-storefront-results-loading');
                window.fetch = (url, options) => {
                    if (!options?.headers?.['X-Ab-Catalog-Page']) return fetchPage(url, options);
                    return new Promise((resolve, reject) => {
                        requests.push({ resolve, reject, url, options });
                        options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
                    });
                };
                Date.now = () => now() + offset;
                try {
                    const originalGrid = document.querySelector('#products_grid');
                    const originalUrl = location.href;
                    offset = 2000;
                    window.dispatchEvent(new Event('focus'));
                    assert(requests.length === 0, 'Fresh catalog was fetched again on focus');
                    offset = 31000;
                    document.dispatchEvent(new Event('visibilitychange'));
                    window.dispatchEvent(new Event('focus'));
                    await wait(() => requests.length === 1);
                    assert(!originalGrid.hasAttribute('inert'), 'Background refresh blocked the catalog');
                    assert(!originalGrid.classList.contains('ab-storefront-results-loading'), 'Background refresh displayed navigation progress');
                    requests[0].reject(new TypeError('Simulated offline background refresh'));
                    await wait(idle);
                    assert(location.href === originalUrl && originalGrid.isConnected, 'Background failure navigated away');
                    window.dispatchEvent(new Event('focus'));
                    assert(requests.length === 1, 'Failed refresh retried immediately');
                    offset = 62000;
                    window.dispatchEvent(new Event('focus'));
                    await wait(() => requests.length === 2);
                    const quantity = originalGrid.querySelector('[name="add_qty"]');
                    const productId = quantity?.closest('form').querySelector('[name="product_id"]').value;
                    if (quantity) quantity.value = '2';
                    const request = requests[1];
                    fetchPage(request.url, request.options).then(request.resolve, request.reject);
                    await wait(() => !originalGrid.isConnected && idle());
                    if (productId) {
                        const form = [...document.querySelectorAll('#products_grid form')].find(form => form.querySelector('[name="product_id"]')?.value === productId);
                        assert(form.querySelector('[name="add_qty"]').value === '2', 'Background refresh discarded an in-flight quantity edit');
                    }
                    const next = [...document.querySelectorAll('#o_wsale_pager a[href]')].find(link => /\\/page\\/2(?:\\?|$)/.test(link.href));
                    assert(next, 'Second page link missing');
                    next.click();
                    await wait(() => requests.length === 3);
                    assert(document.querySelector('#products_grid[inert]'), 'Foreground navigation did not lock its pending grid');
                    window.dispatchEvent(new Event('pagehide'));
                    await wait(idle);
                    assert(requests[2].options.signal.aborted, 'Leaving the page did not abort its request');
                    assert(location.href === originalUrl, 'Cancelled pagination changed history');
                    console.log('test successful');
                } finally {
                    Date.now = now;
                    window.fetch = fetchPage;
                }
            })().catch(error => console.error(error));
        """, ready="document.readyState === 'complete' && !!sessionStorage.getItem('ab_storefront_catalog_v1')", timeout=120)

    def test_pagination_reuses_static_data_and_refreshes_commerce(self):
        self.browser_js('/ar/shop', """
            (async () => {
                const assert = (condition, message) => { if (!condition) throw new Error(message); };
                const wait = async (condition) => {
                    const end = Date.now() + 25000;
                    while (!condition()) {
                        if (Date.now() > end) throw new Error('Catalog update timeout');
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                };
                const ids = () => [...document.querySelectorAll('#products_grid input[name="product_template_id"]')].map(input => input.value).join(',');
                const original = ids();
                const firstUrl = location.href;
                const navigationCount = performance.getEntriesByType('navigation').length;
                const seen = [];
                const fetchPage = window.fetch;
                window.fetch = async (...args) => {
                    const response = await fetchPage(...args);
                    if (args[1]?.headers?.['X-Ab-Catalog-Page']) {
                        seen.push(await response.clone().json());
                    }
                    return response;
                };
                const next = [...document.querySelectorAll('#o_wsale_pager a[href]')].find(link => /\\/page\\/2(?:\\?|$)/.test(link.href));
                assert(next, 'Second page link missing');
                next.click();
                await wait(() => ids() !== original && !document.querySelector('#products_grid[inert]'));
                assert(seen.length === 1, 'Pagination must use one batch request');
                assert(performance.getEntriesByType('navigation').length === navigationCount, 'Pagination reloaded document');
                history.back();
                await wait(() => location.href === firstUrl && ids() === original && !document.querySelector('#products_grid[inert]'));
                assert(seen.length === 2, 'Back navigation must revalidate once');
                assert(seen[1].grid.includes('data-ab-catalog-cached'), 'Visited static content was retransmitted');
                assert(!document.querySelector('[data-ab-catalog-cached]'), 'Cached static content was not restored');
                assert(document.querySelector('#products_grid .ab-storefront-sale-price')?.textContent.trim(), 'Fresh price missing');
                const saved = JSON.parse(sessionStorage.getItem('ab_storefront_catalog_v1'));
                assert(saved.entries.every(([, value]) => !value.includes('csrf_token') && !value.includes('ab-storefront-sale-price')), 'Commerce data entered static cache');
                const quantity = document.querySelector('#products_grid input[name="add_qty"]');
                const chosenProduct = quantity?.closest('form').querySelector('[name="product_id"]').value;
                if (quantity) quantity.value = '3';
                document.dispatchEvent(new CustomEvent('ab-storefront:commerce-context-changed'));
                await wait(() => seen.length === 3 && !document.querySelector('#products_grid[inert]'));
                if (chosenProduct) {
                    const card = [...document.querySelectorAll('#products_grid form')].find(form => form.querySelector('[name="product_id"]')?.value === chosenProduct);
                    assert(card.querySelector('[name="add_qty"]').value === '3', 'Refreshing commerce discarded the chosen quantity');
                    card.querySelector('[data-ab-card-quantity="increase"]').click();
                    assert(card.querySelector('[name="add_qty"]').value === '4', 'Product interactions were not restarted');
                }
                console.log('test successful');
            })().catch(error => { console.error(error); });
        """, ready="document.readyState === 'complete' && !!sessionStorage.getItem('ab_storefront_catalog_v1')", timeout=120)
