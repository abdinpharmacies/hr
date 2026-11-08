from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.website_sale.tests.common import MockRequest

from ..controllers.shop import AbEcommerceStorefrontShop


@tagged("post_install", "-at_install")
class TestStorefrontStockAvailability(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref("website.default_website")
        cls.company = cls.website.company_id
        cls.warehouse = cls.env["stock.warehouse"].create({
            "name": "Storefront stock validation", "code": "SSV",
            "company_id": cls.company.id,
        })
        cls.website.warehouse_id = cls.warehouse
        cls.warehouse.out_type_id.reservation_method = "at_confirm"
        cls.partner = cls.env["res.partner"].create({"name": "Storefront stock customer"})
        cls.source = cls.env["ab_product"].create({
            "name": "Storefront stock product", "product_card_name": "Storefront stock product",
            "code": "STOREFRONT-STOCK-TEST",
        })
        template = cls.env["product.template"].create({
            "name": "Storefront stock product", "type": "consu", "is_storable": True,
            "ab_product_id": cls.source.id, "eplus_stock_shown_qty_value": 100.0,
            "list_price": 10.0, "is_published": True,
            "website_id": cls.website.id, "company_id": cls.company.id,
            "taxes_id": [Command.clear()],
        })
        cls.product = template.product_variant_id
        cls.snapshot = cls.env["ab_eplus_stock_snapshot"].create({
            "itm_id": -20261018, "product_id": cls.source.id, "itm_qty": 100.0,
        })
        cls.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": cls.product.id, "location_id": cls.warehouse.lot_stock_id.id,
            "inventory_quantity": 10.0,
        }).action_apply_inventory()

    def order(self, quantity=3.0, warehouse=None):
        return self.env["sale.order"].with_context(mail_notrack=True).create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "warehouse_id": (warehouse or self.warehouse).id, "company_id": self.company.id,
            "order_line": [Command.create({
                "product_id": self.product.id, "product_uom_qty": quantity,
                "price_unit": 10.0, "tax_ids": [Command.clear()],
            })],
        })

    def setUp(self):
        super().setUp()
        self.patch(type(self.env["sale.order"]), "_ab_require_authoritative_reservation", lambda order: None)

    def available(self):
        website = self.website.with_user(self.website.user_id).with_context(
            website_id=self.website.id, allowed_company_ids=self.company.ids,
        )
        return website._get_product_available_qty(self.product.with_env(website.env))

    def on_hand(self):
        return self.product.with_context(warehouse_id=self.warehouse.id).qty_available

    def deliver(self, order):
        picking = order.picking_ids
        picking.move_ids.write({"quantity": order.order_line.product_uom_qty, "picked": True})
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        return picking

    def test_reservation_delivery_and_last_mile_deduct_once(self):
        order = self.order()
        self.assertEqual(self.available(), 10.0)
        self.assertEqual(order._get_free_qty(self.product), 10.0)
        order.action_confirm()
        self.assertEqual(self.on_hand(), 10.0)
        self.assertEqual(self.available(), 7.0)
        with self.assertRaises(UserError):
            order.action_ab_mark_delivered()
        self.deliver(order)
        self.assertEqual(self.on_hand(), 7.0)
        self.assertEqual(self.available(), 7.0)
        order.action_ab_mark_delivered()
        order.action_ab_mark_delivered()
        self.assertEqual(self.on_hand(), 7.0)
        self.assertEqual(self.available(), 7.0)
        self.assertEqual(self.snapshot.itm_qty, 100.0)

    def test_eplus_resync_replaces_stock_after_website_delivery(self):
        order = self.order(quantity=1)
        order.action_confirm()
        picking = self.deliver(order)
        self.assertEqual(self.on_hand(), 9.0)
        with patch.object(
            type(self.snapshot), "_get_inventory_sync_warehouse", return_value=self.warehouse,
        ):
            for quantity in (5.0, 12.0, 0.0):
                self.snapshot.itm_qty = quantity
                self.snapshot._sync_to_odoo_inventory()
                self.assertEqual(self.on_hand(), quantity)
                result = self.snapshot._sync_to_odoo_inventory()
                self.assertEqual(result["updated"], 0)
                self.assertEqual(self.on_hand(), quantity)
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.move_ids.quantity, 1.0)

    def test_eplus_full_sync_uses_source_after_delivery(self):
        order = self.order(quantity=1)
        order.action_confirm()
        self.deliver(order)
        job = self.env["ab_eplus_inventory_sync_job"].create({
            "warehouse_id": self.warehouse.id,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        with patch.object(
            type(self.snapshot), "_get_inventory_sync_stock_groups",
            return_value=[(self.source, 6.0)],
        ):
            job._prepare_full_sync()
        job._process_all_remaining_batches()
        self.assertEqual(job.state, "done")
        self.assertEqual(self.on_hand(), 6.0)
        self.assertEqual(job.updated_count, 1)

    def test_eplus_full_sync_clears_disappeared_source_stock(self):
        self.snapshot.active = False
        groups = self.snapshot._get_inventory_sync_stock_groups()
        self.assertEqual(dict(groups)[self.source], 0.0)
        job = self.env["ab_eplus_inventory_sync_job"].create({
            "warehouse_id": self.warehouse.id,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        with patch.object(
            type(self.snapshot), "_get_inventory_sync_stock_groups",
            return_value=[(self.source, dict(groups)[self.source])],
        ):
            job._prepare_full_sync()
        job._process_all_remaining_batches()
        self.assertEqual(job.state, "done")
        self.assertEqual(self.on_hand(), 0.0)
        self.assertTrue(self.product.exists())
        self.assertTrue(self.snapshot.exists())

    def branch_row(self, store_id, quantity):
        return self.snapshot._normalize_eplus_store_row({
            "itm_id": self.snapshot.itm_id, "itm_code": self.source.code,
            "sto_id": store_id, "itm_qty": quantity,
        })

    def test_branch_refresh_replaces_in_batches_and_archives_missing(self):
        Store = self.env["ab_eplus_stock_snapshot_store"]
        Store._refresh_from_eplus_rows([self.branch_row(7001, 30), self.branch_row(7003, 20)])
        with patch.object(type(self.snapshot), "_fetch_eplus_stock_store_rows", return_value=iter([
            [self.branch_row(7001, 7)], [self.branch_row(7002, 9)],
        ])):
            result = self.snapshot._refresh_branch_stock_from_eplus()
        rows = Store.search([("itm_id", "=", self.snapshot.itm_id)])
        self.assertEqual({row.sto_id: row.itm_qty for row in rows}, {7001: 7, 7002: 9})
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["matched"], 2)
        archived = Store.with_context(active_test=False).search([
            ("itm_id", "=", self.snapshot.itm_id), ("sto_id", "=", 7003),
        ])
        self.assertTrue(archived)
        self.assertFalse(archived.active)

    def test_branch_refresh_failure_preserves_previous_snapshot(self):
        Store = self.env["ab_eplus_stock_snapshot_store"]
        Store._refresh_from_eplus_rows([self.branch_row(7001, 30)])

        def failing_batches():
            yield [self.branch_row(7001, 7)]
            raise RuntimeError("source disconnected")

        with patch.object(type(self.snapshot), "_fetch_eplus_stock_store_rows", return_value=failing_batches()):
            with self.assertRaisesRegex(RuntimeError, "source disconnected"):
                self.snapshot._refresh_branch_stock_from_eplus()
        row = Store.search([("itm_id", "=", self.snapshot.itm_id), ("sto_id", "=", 7001)])
        self.assertTrue(row.active)
        self.assertEqual(row.itm_qty, 30)

    def test_branch_query_uses_bounded_fetches(self):
        cursor = MagicMock()
        cursor.description = [("itm_id",), ("itm_code",), ("sto_id",), ("itm_qty",)]
        cursor.fetchmany.side_effect = [[(123, "P123", 1, 2)], [(124, "P124", 1, 3)], []]
        batches = list(self.snapshot._execute_eplus_stock_store_query(cursor, "SELECT stock WHERE sto_id = ?", (1,)))
        self.assertEqual([batch[0]["itm_qty"] for batch in batches], [2.0, 3.0])
        cursor.execute.assert_called_once_with("SELECT stock WHERE sto_id = ?", (1,))
        cursor.fetchall.assert_not_called()
        self.assertEqual(cursor.fetchmany.call_count, 3)

    def branch_connection(self):
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [(7001,), (7002,)]
        return connection, cursor

    def test_branch_queries_are_scoped_and_use_odbc(self):
        connection, cursor = self.branch_connection()
        with patch.object(type(self.snapshot), "connect_eplus", return_value=connection) as connect, patch.object(
            type(self.snapshot), "_execute_eplus_stock_store_query", return_value=iter([]),
        ) as query:
            list(self.snapshot._fetch_eplus_stock_store_rows())
        self.assertEqual(connect.call_args.kwargs["param_str"], "?")
        self.assertTrue(connect.call_args.kwargs["propagate_error"])
        self.assertEqual([call.args[2] for call in query.call_args_list], [(7001,), (7002,)])
        for call in query.call_args_list:
            self.assertIn("WHERE ics.sto_id = ?", call.args[1])

    def test_branch_timeout_does_not_retry_metadata_query(self):
        connection, cursor = self.branch_connection()
        with patch.object(type(self.snapshot), "connect_eplus", return_value=connection), patch.object(
            type(self.snapshot), "_execute_eplus_stock_store_query", side_effect=RuntimeError("HYT00 timeout"),
        ) as query:
            with self.assertRaisesRegex(UserError, "previous snapshot has been kept"):
                list(self.snapshot._fetch_eplus_stock_store_rows())
        self.assertEqual(query.call_count, 1)

    def test_branch_missing_columns_use_basic_query(self):
        connection, cursor = self.branch_connection()
        cursor.fetchall.return_value = [(7001,)]
        with patch.object(type(self.snapshot), "connect_eplus", return_value=connection), patch.object(
            type(self.snapshot), "_execute_eplus_stock_store_query",
            side_effect=[RuntimeError("42S22 invalid column"), iter([[self.branch_row(7001, 7)]])],
        ) as query:
            rows = list(self.snapshot._fetch_eplus_stock_store_rows())
        self.assertEqual(rows[0][0]["itm_qty"], 7)
        self.assertEqual(query.call_count, 2)
        self.assertNotIn("LEFT JOIN Store", query.call_args.args[1])
        self.assertEqual(query.call_args.args[2], (7001,))

    def test_branch_partial_read_does_not_retry_with_mixed_snapshot(self):
        connection, cursor = self.branch_connection()

        def failing_query(cursor, query, parameters):
            yield [self.branch_row(7001, 7)]
            raise RuntimeError("source disconnected")

        with patch.object(type(self.snapshot), "connect_eplus", return_value=connection), patch.object(
            type(self.snapshot), "_execute_eplus_stock_store_query", side_effect=failing_query,
        ) as query:
            with self.assertRaisesRegex(UserError, "previous snapshot has been kept"):
                list(self.snapshot._fetch_eplus_stock_store_rows())
        self.assertEqual(query.call_count, 1)

    def test_cancel_releases_reserved_availability(self):
        order = self.order()
        order.action_confirm()
        self.assertEqual(self.available(), 7.0)
        order.with_context(disable_cancel_warning=True).action_cancel()
        self.assertEqual(order.state, "cancel")
        self.assertEqual(self.available(), 10.0)
        self.assertEqual(self.on_hand(), 10.0)

    def test_validated_return_restores_stock(self):
        order = self.order()
        order.action_confirm()
        picking = self.deliver(order)
        wizard = self.env["stock.return.picking"].create({"picking_id": picking.id})
        wizard.product_return_moves.quantity = 3.0
        returned = self.env["stock.picking"].browse(wizard.action_create_returns()["res_id"])
        returned.move_ids.write({"quantity": 3.0, "picked": True})
        returned.button_validate()
        self.assertEqual(returned.state, "done")
        self.assertEqual(self.available(), 10.0)
        self.assertEqual(self.on_hand(), 10.0)

    def test_checkout_is_limited_by_unreserved_stock(self):
        reserved_order = self.order(8.0)
        reserved_order.action_confirm()
        cart = self.order(1.0)
        quantity, warning = cart._verify_updated_quantity(
            cart.order_line, self.product.id, 5.0, self.product.uom_id.id,
        )
        self.assertEqual(quantity, 2.0)
        self.assertTrue(warning)

    def test_checkout_converts_stock_to_sale_unit(self):
        pack = self.env.ref("uom.product_uom_pack_6")
        cart = self.order(1.0)
        cart.order_line.product_uom_id = pack
        quantity, warning = cart._verify_updated_quantity(
            cart.order_line, self.product.id, 2.0, pack.id,
        )
        self.assertEqual(quantity, 1.0)
        self.assertTrue(warning)

    def test_partial_delivery_keeps_backorder_reserved(self):
        order = self.order()
        order.action_confirm()
        picking = order.picking_ids
        picking.move_ids.write({"quantity": 1.0, "picked": True})
        picking.with_context(skip_backorder=True).button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(self.on_hand(), 9.0)
        self.assertEqual(self.available(), 7.0)
        with self.assertRaises(UserError):
            order.action_ab_mark_delivered()
        backorder = order.picking_ids - picking
        backorder.move_ids.write({"quantity": 2.0, "picked": True})
        backorder.button_validate()
        order.action_ab_mark_delivered()
        self.assertEqual(self.on_hand(), 7.0)
        self.assertEqual(self.available(), 7.0)

    def test_sold_out_product_hidden_from_catalog(self):
        order = self.order(10.0)
        order.action_confirm()
        self.assertEqual(self.available(), 0.0)
        self.assertTrue(self.product.with_context(website_id=self.website.id)._is_sold_out())
        with MockRequest(self.env, website=self.website):
            visible = AbEcommerceStorefrontShop()._ab_storefront_available_products(
                self.product.product_tmpl_id, self.website,
            )
        self.assertFalse(visible)

    def test_other_warehouse_stock_is_not_available(self):
        other = self.env["stock.warehouse"].create({
            "name": "Other storefront warehouse", "code": "SSO", "company_id": self.company.id,
        })
        self.website.warehouse_id = other
        self.assertEqual(self.available(), 0.0)
        self.assertEqual(self.order(warehouse=other)._get_free_qty(self.product), 0.0)

    def test_other_company_warehouse_is_rejected(self):
        company = self.env["res.company"].create({"name": "Other storefront stock company"})
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        product = self.product.with_context(website_id=self.website.id, warehouse_id=warehouse.id)
        self.assertEqual(product._get_ab_website_available_qty(), 0.0)
        self.website.warehouse_id = warehouse
        self.assertFalse(self.website._ab_storefront_stock_warehouse_id())
        self.assertEqual(self.available(), 0.0)
        with MockRequest(self.env, website=self.website):
            visible = AbEcommerceStorefrontShop()._ab_storefront_available_products(
                self.product.product_tmpl_id, self.website,
            )
        self.assertFalse(visible)

    def test_warehouse_fallback_matches_order(self):
        self.website.warehouse_id = False
        warehouse_id = self.website._ab_storefront_stock_warehouse_id()
        order = self.order(warehouse=self.env["stock.warehouse"].browse(warehouse_id))
        self.assertEqual(order._get_free_qty(self.product), self.available())

    def test_configured_quantity_and_percentage_caps_are_preserved(self):
        self.product.eplus_stock_shown_qty_value = 4.0
        self.assertEqual(self.available(), 4.0)
        self.product.write({"eplus_stock_shown_qty_type": "percentage", "eplus_stock_shown_qty_value": 5.0})
        self.assertEqual(self.available(), 5.0)
        self.snapshot.itm_qty = 2.0
        self.assertAlmostEqual(self.available(), 0.1)

    def test_public_cannot_deliver_or_edit_inventory(self):
        order = self.order()
        with self.assertRaises(AccessError):
            order.with_user(self.website.user_id).action_ab_mark_delivered()
        quant = self.env["stock.quant"].search([
            ("product_id", "=", self.product.id), ("location_id", "=", self.warehouse.lot_stock_id.id),
        ])
        with self.assertRaises(AccessError):
            quant.with_user(self.website.user_id).write({"inventory_quantity": 99.0})

    def test_non_eplus_product_keeps_native_availability(self):
        self.product.product_tmpl_id.ab_product_id = False
        self.assertIsNone(self.product._get_ab_website_available_qty())
        self.assertEqual(self.website._get_product_available_qty(self.product), 10.0)

    def test_catalog_preserves_native_quantities_and_caller_order(self):
        service = self.env['product.template'].create({
            'name': 'Catalog service', 'type': 'service', 'sale_ok': True,
        })
        empty = self.env['product.template'].create({
            'name': 'Catalog empty stock', 'type': 'consu', 'is_storable': True,
            'allow_out_of_stock_order': False,
        })
        templates = empty | service | self.product.product_tmpl_id
        native_quantities = templates.product_variant_id.with_context(
            warehouse_id=self.warehouse.id, allowed_company_ids=self.company.ids,
        )
        self.assertEqual(native_quantities.filtered(lambda product: product.free_qty > 0), self.product)
        website = self.website.with_user(self.website.user_id).with_context(
            website_id=self.website.id, allowed_company_ids=self.company.ids,
        )
        with MockRequest(website.env, website=website):
            visible = AbEcommerceStorefrontShop()._ab_storefront_available_products(
                templates.with_env(website.env), website,
            )
        self.assertEqual(visible.ids, (service | self.product.product_tmpl_id).ids)
        self.assertEqual(visible.env.uid, website.env.uid)
        self.assertFalse(visible.env.su)

    def test_unavailable_source_skips_native_quantity_calculation(self):
        self.snapshot.itm_qty = 0
        with MockRequest(self.env, website=self.website), patch.object(
            type(self.product), '_compute_quantities_dict',
            side_effect=AssertionError('Already unavailable products need no quantity calculation'),
        ):
            visible = AbEcommerceStorefrontShop()._ab_storefront_available_products(
                self.product.product_tmpl_id, self.website,
            )
        self.assertFalse(visible)

    def test_catalog_keeps_native_first_variant_selection(self):
        attribute = self.env['product.attribute'].create({'name': 'Catalog size'})
        values = self.env['product.attribute.value'].create([
            {'name': 'Small', 'attribute_id': attribute.id},
            {'name': 'Large', 'attribute_id': attribute.id},
        ])
        template = self.env['product.template'].create({
            'name': 'Catalog variants', 'type': 'consu', 'is_storable': True,
            'allow_out_of_stock_order': False,
            'attribute_line_ids': [Command.create({
                'attribute_id': attribute.id, 'value_ids': [Command.set(values.ids)],
            })],
        })
        variants = template.product_variant_ids.sorted('id')
        variants[0].default_code = 'CATALOG-Z'
        variants[1].default_code = 'CATALOG-A'
        template.invalidate_recordset(['product_variant_ids', 'product_variant_id'])
        first = template.with_context(active_test=False).product_variant_id
        self.assertEqual(first, variants[1])
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': first.id, 'location_id': self.warehouse.lot_stock_id.id,
            'inventory_quantity': 2,
        }).action_apply_inventory()
        with MockRequest(self.env, website=self.website):
            self.assertEqual(AbEcommerceStorefrontShop()._ab_storefront_available_products(
                template, self.website,
            ), template)
