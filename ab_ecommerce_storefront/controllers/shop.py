from odoo import fields, http
from odoo.http import request
from odoo.tools import SQL, float_round

from odoo.addons.website_sale.controllers.main import WebsiteSale


class AbEcommerceStorefrontShop(WebsiteSale):
    """Storefront shop refinements that keep Odoo's native /shop behavior."""

    @http.route(["/shop/offers", "/shop/offers/page/<int:page>"], type="http", auth="public", website=True, sitemap=False)
    def ab_storefront_offers(self, page=1, **kwargs):
        page = max(page, 1)
        path = "/shop/category" if page == 1 else f"/shop/category/page/{page}"
        return request.redirect(f"{path}?deal=discount", code=302)

    @http.route(["/shop/category", "/shop/category/page/<int:page>"], type="http", auth="public", website=True, sitemap=False)
    def ab_storefront_category_listing(self, page=0, **kwargs):
        return self.shop(page=page, **kwargs)

    def _get_shop_path(self, category=None, page=0):
        path = request.httprequest.path.rstrip("/")
        if not category and (path.endswith("/shop/category") or "/shop/category/page/" in path):
            return "/shop/category" + (f"/page/{page}" if page else "")
        return super()._get_shop_path(category, page)

    def _get_default_country(self, order_sudo=False, **kwargs):
        country = super()._get_default_country(order_sudo=order_sudo, **kwargs)
        return country or request.website.company_id.country_id

    def _get_mandatory_address_fields(self, country_sudo):
        fields = super()._get_mandatory_address_fields(country_sudo)
        fields.discard("zip")
        return fields

    def _get_mandatory_billing_address_fields(self, country_sudo):
        fields = super()._get_mandatory_billing_address_fields(country_sudo)
        fields.discard("email")
        return fields

    def _get_mandatory_delivery_address_fields(self, country_sudo):
        fields = super()._get_mandatory_delivery_address_fields(country_sudo)
        fields.discard("email")
        return fields

    def _get_additional_shop_values(self, values, **kwargs):
        result = super()._get_additional_shop_values(values, **kwargs)
        result.update(self._ab_storefront_price_range_values(values))
        need_key = request.params.get('need')
        result['ab_shop_need'] = request.env['product.tag'].search(
            fields.Domain('ab_shop_need_key', '=', need_key), limit=1
        ) if need_key else request.env['product.tag']
        result['ab_storefront_brands'] = self._ab_storefront_brands(values)
        result['ab_storefront_brand_id'] = self._ab_storefront_brand_id()
        deals = self._ab_storefront_deals()
        selected_deals = set(deals)
        result['ab_storefront_deals'] = deals
        result['ab_storefront_deal_toggles'] = {
            key: ','.join(deal for deal in ('discount', 'coupon', 'today')
                          if deal in (selected_deals ^ {key})) or None
            for key in ('discount', 'coupon', 'today')
        }
        result['ab_storefront_include_oos'] = request.params.get('include_oos') == '1'
        return result

    def _get_search_options(self, *args, **kwargs):
        options = super()._get_search_options(*args, **kwargs)
        options['ab_shop_need_key'] = request.params.get('need')
        options['ab_storefront_brand_id'] = self._ab_storefront_brand_id()
        options['ab_storefront_deals'] = self._ab_storefront_deals()
        return options

    def _shop_lookup_products(self, options, post, search, website):
        deals = self._ab_storefront_deals()
        if 'discount' in deals or 'today' in deals:
            request.env.cr.execute("SET LOCAL jit = off")
        fuzzy_search_term, _product_count, products = super()._shop_lookup_products(
            options, post, search, website
        )
        include_oos = request.params.get('include_oos') == '1'
        if deals:
            matching_ids = set()
            if 'coupon' in deals:
                matching_ids.update(products.filtered_domain(
                    website._ab_storefront_coupon_candidate_domain()
                ).ids)
        if 'discount' in deals or 'today' in deals:
            prices = products._get_sales_prices(website)
            matching_ids.update(product.id for product in products if (
                bool(prices[product.id].get('ab_offer'))
                or ('discount' in deals and prices[product.id].get('base_price', 0)
                    > prices[product.id]['price_reduce'])
            ))
        if deals:
            products = products.filtered(lambda product: product.id in matching_ids)
        if not include_oos:
            products = self._ab_storefront_available_products(products, website)
        return fuzzy_search_term, len(products), products

    def _ab_storefront_available_products(self, products, website):
        templates = products.sudo().with_context(active_test=False)
        eplus_templates = templates.search_fetch(
            fields.Domain("id", "in", templates.ids)
            & fields.Domain("ab_product_id", "!=", False)
            & fields.Domain("ab_product_id.is_service", "=", False),
            ["ab_product_id", "eplus_stock_shown_qty_value"],
        )
        sold_out_ids = set()
        source_ids = eplus_templates.mapped('ab_product_id').ids
        quantities = {}
        snapshots = request.env['ab_eplus_stock_snapshot'].sudo()
        if source_ids:
            rows = snapshots._read_group(
                [
                    ('product_id', 'in', source_ids),
                    ('active', '=', True),
                ],
                ['product_id'],
                ['itm_qty:sum'],
            )
            quantities.update({source.id: quantity for source, quantity in rows})
        for template in eplus_templates:
            if (
                template.eplus_stock_shown_qty_value <= 0
                or quantities.get(template.ab_product_id.id, 0) <= 0
            ):
                sold_out_ids.add(template.id)

        stock_limited = templates.search(
            fields.Domain("id", "in", (templates - eplus_templates).ids)
            & fields.Domain("is_storable", "=", True)
            & fields.Domain("allow_out_of_stock_order", "=", False)
        )
        scoped_templates = (eplus_templates | stock_limited).filtered(
            lambda template: template.id not in sold_out_ids
        )
        warehouse_id = website._ab_storefront_stock_warehouse_id()
        warehouse = request.env["stock.warehouse"].sudo().browse(warehouse_id).exists()
        cart = request.cart
        exclude_order = cart if cart and cart.website_id == website else None
        if not warehouse:
            sold_out_ids.update(scoped_templates.ids)
        else:
            scoped_templates.fetch(['type', 'uom_id'])
            services = scoped_templates.filtered(lambda template: template.type == 'service')
            sold_out_ids.update(services.ids)
            scoped_templates -= services
            for start in range(0, len(scoped_templates), 5000):
                batch = scoped_templates[start:start + 5000]
                variants = request.env['product.product'].sudo().with_context(
                    active_test=False,
                    warehouse_id=warehouse.id, allowed_company_ids=website.company_id.ids,
                ).search_fetch(
                    fields.Domain('product_tmpl_id', 'in', batch.ids), ['product_tmpl_id'],
                )
                first_variants = {}
                for variant in variants:
                    first_variants.setdefault(variant.product_tmpl_id.id, variant.id)
                variants = variants.browse(first_variants.values())
                quantities_by_variant = variants._compute_quantities_dict(
                    variants.env.context.get('lot_id'), variants.env.context.get('owner_id'),
                    variants.env.context.get('package_id'), variants.env.context.get('from_date'),
                    variants.env.context.get('to_date'),
                )
                held = request.env["ab_storefront_cart_hold"]._quantities(
                    variants, website.company_id, warehouse, exclude_order,
                )
                for template in batch:
                    variant_id = first_variants.get(template.id)
                    free_quantity = quantities_by_variant.get(variant_id, {}).get('free_qty', 0)
                    if free_quantity - held.get(variant_id, 0) <= 0:
                        sold_out_ids.add(template.id)
        return products.filtered(lambda product: product.id not in sold_out_ids)

    def _get_shop_domain(self, search, category, attribute_value_dict, search_in_description=True):
        domain = super()._get_shop_domain(search, category, attribute_value_dict, search_in_description)
        need_key = request.params.get('need')
        if need_key:
            need = request.env['product.tag'].search(fields.Domain('ab_shop_need_key', '=', need_key))
            domain &= fields.Domain('public_categ_ids', 'child_of', need._ab_shop_category_ids(request.website))
        brand_id = self._ab_storefront_brand_id()
        if brand_id:
            domain &= fields.Domain('ab_storefront_brand_id', '=', brand_id)
        deals = self._ab_storefront_deals()
        if deals:
            domain &= request.website._ab_storefront_deal_candidate_domain(deals)
        return domain

    def _shop_get_query_url_kwargs(self, *args, **kwargs):
        values = super()._shop_get_query_url_kwargs(*args, **kwargs)
        values['need'] = request.params.get('need') or None
        values['brand'] = self._ab_storefront_brand_id() or None
        values['deal'] = ','.join(self._ab_storefront_deals()) or None
        values['include_oos'] = '1' if request.params.get('include_oos') == '1' else None
        return values

    def _ab_storefront_brand_id(self):
        try:
            brand_id = int(request.params.get('brand') or 0)
        except (TypeError, ValueError):
            return 0
        return brand_id if 0 < brand_id <= 2147483647 else 0

    def _ab_storefront_deals(self):
        selected = set((request.params.get('deal') or '').split(','))
        return tuple(deal for deal in ('discount', 'coupon', 'today') if deal in selected)

    def _ab_storefront_brands(self, values):
        domain = super()._get_shop_domain(
            values.get('original_search') or values.get('search'),
            values.get('category'),
            values.get('attrib_values') or {},
        )
        need_key = request.params.get('need')
        if need_key:
            need = request.env['product.tag'].search(fields.Domain('ab_shop_need_key', '=', need_key))
            domain &= fields.Domain('public_categ_ids', 'child_of', need._ab_shop_category_ids(request.website))
        groups = request.env['product.template']._read_group(
            domain & fields.Domain('ab_storefront_brand_id', '!=', False),
            ['ab_storefront_brand_id'], ['__count'],
        )
        brand_ids = [brand.id for brand, _count in groups if brand]
        brands = request.env['ab_product_company'].sudo().browse(brand_ids).sorted('name')
        return [{'id': brand.id, 'name': brand.name} for brand in brands]

    def _ab_storefront_price_range_values(self, values):
        website = request.website
        if not website.is_view_active("website_sale.filter_products_price"):
            return {}

        available_min_price, available_max_price, price_histogram = self._ab_storefront_available_price_range(values)
        current_min_price = values.get("min_price") or available_min_price
        current_max_price = values.get("max_price") or available_max_price

        if current_min_price < available_min_price:
            current_min_price = available_min_price
        if current_min_price > available_max_price:
            current_min_price = available_min_price
        if current_max_price > available_max_price or current_max_price < available_min_price:
            current_max_price = available_max_price

        return {
            "available_min_price": float_round(available_min_price, 2),
            "available_max_price": float_round(available_max_price, 2),
            "min_price": current_min_price,
            "max_price": current_max_price,
            "ab_price_histogram": price_histogram,
        }

    def _ab_storefront_available_price_range(self, values):
        website = request.website
        company_currency = website.company_id.sudo().currency_id
        conversion_rate = request.env["res.currency"]._get_conversion_rate(
            company_currency,
            website.currency_id,
            website.company_id,
            fields.Date.today(),
        )
        domain = self._get_shop_domain(
            values.get("original_search") or values.get("search"),
            values.get("category"),
            values.get("attrib_values") or {},
        )
        Product = request.env["product.template"].with_context(bin_size=True)
        query = Product._search(domain)
        price_expression = SQL(
            "COALESCE(list_price, 0) * %(conversion_rate)s",
            conversion_rate=conversion_rate,
        )
        price_subquery = query.subselect(SQL("%s AS price", price_expression))
        min_price, max_price = request.env.execute_query(
            SQL(
                """
                WITH filtered_prices AS %s
                SELECT COALESCE(MIN(price), 0), COALESCE(MAX(price), 0)
                FROM filtered_prices
                """,
                price_subquery,
            )
        )[0]

        min_price = float(min_price or 0)
        max_price = float(max_price or 0)
        return min_price, max_price, self._ab_storefront_price_histogram(query, price_expression, min_price, max_price)

    def _ab_storefront_price_histogram(self, query, price_expression, min_price, max_price):
        bucket_count = 16
        buckets = [0 for _index in range(bucket_count)]
        if not max_price:
            return buckets
        if min_price == max_price:
            return [100 if index == bucket_count - 1 else 12 for index in range(bucket_count)]

        price_span = max_price - min_price
        price_subquery = query.subselect(SQL("%s AS price", price_expression))
        bucket_rows = request.env.execute_query(
            SQL(
                """
                WITH filtered_prices AS %s
                SELECT
                    LEAST(
                        %s,
                        GREATEST(
                            0,
                            FLOOR(((price - %s) / %s) * %s)::int
                        )
                    ) AS bucket_index,
                    COUNT(*) AS bucket_count
                FROM filtered_prices
                GROUP BY bucket_index
                """,
                price_subquery,
                bucket_count - 1,
                min_price,
                price_span,
                bucket_count - 1,
            )
        )
        for bucket_index, bucket_total in bucket_rows:
            buckets[int(bucket_index)] = int(bucket_total)

        max_bucket = max(buckets) or 1
        return [
            max(12, round((bucket / max_bucket) * 100)) if bucket else 0
            for bucket in buckets
        ]
