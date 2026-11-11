# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class AbTransferRequestReport(models.Model):
    _name = "ab_transfer_request_report"
    _description = "Transfer Request Report"
    _auto = False
    _order = "request_date desc, request_id desc"
    _rec_name = "request_id"

    request_id = fields.Many2one(
        "ab_transfer_request",
        string="Transfer Request",
        readonly=True,
    )
    request_date = fields.Datetime(
        string="Request Date",
        readonly=True,
    )
    requesting_store_id = fields.Many2one(
        "ab_store",
        string="Requesting Store",
        readonly=True,
    )
    requested_by_id = fields.Many2one(
        "ab_costcenter",
        string="Requested By",
        readonly=True,
    )
    request_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        string="Request Status",
        readonly=True,
    )
    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        readonly=True,
    )
    requested_qty = fields.Float(
        string="Requested Quantity",
        readonly=True,
        digits=(16, 3),
        aggregator="sum",
    )
    transferred_qty = fields.Float(
        string="Transferred Quantity",
        readonly=True,
        digits=(16, 3),
        aggregator="sum",
    )
    remaining_qty = fields.Float(
        string="Remaining Quantity",
        readonly=True,
        digits=(16, 3),
        aggregator="sum",
    )
    execution_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("partially_executed", "Partially Executed"),
            ("fully_executed", "Fully Executed"),
        ],
        string="Execution Status",
        readonly=True,
    )
    related_transfer_id = fields.Many2one(
        "ab_transfer_header",
        string="Related Transfer",
        readonly=True,
    )
    transfer_date = fields.Datetime(
        string="Transfer Date",
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
    )

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                WITH request_product AS (
                    SELECT
                        MIN(line.id) AS id,
                        request.id AS request_id,
                        request.create_date AS request_date,
                        request.from_store_id AS requesting_store_id,
                        request.user_id AS requested_by_id,
                        request.state AS request_state,
                        line.product_id AS product_id,
                        SUM(line.requested_qty) AS requested_qty,
                        request.company_id AS company_id
                    FROM ab_transfer_request_line line
                    INNER JOIN ab_transfer_request request ON request.id = line.request_id
                    GROUP BY
                        request.id,
                        request.create_date,
                        request.from_store_id,
                        request.user_id,
                        request.state,
                        line.product_id,
                        request.company_id
                ),
                submitted_transfer AS (
                    SELECT
                        header.transfer_request_id AS request_id,
                        line.product_id AS product_id,
                        SUM(line.qty) AS transferred_qty,
                        (ARRAY_AGG(header.id ORDER BY header.sent_at DESC NULLS LAST, header.id DESC))[1] AS related_transfer_id,
                        MAX(header.sent_at) AS transfer_date
                    FROM ab_transfer_line line
                    INNER JOIN ab_transfer_header header ON header.id = line.header_id
                    WHERE header.transfer_request_id IS NOT NULL
                      AND header.is_submitted IS TRUE
                      AND header.selection = 'saved'
                    GROUP BY
                        header.transfer_request_id,
                        line.product_id
                )
                SELECT
                    request_product.id AS id,
                    request_product.request_id AS request_id,
                    request_product.request_date AS request_date,
                    request_product.requesting_store_id AS requesting_store_id,
                    request_product.requested_by_id AS requested_by_id,
                    request_product.request_state AS request_state,
                    request_product.product_id AS product_id,
                    request_product.requested_qty AS requested_qty,
                    COALESCE(submitted_transfer.transferred_qty, 0.0) AS transferred_qty,
                    request_product.requested_qty - COALESCE(submitted_transfer.transferred_qty, 0.0) AS remaining_qty,
                    CASE
                        WHEN COALESCE(submitted_transfer.transferred_qty, 0.0) <= 0.0 THEN 'pending'
                        WHEN COALESCE(submitted_transfer.transferred_qty, 0.0) < request_product.requested_qty THEN 'partially_executed'
                        ELSE 'fully_executed'
                    END AS execution_status,
                    submitted_transfer.related_transfer_id AS related_transfer_id,
                    submitted_transfer.transfer_date AS transfer_date,
                    request_product.company_id AS company_id
                FROM request_product
                LEFT JOIN submitted_transfer
                    ON submitted_transfer.request_id = request_product.request_id
                   AND submitted_transfer.product_id = request_product.product_id
            )
            """ % self._table
        )
