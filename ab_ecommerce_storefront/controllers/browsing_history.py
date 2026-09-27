from odoo import fields, http
from odoo.http import request

from odoo.addons.ab_ecommerce_storefront.models.browsing_history import (
    AB_BROWSING_HISTORY_LIMIT,
)


class AbStorefrontBrowsingHistory(http.Controller):
    def _history_model(self):
        return request.env["ab.ecommerce.browsing.history"]

    def _history_partner(self):
        if request.website.is_public_user():
            return False
        return self._history_model()._ab_history_partner(request.env.user)

    def _normalize_product_ids(self, product_ids):
        return self._history_model()._ab_normalize_product_ids(product_ids)

    def _available_products(self, product_ids, exclude_ids=None):
        product_ids = self._normalize_product_ids(product_ids)
        exclude_ids = set(self._normalize_product_ids(exclude_ids))
        if not product_ids:
            return request.env["product.template"]
        domain = request.website.sale_product_domain()
        domain &= fields.Domain("id", "in", product_ids)
        if exclude_ids:
            domain &= fields.Domain("id", "not in", list(exclude_ids))
        products = request.env["product.template"].with_context(bin_size=True).search(domain)
        products_by_id = {product.id: product for product in products}
        ordered_products = request.env["product.template"]
        for product_id in product_ids:
            product = products_by_id.get(product_id)
            if product:
                ordered_products |= product
        return ordered_products

    def _product_card_values(self, products):
        variants = request.env["product.product"].sudo().browse([
            variant_id
            for variant_id in products.mapped(lambda product: product._get_first_possible_variant_id())
            if variant_id
        ])
        variants_by_template = {
            variant.product_tmpl_id.id: variant
            for variant in variants
        }
        return {
            "products": products,
            "ab_history_prices": products._get_sales_prices(request.website) if products else {},
            "ab_history_variants": variants_by_template,
            "ab_history_wishlist_product_ids": set(
                request.env["product.wishlist"].current().product_id.ids
            ),
        }

    def _render_cards(self, products):
        if not products:
            return ""
        html = request.env["ir.ui.view"]._render_template(
            "ab_ecommerce_storefront.browsing_history_cards",
            self._product_card_values(products),
        )
        return str(html)

    @http.route("/my/browsing-history", type="http", auth="public", website=True, sitemap=False)
    def browsing_history_page(self, **kwargs):
        return request.render("ab_ecommerce_storefront.browsing_history_page", {
            "ab_history_limit": AB_BROWSING_HISTORY_LIMIT,
        })

    @http.route("/ab/storefront/browsing-history/cards", type="jsonrpc", auth="public", website=True)
    def browsing_history_cards(self, product_ids=None, limit=AB_BROWSING_HISTORY_LIMIT, exclude_ids=None, **kwargs):
        partner = self._history_partner()
        limit = min(max(int(limit or AB_BROWSING_HISTORY_LIMIT), 1), AB_BROWSING_HISTORY_LIMIT)
        if partner:
            source_ids = self._history_model()._ab_partner_product_ids(
                partner,
                request.website,
                limit=AB_BROWSING_HISTORY_LIMIT,
            )
        else:
            source_ids = self._normalize_product_ids(product_ids)
        products = self._available_products(source_ids, exclude_ids=exclude_ids)[:limit]
        return {
            "authenticated": bool(partner),
            "count": len(products),
            "product_ids": products.ids,
            "html": self._render_cards(products),
        }

    @http.route("/ab/storefront/browsing-history/record", type="jsonrpc", auth="public", website=True)
    def browsing_history_record(self, product_id=None, **kwargs):
        product_ids = self._normalize_product_ids([product_id])
        products = self._available_products(product_ids)
        if not products:
            return {"recorded": False, "authenticated": bool(self._history_partner())}
        partner = self._history_partner()
        if partner:
            self._history_model()._ab_record_view(partner, request.website, products[0])
        return {
            "recorded": True,
            "authenticated": bool(partner),
            "product_id": products[0].id,
        }

    @http.route("/ab/storefront/browsing-history/sync", type="jsonrpc", auth="public", website=True)
    def browsing_history_sync(self, product_ids=None, **kwargs):
        partner = self._history_partner()
        if not partner:
            return {"synced": False, "product_ids": []}
        products = self._available_products(product_ids)
        merged_ids = self._history_model()._ab_merge_product_ids(
            partner,
            request.website,
            products.ids,
        )
        return {
            "synced": True,
            "product_ids": merged_ids,
        }

    @http.route("/ab/storefront/browsing-history/clear", type="jsonrpc", auth="public", website=True)
    def browsing_history_clear(self, **kwargs):
        partner = self._history_partner()
        if partner:
            self._history_model()._ab_clear_partner_history(partner, request.website)
        return {
            "cleared": True,
            "authenticated": bool(partner),
        }

    @http.route("/ab/storefront/browsing-history/remove", type="jsonrpc", auth="public", website=True)
    def browsing_history_remove(self, product_id=None, **kwargs):
        product_ids = self._normalize_product_ids([product_id])
        products = self._available_products(product_ids)
        partner = self._history_partner()
        removed = False
        if partner and products:
            removed = self._history_model()._ab_remove_partner_product(
                partner,
                request.website,
                products[0],
            )
        return {
            "removed": bool(removed or product_ids),
            "authenticated": bool(partner),
            "product_id": product_ids[0] if product_ids else False,
        }
