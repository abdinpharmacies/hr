from werkzeug import urls

from odoo import fields
from odoo.http import Controller, request, route


class AbEcommerceLegacyRoutes(Controller):
    """Keep useful links from the reference storefront working after cutover."""

    @route(
        "/products/<string:legacy_slug>/<int:eplus_item_id>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        readonly=True,
    )
    def legacy_product(self, legacy_slug, eplus_item_id, **kwargs):
        # The bridge field is intentionally internal-only. Elevate only the
        # stable-ID lookup, then return to the visitor before checking website
        # publication and generating the destination URL.
        bridge_domain = fields.Domain(
            "ab_product_id.eplus_serial",
            "=",
            eplus_item_id,
        )
        product_sudo = request.env["product.template"].sudo().search(
            bridge_domain,
            limit=1,
        )
        product = product_sudo.with_user(request.env.user).filtered_domain(
            request.website.sale_product_domain()
        )
        if product:
            return request.redirect(product._get_product_url(), code=301)

        query = self._normalise_category_label(legacy_slug)
        return request.redirect(self._shop_search_url(query), code=302)

    @route(
        "/products/<string:legacy_category>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
        readonly=True,
    )
    def legacy_category(self, legacy_category, **kwargs):
        subcategory = kwargs.get("subCategoryId")
        category = self._find_category(subcategory, legacy_category)
        if category:
            category_slug = request.env["ir.http"]._slug(category)
            return request.redirect(f"/shop/category/{category_slug}", code=301)

        query = self._normalise_category_label(subcategory or legacy_category)
        return request.redirect(self._shop_search_url(query), code=302)

    @staticmethod
    def _find_category(*legacy_values):
        Category = request.env["product.public.category"]
        base_domain = request.website.website_domain() & fields.Domain(
            "has_published_products",
            "=",
            True,
        )
        for legacy_value in legacy_values:
            for candidate in AbEcommerceLegacyRoutes._category_candidates(legacy_value):
                category = Category.search(
                    base_domain & fields.Domain("name", "=ilike", candidate),
                    limit=1,
                )
                if category:
                    return category
        return Category

    @staticmethod
    def _category_candidates(value):
        value = (value or "").strip()
        if not value:
            return []

        candidates = [value]
        readable = value.replace("_-_", " - ").replace("_", " ")
        simplified = readable.replace(" - ", " ").replace("-", " ")
        for candidate in (readable, simplified):
            candidate = " ".join(candidate.split())
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        return candidates

    @staticmethod
    def _normalise_category_label(value):
        candidates = AbEcommerceLegacyRoutes._category_candidates(value)
        return candidates[-1] if candidates else ""

    @staticmethod
    def _shop_search_url(query):
        return f"/shop?{urls.urlencode({'search': query})}" if query else "/shop"
