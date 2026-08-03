import base64

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestAbSalesSpecificPromo(TransactionCase):
    def setUp(self):
        super().setUp()
        self.uom_category = self.env["ab_product_uom_category"].sudo().create({
            "name": "Promo Unit",
            "active": True,
        })
        self.uom = self.env["ab_product_uom"].sudo().create({
            "name": "Unit",
            "category_id": self.uom_category.id,
            "factor": 1.0,
        })
        self.store = self.env["ab_store"].sudo().create({
            "name": "Promo Test Store",
            "code": "PROMO-TST",
        })
        trigger_card = self.env["ab_product_card"].sudo().create({"name": "Promo Trigger"})
        discount_card = self.env["ab_product_card"].sudo().create({"name": "Promo Discount"})
        self.trigger_product = self.env["ab_product"].sudo().create({
            "product_card_id": trigger_card.id,
            "code": "PROMO-TRG",
            "default_price": 10.0,
            "uom_category_id": self.uom_category.id,
            "uom_id": self.uom.id,
        })
        self.discount_product = self.env["ab_product"].sudo().create({
            "product_card_id": discount_card.id,
            "code": "PROMO-DSC",
            "default_price": 2.0,
            "uom_category_id": self.uom_category.id,
            "uom_id": self.uom.id,
        })
        self.program = self.env["ab_promo_program"].sudo().create({
            "name": "Specific Product Promo",
            "apply_disc_on": "specific_products",
            "rule_min_qty": 2,
            "disc_percent": 50.0,
            "product_ids": [(6, 0, [self.trigger_product.id])],
            "disc_specific_product_ids": [(6, 0, [self.discount_product.id])],
            "approval_email_attachment": base64.b64encode(b"approval email"),
            "approval_email_attachment_filename": "approval_email.eml",
        })

    def _new_header(self, products):
        line_commands = []
        for product, price in products:
            line_commands.append((0, 0, {
                "product_id": product.id,
                "qty_str": "1",
                "sell_price": price,
                "uom_id": self.uom.id,
            }))
        header = self.env["ab_sales_header"].new({
            "store_id": self.store.id,
            "line_ids": line_commands,
            "applied_program_ids": [(6, 0, [self.program.id])],
        })
        header.line_ids._compute_qty()
        header.line_ids._compute_amount()
        header._compute_amounts()
        return header

    def test_specific_products_counts_trigger_and_discount_products_for_min_qty(self):
        header = self._new_header([
            (self.trigger_product, 10.0),
            (self.discount_product, 2.0),
        ])

        header._compute_promo_totals()

        self.assertTrue(header._specific_products_meets_min_qty(self.program))
        self.assertAlmostEqual(header.promo_discount_amount, 1.0, places=2)
        self.assertAlmostEqual(header.amount_total_after_promo, 11.0, places=2)

    def test_specific_products_discounts_only_one_discount_product(self):
        header = self._new_header([
            (self.trigger_product, 10.0),
            (self.discount_product, 2.0),
            (self.discount_product, 2.0),
        ])

        header._compute_promo_totals()

        self.assertTrue(header._specific_products_meets_min_qty(self.program))
        self.assertAlmostEqual(header.promo_discount_amount, 1.0, places=2)
        self.assertAlmostEqual(header.amount_total_after_promo, 13.0, places=2)

    def test_specific_products_still_requires_min_qty(self):
        header = self._new_header([
            (self.discount_product, 2.0),
        ])

        header._compute_promo_totals()

        self.assertFalse(header._specific_products_meets_min_qty(self.program))
        self.assertAlmostEqual(header.promo_discount_amount, 0.0, places=2)
        with self.assertRaises(ValidationError):
            header._apply_promotion_to_lines()
