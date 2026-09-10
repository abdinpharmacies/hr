from odoo import fields
from odoo.http import request
from odoo.tools import SQL, float_round

from odoo.addons.website_sale.controllers.main import WebsiteSale


class AbEcommerceStorefrontShop(WebsiteSale):
    """Storefront shop refinements that keep Odoo's native /shop behavior."""

    def _get_additional_shop_values(self, values, **kwargs):
        result = super()._get_additional_shop_values(values, **kwargs)
        result.update(self._ab_storefront_price_range_values(values))
        return result

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
