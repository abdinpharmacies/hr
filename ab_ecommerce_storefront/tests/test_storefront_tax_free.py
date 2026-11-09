from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestStorefrontTaxFree(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref("website.default_website")
        cls.company = cls.website.company_id
        cls.partner = cls.env["res.partner"].create({"name": "Tax-free checkout customer"})
        cls.tax = cls.env["account.tax"].create({
            "name": "Checkout tax", "amount": 14,
            "type_tax_use": "sale", "company_id": cls.company.id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Tax-free checkout product", "list_price": 250,
            "taxes_id": [Command.set(cls.tax.ids)],
        })

    def test_website_order_uses_product_price_without_tax(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "website_id": self.website.id,
            "company_id": self.company.id,
            "order_line": [Command.create({
                "product_id": self.product.id, "product_uom_qty": 1,
            })],
        })
        line = order.order_line
        line._reset_price_unit()
        self.assertFalse(line.tax_ids)
        line.write({"tax_ids": [Command.set(self.tax.ids)]})
        self.assertFalse(line.tax_ids)
        self.assertEqual(line.price_unit, 250)
        self.assertEqual(order.amount_tax, 0)
        self.assertEqual(order.amount_total, 250)
        self.assertEqual(self.product.product_tmpl_id._apply_taxes_to_price(
            250, order.currency_id, self.tax, self.tax,
            self.product.product_tmpl_id, website=self.website,
        ), 250)

    def test_backend_order_keeps_product_tax(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "order_line": [Command.create({
                "product_id": self.product.id, "product_uom_qty": 1,
            })],
        })
        order.web_read({"id": {}, "tax_totals": {}})
        self.assertEqual(order.order_line.tax_ids, self.tax)
        self.assertGreater(order.amount_tax, 0)

    def test_existing_draft_website_order_clears_saved_tax(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "price_unit": 250,
                "product_uom_qty": 1,
            })],
        })
        self.assertEqual(order.order_line.tax_ids, self.tax)
        order.website_id = self.website
        order.web_read({
            "id": {}, "tax_totals": {},
        })
        self.assertFalse(order.order_line.tax_ids)
        self.assertEqual(order.amount_tax, 0)
        self.assertEqual(order.amount_total, 250)
