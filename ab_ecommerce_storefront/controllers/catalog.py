import hashlib
import re

from lxml import etree, html

from odoo import http
from odoo.http import request

from .shop import AbEcommerceStorefrontShop


class AbStorefrontCatalog(AbEcommerceStorefrontShop):
    def _ab_catalog_scope(self):
        website = request.website
        cart = request.cart
        scope = (
            request.env.cr.dbname, website.id, website.company_id.id,
            website.warehouse_id.id, request.env.uid, request.env.lang,
            request.pricelist.id, request.fiscal_position.id,
            cart.partner_shipping_id.id if cart else False,
            cart.warehouse_id.id if cart else False,
        )
        return hashlib.sha256(repr(scope).encode()).hexdigest()

    @http.route()
    def shop(self, page=0, category=None, search='', min_price=0.0, max_price=0.0, tags='', **post):
        partial = request.httprequest.headers.get("X-Ab-Catalog-Page") == "1"
        known_header = request.httprequest.headers.get("X-Ab-Catalog-Known", "")
        if partial and (
            len(known_header) > 5000
            or not re.fullmatch(r"(?:[a-f0-9]{24}(?:,[a-f0-9]{24})*)?", known_header)
        ):
            return request.make_json_response({"reload": True}, status=400)
        response = super().shop(
            page=page, category=category, search=search, min_price=min_price,
            max_price=max_price, tags=tags, **post,
        )
        if not getattr(response, "qcontext", None) or response.status_code != 200:
            return response
        scope = self._ab_catalog_scope()
        if partial and request.httprequest.headers.get("X-Ab-Catalog-Scope") != scope:
            return request.make_json_response(
                {"reload": True}, headers={"Cache-Control": "private, no-store"},
            )
        if partial:
            response.template = "ab_ecommerce_storefront.catalog_page"
        response.flatten()
        document = html.fromstring(response.get_data(as_text=True))
        grids = document.xpath("//*[@id='products_grid']")
        if not grids:
            return response
        grid = grids[0]
        grid.set("data-ab-catalog-scope", scope)
        known = set(known_header.split(',')) if partial else set()
        for element in grid.xpath(".//*[@data-ab-catalog-static]"):
            key = hashlib.sha256(etree.tostring(element, method="html", with_tail=False)).hexdigest()[:24]
            element.set("data-ab-catalog-key", key)
            if key in known:
                for child in list(element):
                    element.remove(child)
                element.text = None
                element.set("data-ab-catalog-cached", "1")
        if partial:
            return request.make_json_response({
                "scope": scope,
                "grid": etree.tostring(grid, method="html", encoding="unicode", with_tail=False),
            }, headers={"Cache-Control": "private, no-store", "Vary": "X-Ab-Catalog-Page"})
        response.set_data(etree.tostring(document, method="html", encoding="unicode", doctype="<!DOCTYPE html>"))
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = ", ".join(filter(None, (response.headers.get("Vary"), "X-Ab-Catalog-Page")))
        return response
