from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestInventoryTotalBalance(TransactionCase):
    def setUp(self):
        super().setUp()
        self.store_a = self.env["ab_store"].sudo().create({
            "name": "Total Balance Store A",
            "code": "TBSA",
            "eplus_serial": 1001,
        })
        self.store_b = self.env["ab_store"].sudo().create({
            "name": "Total Balance Store B",
            "code": "TBSB",
            "eplus_serial": 1002,
        })
        self.product = self._create_product("TB-SUM", 901001)
        self.null_only_product = self._create_product("TB-NULL-ONLY", 901002)

    def _create_product(self, code, eplus_serial):
        card = self.env["ab_product_card"].sudo().create({"name": code})
        return self.env["ab_product"].sudo().create({
            "product_card_id": card.id,
            "code": code,
            "eplus_serial": eplus_serial,
            "default_price": 10.0,
        })

    def _create_inventory_rows(self):
        Inventory = self.env["ab_sales_inventory"].sudo()
        Inventory.create([
            {
                "product_eplus_serial": self.product.eplus_serial,
                "product_id": self.product.id,
                "product_code": self.product.code,
                "store_id": False,
                "balance": 999.0,
            },
            {
                "product_eplus_serial": self.product.eplus_serial,
                "product_id": self.product.id,
                "product_code": self.product.code,
                "store_id": self.store_a.id,
                "balance": 2.0,
            },
            {
                "product_eplus_serial": self.product.eplus_serial,
                "product_id": self.product.id,
                "product_code": self.product.code,
                "store_id": self.store_b.id,
                "balance": 3.0,
            },
            {
                "product_eplus_serial": self.null_only_product.eplus_serial,
                "product_id": self.null_only_product.id,
                "product_code": self.null_only_product.code,
                "store_id": False,
                "balance": 50.0,
            },
        ])

    def test_product_balance_sums_store_rows_and_ignores_null_total_row(self):
        self._create_inventory_rows()
        Product = self.env["ab_product"].sudo()

        self.assertEqual(self.product.balance, 5.0)
        self.assertEqual(self.null_only_product.balance, 0.0)

        products_with_balance = Product.search([
            ("id", "in", [self.product.id, self.null_only_product.id]),
            ("has_balance", "=", True),
        ])
        self.assertEqual(products_with_balance, self.product)

    def test_inventory_total_helper_sums_store_rows_and_keeps_branch_balance(self):
        self._create_inventory_rows()
        api = self.env["ab_sales_ui_api"].sudo()

        total_by_serial, pos_by_serial = api._inventory_total_and_pos_balances_by_serial(
            [self.product.eplus_serial, self.null_only_product.eplus_serial],
            store_id=self.store_a.id,
        )

        self.assertEqual(total_by_serial.get(self.product.eplus_serial), 5.0)
        self.assertEqual(pos_by_serial.get(self.product.eplus_serial), 2.0)
        self.assertNotIn(self.null_only_product.eplus_serial, total_by_serial)

    def test_pos_search_payload_uses_summed_store_total(self):
        self._create_inventory_rows()
        rows = self.env["ab_sales_ui_api"].sudo().search_products(
            query=self.product.code,
            limit=10,
            has_balance=True,
            has_pos_balance=False,
            store_id=self.store_a.id,
        )

        row = next(item for item in rows if item["id"] == self.product.id)
        self.assertEqual(row["balance"], 5.0)
        self.assertEqual(row["pos_balance"], 2.0)

    def test_pos_search_fast_path_uses_summed_store_total(self):
        self._create_inventory_rows()
        customer_phone = "01000000001"
        self.env["ab_product_rank"].sudo().create({
            "product_id": self.product.id,
            "store_id": self.store_a.id,
            "customer_phone": customer_phone,
            "rank_scope": "customer",
            "period_days": 90,
            "order_count": 1,
            "qty_total": 1.0,
            "score": 1.0,
        })

        rows = self.env["ab_sales_ui_api"].sudo().search_products(
            query="",
            limit=10,
            has_balance=True,
            has_pos_balance=True,
            store_id=self.store_a.id,
            customer_phone=customer_phone,
        )

        row = next(item for item in rows if item["id"] == self.product.id)
        self.assertEqual(row["balance"], 5.0)
        self.assertEqual(row["pos_balance"], 2.0)

    def test_api_branch_stores_respect_allowed_store_scope(self):
        self.store_a.allow_sale = True
        self.store_b.allow_sale = True
        Config = self.env["ab_sales_branch_rpc_config"].sudo()
        for index, store in enumerate((self.store_a, self.store_b), start=1):
            Config.create({
                "store_id": store.id,
                "db_serial": 8000 + index,
                "rpc_url": "https://inventory-%s.example.test" % index,
                "rpc_db": "inventory_%s" % index,
                "administrator_id": self.env.ref("base.user_admin").id,
            })

        Client = self.env["ab_sales_branch_client"]
        with patch.object(type(self.env["ab_sales_header"]), "_get_allowed_store_ids", return_value=[self.store_b.id]):
            stores = Client._stores()

        self.assertNotIn(self.store_a, stores)
        self.assertIn(self.store_b, stores)

    def test_apply_api_balances_updates_only_target_store_rows(self):
        stale_line = self.env["ab_sales_inventory"].sudo().create({
            "product_eplus_serial": self.product.eplus_serial,
            "product_id": self.product.id,
            "product_code": self.product.code,
            "store_id": self.store_a.id,
            "balance": 9.0,
        })
        other_store_line = self.env["ab_sales_inventory"].sudo().create({
            "product_eplus_serial": self.product.eplus_serial,
            "product_id": self.product.id,
            "product_code": self.product.code,
            "store_id": self.store_b.id,
            "balance": 3.0,
        })

        self.store_a.allow_sale = True
        self.env["ab_sales_branch_rpc_config"].sudo().create({
            "store_id": self.store_a.id,
            "db_serial": 8101,
            "rpc_url": "https://inventory-cache.example.test",
            "rpc_db": "inventory_cache",
            "administrator_id": self.env.ref("base.user_admin").id,
        })
        self.env["ab_sales_inventory"].sudo()._apply_api_balances(
            self.store_a,
            [{
                "product_eplus_serial": self.product.eplus_serial,
                "store_eplus_serial": self.store_a.eplus_serial,
                "balance": 4.0,
                "default_price": 10.0,
            }],
            "2026-10-06 12:00:00",
            complete=True,
        )

        self.assertEqual(stale_line.balance, 4.0)
        self.assertEqual(other_store_line.balance, 3.0)
