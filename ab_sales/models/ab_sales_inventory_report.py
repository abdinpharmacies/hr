# -*- coding: utf-8 -*-

import re

from odoo import fields, models, tools


class AbSalesInventoryReport(models.Model):
    _name = "ab_sales_inventory_report"
    _description = "Sales Inventory Report"
    _auto = False
    _order = "product_code, store_code, id"
    _rec_name = "product_code"

    product_eplus_serial = fields.Integer(
        string="Product ePlus Serial",
        readonly=True,
    )
    product_codes_search = fields.Char(
        string="Product Codes",
        compute="_compute_product_codes_search",
        search="_search_product_codes_search",
    )
    product_code = fields.Char(
        string="Product Code",
        readonly=True,
    )
    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        readonly=True,
    )
    store_code = fields.Char(
        string="Store Code",
        readonly=True,
    )
    store_id = fields.Many2one(
        "ab_store",
        string="Store",
        readonly=True,
    )
    balance = fields.Float(
        string="Balance",
        readonly=True,
        aggregator="sum",
    )
    default_price = fields.Float(
        string="Default Price",
        readonly=True,
        aggregator="avg",
    )

    def _compute_product_codes_search(self):
        for rec in self:
            rec.product_codes_search = False

    def _search_product_codes_search(self, operator, value):
        tokens = [
            token
            for token in re.split(r"[\s,]+", str(value or "").strip())
            if token
        ]
        if not tokens:
            return []
        conditions = [("product_code", "=ilike", token) for token in tokens]
        if len(conditions) == 1:
            return conditions
        return ["|"] * (len(conditions) - 1) + conditions

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    inventory.id AS id,
                    inventory.product_eplus_serial AS product_eplus_serial,
                    inventory.product_code AS product_code,
                    inventory.product_id AS product_id,
                    store.code AS store_code,
                    inventory.store_id AS store_id,
                    inventory.balance AS balance,
                    inventory.default_price AS default_price
                FROM ab_sales_inventory inventory
                LEFT JOIN ab_store store
                    ON store.id = inventory.store_id
            )
            """
            % self._table
        )
