# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestAbSalesLead(TransactionCase):
    def setUp(self):
        super().setUp()
        self.store = self.env["ab_store"].sudo().create({
            "name": "Lead Test Store",
            "code": "LTS",
        })
        self.uom_category = self.env["ab_product_uom_category"].sudo().create({
            "name": "Lead Test Category",
        })
        self.uom = self.env["ab_product_uom"].sudo().create({
            "name": "Unit",
            "category_id": self.uom_category.id,
            "factor": 1.0,
        })
        self.product_card = self.env["ab_product_card"].sudo().create({
            "name": "Lead Test Product",
        })
        self.product = self.env["ab_product"].sudo().create({
            "product_card_id": self.product_card.id,
            "code": "LEAD-001",
            "eplus_serial": 990001,
            "uom_category_id": self.uom_category.id,
            "uom_id": self.uom.id,
            "default_price": 15.0,
        })

    def test_special_order_requires_customer_phone(self):
        with self.assertRaises(ValidationError):
            self.env["ab_sales_lead"].sudo().create({
                "lead_type": "special_order",
                "product_id": self.product.id,
                "quantity": 1.0,
            })

    def test_pos_create_lost_sales_lead(self):
        result = self.env["ab_sales_lead"].pos_create_lead({
            "lead_type": "lost_sales",
            "product_id": self.product.id,
            "product_name": "Lead Test Product",
            "product_code": "LEAD-001",
            "store_id": self.store.id,
            "quantity": 2.0,
            "lost_reason": "not_available",
            "notes": "Customer asked for unavailable product.",
        })

        lead = self.env["ab_sales_lead"].browse(result["id"])
        self.assertEqual(lead.source, "pos")
        self.assertEqual(lead.lead_type, "lost_sales")
        self.assertEqual(lead.product_id, self.product)
        self.assertEqual(lead.store_id, self.store)
        self.assertEqual(lead.quantity, 2.0)

    def test_base_user_can_create_but_not_write_lead(self):
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Lead POS User",
            "login": "lead_pos_user",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })

        lead = self.env["ab_sales_lead"].with_user(user).create({
            "lead_type": "lost_sales",
            "product_id": self.product.id,
            "quantity": 1.0,
            "lost_reason": "not_available",
        })
        self.assertTrue(lead.with_user(user).read(["id"]))
        with self.assertRaises(AccessError):
            lead.with_user(user).write({"notes": "Updated by cashier."})

    def test_pos_item_report_uses_inventory_and_last_30_days_sales(self):
        other_store = self.env["ab_store"].sudo().create({
            "name": "Lead Other Store",
            "code": "LOS",
        })
        today = fields.Date.context_today(self.env["ab_sales_lead"])

        Inventory = self.env["ab_sales_inventory"].sudo()
        Inventory.create({
            "product_eplus_serial": self.product.eplus_serial,
            "store_id": self.store.id,
            "balance": 0.0,
        })
        Inventory.create({
            "product_eplus_serial": self.product.eplus_serial,
            "store_id": other_store.id,
            "balance": 12.0,
        })

        SalesPerDay = self.env["ab_sales_per_day"].sudo()
        SalesPerDay.create({
            "store_id": self.store.id,
            "product_eplus_serial": self.product.eplus_serial,
            "product_id": self.product.id,
            "sale_date": today - timedelta(days=2),
            "sales_qty": 5.0,
        })
        SalesPerDay.create({
            "store_id": other_store.id,
            "product_eplus_serial": self.product.eplus_serial,
            "product_id": self.product.id,
            "sale_date": today - timedelta(days=5),
            "sales_qty": 2.0,
        })
        SalesPerDay.create({
            "store_id": other_store.id,
            "product_eplus_serial": self.product.eplus_serial,
            "product_id": self.product.id,
            "sale_date": today - timedelta(days=45),
            "sales_qty": 100.0,
        })

        result = self.env["ab_sales_lead"].pos_item_report(self.product.id)
        rows = result["rows"]

        self.assertEqual([row["store_id"] for row in rows], [other_store.id, self.store.id])
        self.assertEqual(rows[0]["balance"], 12.0)
        self.assertEqual(rows[0]["last_30_days_sales"], 2.0)
        self.assertEqual(rows[1]["balance"], 0.0)
        self.assertEqual(rows[1]["last_30_days_sales"], 5.0)
        self.assertEqual(result["total_balance"], 12.0)
        self.assertEqual(result["total_last_30_days_sales"], 7.0)
