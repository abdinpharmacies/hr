from unittest import SkipTest

from odoo.tests.common import TransactionCase


class TestAbSalesPromoMarker(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Product = self.env["ab_product"].sudo().with_context(active_test=False)
        self.Program = self.env["ab_promo_program"].sudo()
        self.env.cr.execute(
            """
                SELECT id, uom_id
                 FROM ab_product
                 WHERE eplus_serial IS NOT NULL
                   AND uom_id IS NOT NULL
                   AND active IS TRUE
                 LIMIT 4
            """
        )
        product_rows = self.env.cr.fetchall()
        if len(product_rows) < 4:
            raise SkipTest("Need at least four existing products with E-Plus serials and UoM.")
        product_ids = [row[0] for row in product_rows]
        self.product_uom_by_id = {row[0]: row[1] for row in product_rows}
        (
            self.trigger_product,
            self.reward_product,
            self.scope_product,
            self.unrelated_product,
        ) = self.Product.browse(product_ids)

    def _create_program(self, **vals):
        base_vals = {
            "name": vals.pop("name", "Promo Marker Program"),
            "apply_disc_on": vals.pop("apply_disc_on", "on_order"),
            "disc_percent": vals.pop("disc_percent", 10.0),
            "rule_min_qty": vals.pop("rule_min_qty", 1),
        }
        base_vals.update(vals)
        return self.Program.create(base_vals).with_context(active_test=False)

    def _new_header(self, products, program, description=""):
        line_commands = []
        for product in products:
            line_commands.append((0, 0, {
                "product_id": product.id,
                "qty_str": "1",
                "sell_price": 1.0,
                "uom_id": self.product_uom_by_id[product.id],
            }))
        header = self.env["ab_sales_header"].new({
            "description": description,
            "line_ids": line_commands,
            "applied_program_ids": [(6, 0, [program.id])],
        })
        header.line_ids._compute_qty()
        header.line_ids._compute_amount()
        header._compute_amounts()
        return header

    def test_specific_products_marker_scope_includes_trigger_and_reward_products(self):
        program = self._create_program(
            name="Specific Product Marker Promo",
            apply_disc_on="specific_products",
            product_ids=[(6, 0, [self.trigger_product.id])],
            disc_specific_product_ids=[(6, 0, [self.reward_product.id])],
        )
        header = self._new_header(
            [self.trigger_product, self.reward_product, self.unrelated_product],
            program,
        )

        marker_products = header._program_marker_products(program)

        self.assertEqual(set(marker_products.ids), {self.trigger_product.id, self.reward_product.id})

    def test_normal_promotion_marker_scope_uses_program_product_scope(self):
        program = self._create_program(
            name="Normal Product Marker Promo",
            apply_disc_on="cheapest_product",
            rule_min_qty=2,
            product_ids=[(6, 0, [self.trigger_product.id, self.scope_product.id])],
        )
        header = self._new_header(
            [self.trigger_product, self.scope_product, self.unrelated_product],
            program,
        )

        marker_products = header._program_marker_products(program)

        self.assertEqual(set(marker_products.ids), {self.trigger_product.id, self.scope_product.id})

    def test_incentives_marker_scope_is_empty(self):
        program = self._create_program(
            name="Incentive Marker Promo",
            apply_disc_on="incentives",
            product_ids=[(6, 0, [self.trigger_product.id, self.scope_product.id])],
        )
        header = self._new_header([self.trigger_product, self.scope_product], program)

        self.assertFalse(header._program_marker_products(program))

    def test_incentives_header_notice_has_no_marker(self):
        program = self._create_program(
            name="Incentive Header Marker Promo",
            apply_disc_on="incentives",
            product_ids=[(6, 0, [self.trigger_product.id])],
        )
        header = self._new_header([self.trigger_product], program, description="invoice note")

        self.assertEqual(header._get_sales_trans_h_notice(), "invoice note")

    def test_header_marker_matches_detail_marker_eligibility(self):
        normal_program = self._create_program(
            name="Header Detail Marker Promo",
            apply_disc_on="on_order",
            rule_products_domain="[('id', '=', %s)]" % self.trigger_product.id,
        )
        normal_header = self._new_header([self.trigger_product], normal_program)
        self.assertTrue(normal_header._program_marker_products(normal_program))
        self.assertIn("§§§", normal_header._get_sales_trans_h_notice())

        incentive_program = self._create_program(
            name="Header Detail Incentive Promo",
            apply_disc_on="incentives",
            product_ids=[(6, 0, [self.trigger_product.id])],
        )
        incentive_header = self._new_header([self.trigger_product], incentive_program)
        self.assertFalse(incentive_header._program_marker_products(incentive_program))
        self.assertNotIn("§§§", incentive_header._get_sales_trans_h_notice())
