from odoo.tests.common import TransactionCase


class TestItemTypeFilters(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = cls.env["ab_sales_ui_api"].sudo()
        cls.setup_env = cls.env(
            user=cls.env.ref("base.user_root").id,
            context={**cls.env.context, "install_mode": True},
        )
        cls.store = cls.setup_env["ab_store"].create({
            "name": "Item Type Filter Store",
            "code": "ITFSTORE",
            "allow_sale": True,
        })
        cls.medicine_product = cls._create_product("ITF-MED", "0000 ITF Medicine Product", True, 940001)
        cls.non_medicine_product = cls._create_product("ITF-NON", "0000 ITF Non Medicine Product", False, 940002)

    @classmethod
    def _create_product(cls, code, name, is_medicine, eplus_serial):
        card = cls.setup_env["ab_product_card"].create({
            "name": name,
            "is_medicine": is_medicine,
        })
        return cls.setup_env["ab_product"].create({
            "product_card_id": card.id,
            "name": name,
            "code": code,
            "is_medicine": is_medicine,
            "default_price": 10.0,
            "eplus_serial": eplus_serial,
        })

    def _create_sale(self, products, status="pending", **header_vals):
        vals = {"store_id": self.store.id, "status": status}
        vals.update(header_vals)
        header = self.setup_env["ab_sales_header"].create(vals)
        for product in products:
            self.setup_env["ab_sales_line"].create({
                "header_id": header.id,
                "product_id": product.id,
                "qty_str": "1",
                "sell_price": 10.0,
            })
        return header

    def _create_return(self, products, status="pending", **header_vals):
        vals = {"store_id": self.store.id, "status": status}
        vals.update(header_vals)
        header = self.setup_env["ab_sales_return_header"].create(vals)
        for product in products:
            self.setup_env["ab_sales_return_line"].create({
                "header_id": header.id,
                "product_id": product.id,
                "qty_str": "1",
                "sell_price": 10.0,
                "max_returnable_qty": 1.0,
            })
        return header

    def test_bill_wizard_item_type_filters_sales_returns_and_mixed_records(self):
        medicine_sale = self._create_sale([self.medicine_product])
        non_medicine_sale = self._create_sale([self.non_medicine_product])
        mixed_sale = self._create_sale([self.medicine_product, self.non_medicine_product])
        medicine_return = self._create_return([self.medicine_product])
        non_medicine_return = self._create_return([self.non_medicine_product])
        mixed_return = self._create_return([self.medicine_product, self.non_medicine_product])

        medicine = self.api.bill_wizard_search(item_type="medicine", page=1)
        medicine_ids = {row["id"] for row in medicine["items"]}
        self.assertEqual(medicine["filters"]["item_type"], "medicine")
        self.assertIn(medicine_sale.id, medicine_ids)
        self.assertIn(mixed_sale.id, medicine_ids)
        self.assertIn(-medicine_return.id, medicine_ids)
        self.assertIn(-mixed_return.id, medicine_ids)
        self.assertNotIn(non_medicine_sale.id, medicine_ids)
        self.assertNotIn(-non_medicine_return.id, medicine_ids)

        non_medicine = self.api.bill_wizard_search(item_type="non_medicine", page=1)
        non_medicine_ids = {row["id"] for row in non_medicine["items"]}
        self.assertEqual(non_medicine["filters"]["item_type"], "non_medicine")
        self.assertIn(non_medicine_sale.id, non_medicine_ids)
        self.assertIn(mixed_sale.id, non_medicine_ids)
        self.assertIn(-non_medicine_return.id, non_medicine_ids)
        self.assertIn(-mixed_return.id, non_medicine_ids)
        self.assertNotIn(medicine_sale.id, non_medicine_ids)
        self.assertNotIn(-medicine_return.id, non_medicine_ids)

    def test_bill_wizard_invalid_item_type_defaults_to_all_and_keeps_latest_20(self):
        for index in range(25):
            product = self.medicine_product if index % 2 else self.non_medicine_product
            self._create_sale([product])

        result = self.api.bill_wizard_search(item_type="invalid", page=9, per_page=99)

        self.assertEqual(result["filters"]["item_type"], "all")
        self.assertFalse(result["is_search"])
        self.assertEqual(len(result["items"]), 20)
        self.assertEqual(result["pagination"]["page"], 1)
        self.assertEqual(result["pagination"]["per_page"], 20)
        self.assertEqual(result["pagination"]["page_count"], 1)
        self.assertEqual(result["pagination"]["total_count"], 20)

    def test_product_search_item_type_filters_code_name_balance_and_customer_recommendations(self):
        phone = "01012345678"
        self.setup_env["ab_product_rank"].create([
            {
                "product_id": self.medicine_product.id,
                "store_id": self.store.id,
                "customer_phone": phone,
                "rank_scope": "customer",
                "period_days": 90,
                "order_count": 5,
                "qty_total": 5.0,
                "score": 5.0,
            },
            {
                "product_id": self.non_medicine_product.id,
                "store_id": self.store.id,
                "customer_phone": phone,
                "rank_scope": "customer",
                "period_days": 90,
                "order_count": 4,
                "qty_total": 4.0,
                "score": 4.0,
            },
        ])
        self.setup_env["ab_sales_inventory"].create([
            {
                "product_eplus_serial": self.medicine_product.eplus_serial,
                "product_id": self.medicine_product.id,
                "product_code": self.medicine_product.code,
                "store_id": self.store.id,
                "balance": 3.0,
            },
            {
                "product_eplus_serial": self.non_medicine_product.eplus_serial,
                "product_id": self.non_medicine_product.id,
                "product_code": self.non_medicine_product.code,
                "store_id": self.store.id,
                "balance": 2.0,
            },
        ])
        self.env.flush_all()

        by_code = self.api.search_products(
            query=self.medicine_product.code,
            has_balance=False,
            item_type="medicine",
        )
        self.assertEqual([row["id"] for row in by_code], self.medicine_product.ids)
        self.assertFalse(self.api.search_products(
            query=self.medicine_product.code,
            has_balance=False,
            item_type="non_medicine",
        ))

        by_name = self.api.search_products(
            query="0000 ITF Non Medicine",
            has_balance=False,
            item_type="non_medicine",
        )
        self.assertIn(self.non_medicine_product.id, [row["id"] for row in by_name])

        recommended = self.api.search_products(
            query="",
            has_balance=False,
            customer_phone=phone,
            item_type="medicine",
        )
        self.assertIn(self.medicine_product.id, [row["id"] for row in recommended])
        self.assertNotIn(self.non_medicine_product.id, [row["id"] for row in recommended])

        pos_balance = self.api.search_products(
            query=self.non_medicine_product.code,
            store_id=self.store.id,
            has_balance=True,
            has_pos_balance=True,
            item_type="non_medicine",
        )
        self.assertIn(self.non_medicine_product.id, [row["id"] for row in pos_balance])
        self.assertNotIn(self.medicine_product.id, [row["id"] for row in pos_balance])

        blank_pos_balance = self.api.search_products(
            query="",
            store_id=self.store.id,
            has_balance=True,
            has_pos_balance=True,
            item_type="non_medicine",
        )
        self.assertTrue(all(not row.get("is_medicine") for row in blank_pos_balance))

    def test_partial_barcode_respects_item_type(self):
        if "ab_product_barcode" not in self.env.registry:
            self.skipTest("ab_product_barcode is not installed")

        barcode = "998877665544"
        self.setup_env["ab_product_barcode"].create({
            "name": barcode,
            "product_ids": [(6, 0, [self.medicine_product.id, self.non_medicine_product.id])],
        })

        medicine_rows = self.api._search_products_by_partial_barcode(
            barcode_query=barcode[-8:],
            has_balance=False,
            item_type="medicine",
        )
        self.assertIn(self.medicine_product.id, [row["id"] for row in medicine_rows])
        self.assertNotIn(self.non_medicine_product.id, [row["id"] for row in medicine_rows])

        non_medicine_rows = self.api._search_products_by_partial_barcode(
            barcode_query=barcode[-8:],
            has_balance=False,
            item_type="non_medicine",
        )
        self.assertIn(self.non_medicine_product.id, [row["id"] for row in non_medicine_rows])
        self.assertNotIn(self.medicine_product.id, [row["id"] for row in non_medicine_rows])
