from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestPosPriceBadges(TransactionCase):
    def _create_product(self, code, default_price, is_priced=None, is_medicine=True):
        card = self.env["ab_product_card"].sudo().create({
            "name": code,
            "is_medicine": is_medicine,
        })
        product = self.env["ab_product"].sudo().create({
            "product_card_id": card.id,
            "code": code,
            "default_price": default_price,
            **({"is_priced": is_priced} if is_priced is not None else {}),
        })
        return product

    def _price_line(self, product):
        return self.env["ab_sales_line"].new({
            "product_id": product.id,
            "inventory_json": {
                "data": [
                    {"price": 7.0, "qty": 5.0},
                    {"price": 15.0, "qty": 2.0},
                    {"price": 12.0, "qty": 3.0},
                ],
            },
        })

    def _create_header(self):
        suffix = self.env["ab_store"].sudo().search_count([]) + 1
        store = self.env["ab_store"].sudo().create({
            "name": "POS Price Badge Store",
            "code": f"POSPB{suffix}",
        })
        return self.env["ab_sales_header"].sudo().create({
            "store_id": store.id,
            "status": "pending",
        })

    def _create_uom_pair(self):
        suffix = self.env["ab_product_uom_category"].sudo().search_count([]) + 1
        category = self.env["ab_product_uom_category"].sudo().create({
            "name": f"POS UoM Category {suffix}",
        })
        default_uom = self.env["ab_product_uom"].sudo().create({
            "name": f"Unit {suffix}",
            "category_id": category.id,
            "factor": 1.0,
        })
        alternate_uom = self.env["ab_product_uom"].sudo().create({
            "name": f"Box {suffix}",
            "category_id": category.id,
            "factor": 10.0,
        })
        return category, default_uom, alternate_uom

    def _create_sales_line(self, product, sell_price):
        return self.env["ab_sales_line"].sudo().create({
            "header_id": self._create_header().id,
            "product_id": product.id,
            "qty_str": "1",
            "sell_price": sell_price,
            "inventory_json": {
                "data": [
                    {"price": 7.0, "qty": 5.0},
                    {"price": 15.0, "qty": 2.0},
                    {"price": 12.0, "qty": 3.0},
                ],
            },
        })

    def test_unpriced_product_shows_all_badges_with_highest_price(self):
        product = self._create_product("POS-HIGH-ONLY", 10.0, False)
        items = self.env["ab_sales_pos_api"].sudo()._available_prices_list(self._price_line(product))

        self.assertEqual(len(items), 4)
        self.assertEqual([item["price"] for item in items], [15.0, 15.0, 15.0, 15.0])
        self.assertEqual([item["qty"] for item in items], [0.0, 5.0, 3.0, 2.0])

    def test_priced_product_keeps_all_available_prices(self):
        product = self._create_product("POS-ALL-PRICES", 10.0, True)
        items = self.env["ab_sales_pos_api"].sudo()._available_prices_list(self._price_line(product))

        self.assertEqual([item["price"] for item in items], [10.0, 7.0, 12.0, 15.0])

    def test_sales_line_sell_price_must_match_price_badges(self):
        product = self._create_product("POS-LINE-PRICE-OK", 10.0, True)

        self._create_sales_line(product, 12.0)
        with self.assertRaises(ValidationError):
            self._create_sales_line(product, 13.0)

    def test_unpriced_sales_line_sell_price_allows_only_highest_badge_price(self):
        product = self._create_product("POS-LINE-HIGHEST-ONLY", 10.0, False)

        self._create_sales_line(product, 15.0)
        with self.assertRaises(ValidationError):
            self._create_sales_line(product, 7.0)

    def test_pos_line_uom_uses_default_when_product_is_restricted(self):
        category, default_uom, alternate_uom = self._create_uom_pair()
        product = self._create_product("POS-DEFAULT-UOM-ONLY", 10.0, True)
        product.write({
            "uom_category_id": category.id,
            "uom_id": default_uom.id,
            "only_default_sales_uom": True,
        })

        selected_uom = self.env["ab_sales_pos_api"].sudo()._pos_line_uom_id(product, alternate_uom.id)

        self.assertEqual(selected_uom, default_uom.id)

    def test_is_priced_search_uses_stored_product_field(self):
        unpriced = self._create_product("POS-SEARCH-UNPRICED", 10.0, False)
        priced = self._create_product("POS-SEARCH-PRICED", 10.0, True, is_medicine=False)
        default_priced = self._create_product("POS-SEARCH-DEFAULT", 10.0, is_medicine=True)
        default_unpriced = self._create_product("POS-SEARCH-DEFAULT-NO", 10.0, is_medicine=False)
        Product = self.env["ab_product"].sudo()

        self.assertIn(priced, Product.search([("is_priced", "=", True)]))
        self.assertIn(default_priced, Product.search([("is_priced", "=", True)]))
        self.assertNotIn(unpriced, Product.search([("is_priced", "=", True)]))
        self.assertNotIn(default_unpriced, Product.search([("is_priced", "=", True)]))
        self.assertIn(unpriced, Product.search([("is_priced", "=", False)]))
        self.assertIn(default_unpriced, Product.search([("is_priced", "=", False)]))
        self.assertNotIn(priced, Product.search([("is_priced", "=", False)]))
        self.assertNotIn(default_priced, Product.search([("is_priced", "=", False)]))

    def test_product_priced_import_resolves_product_code(self):
        product = self._create_product("POS-IMPORT-CODE", 10.0)
        flag = self.env["ab_product_metadata"].sudo().create({
            "product_code": product.code,
            "is_priced": False,
        })

        self.assertEqual(flag.product_id, product)
        self.assertEqual(flag.product_code, product.code)
        self.assertTrue(product.is_priced)

    def test_product_priced_import_resolves_inactive_product_code(self):
        product = self._create_product("POS-IMPORT-INACTIVE", 10.0)
        product.active = False

        flag = self.env["ab_product_metadata"].sudo().create({
            "product_code": product.code,
            "is_priced": True,
        })

        self.assertEqual(flag.product_id, product)
        self.assertEqual(flag.product_code, product.code)

    def test_product_priced_write_resolves_product_code(self):
        first_product = self._create_product("POS-IMPORT-WRITE-1", 10.0)
        second_product = self._create_product("POS-IMPORT-WRITE-2", 10.0)
        flag = self.env["ab_product_metadata"].sudo().create({
            "product_id": first_product.id,
            "is_priced": True,
        })

        flag.write({"product_code": second_product.code})

        self.assertEqual(flag.product_id, second_product)
        self.assertEqual(flag.product_code, second_product.code)

    @mute_logger("odoo.sql_db")
    def test_product_metadata_is_unique_per_product(self):
        product = self._create_product("POS-METADATA-UNIQUE", 10.0)
        Metadata = self.env["ab_product_metadata"].sudo()
        Metadata.create({
            "product_id": product.id,
            "is_priced": True,
        })

        try:
            Metadata.create({
                "product_code": product.code,
                "is_priced": False,
            })
        except IntegrityError as ex:
            self.assertIn("ab_product_metadata_uniq_product_id", ex.pgerror)
        else:
            self.fail("Duplicate product metadata should violate the unique product constraint.")

    def test_product_priced_import_rejects_unknown_product_code(self):
        with self.assertRaises(UserError):
            self.env["ab_product_metadata"].sudo().create({
                "product_code": "POS-IMPORT-MISSING",
                "is_priced": True,
            })
