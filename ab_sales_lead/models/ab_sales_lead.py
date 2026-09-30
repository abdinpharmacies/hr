# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbSalesLead(models.Model):
    _name = "ab_sales_lead"
    _inherit = "ab_odoo_sync_passive_mirror_mixin"
    _description = "Sales Lead"
    _order = "create_date desc, id desc"

    lead_type = fields.Selection(
        selection=[
            ("lost_sales", "Lost Sale"),
            ("special_order", "Special Order"),
        ],

        default="lost_sales",
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("new", "New"),
            ("in_review", "In Review"),
            ("contacted", "Contacted"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],

        default="new",
        index=True,
    )
    source = fields.Selection(
        selection=[
            ("pos", "POS"),
            ("manual", "Manual"),
        ],

        default="manual",
        index=True,
    )

    product_id = fields.Many2one("ab_product", index=True, ondelete="restrict")
    product_name = fields.Char(index=True)
    product_code = fields.Char(index=True)
    store_id = fields.Many2one("ab_store", index=True, ondelete="set null")
    user_id = fields.Many2one(
        "ab_users",
        default=lambda self: self.env["ab_users"].current_placeholder_id(),
        index=True,
        ondelete="restrict",
    )

    customer_id = fields.Many2one("ab_customer", index=True, ondelete="set null")
    customer_name = fields.Char(index=True)
    customer_phone = fields.Char(index=True)
    customer_address = fields.Char()

    quantity = fields.Float(default=1.0)
    default_price = fields.Float(digits=(16, 2))
    total_balance = fields.Float(string="Total Balance")
    pos_balance = fields.Float(string="POS Store Balance")
    pos_search_query = fields.Char()
    pos_client_token = fields.Char(index=True)

    lost_reason = fields.Selection(
        selection=[
            ("not_available", "Product not available"),
            ("insufficient_quantity", "Insufficient quantity"),
            ("price_too_high", "Price too high"),
            ("customer_found_alternative", "Customer found alternative"),
            ("customer_refused_wait", "Customer refused to wait"),
            ("missing_product_info", "Missing product information"),
            ("other", "Other"),
        ],
    )
    needed_date = fields.Date()
    contact_preference = fields.Selection(
        selection=[
            ("phone", "Phone"),
            ("whatsapp", "WhatsApp"),
            ("in_store", "In Store"),
        ],
        default="phone",
    )
    notes = fields.Text()
    company_action_note = fields.Text()
