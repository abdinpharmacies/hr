from odoo.tests.common import TransactionCase


class TestUnavailableReasonRequired(TransactionCase):
    def setUp(self):
        super().setUp()

        self.store = self.env["ab_store"].sudo().create({
            "name": "Test Store",
            "code": "TST",
        })

        self.uom_category = self.env["ab_product_uom_category"].sudo().create({
            "name": "Test Category",
        })
        self.base_uom = self.env["ab_product_uom"].sudo().create({
            "name": "Box",
            "category_id": self.uom_category.id,
            "factor": 12.0,
        })
        self.alt_uom = self.env["ab_product_uom"].sudo().create({
            "name": "Pack",
            "category_id": self.uom_category.id,
            "factor": 24.0,
        })

        self.product_card = self.env["ab_product_card"].sudo().create({
            "name": "Test Product",
        })
        self.product = self.env["ab_product"].sudo().create({
            "product_card_id": self.product_card.id,
            "code": "P-001",
            "uom_category_id": self.uom_category.id,
            "uom_id": self.base_uom.id,
        })

    def test_unavailable_reason_check_uses_uom_conversion(self):
        header = self.env["ab_sales_header"].sudo().create({
            "store_id": self.store.id,
        })
        line = self.env["ab_sales_line"].sudo().create({
            "header_id": header.id,
            "product_id": self.product.id,
            "qty_str": "2",
            "uom_id": self.alt_uom.id,
            "inventory_json": {
                "data": [
                    {
                        "qty": 3.0,
                        "price": 1.0,
                        "cost": 1.0,
                    }
                ]
            },
        })

        missing_lines = header._unavailable_lines_missing_reason()
        self.assertEqual(missing_lines.ids, line.ids)

        line.write({
            "unavailable_reason": "not_transferred",
            "unavailable_reason_other": "",
        })
        self.assertFalse(header._unavailable_lines_missing_reason())
