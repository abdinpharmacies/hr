# -*- coding: utf-8 -*-

import logging

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class AbSalesReturnHeaderPromo(models.Model):
    _inherit = "ab_sales_return_header"

    def _promo_return_get_source_header(self):
        self.ensure_one()
        if not self.origin_header_id or not self.store_id:
            return self.env["ab_sales_header"]
        return self.env["ab_sales_header"].sudo().search(
            [
                ("eplus_serial", "=", int(self.origin_header_id)),
                ("store_id", "=", self.store_id.id),
            ],
            order="id desc",
            limit=1,
        )

    def _promo_return_get_program(self, source_header=False):
        self.ensure_one()
        source_header = source_header or self._promo_return_get_source_header()
        if not source_header:
            return self.env["ab_promo_program"]
        program = source_header.applied_program_ids.filtered(
            lambda p: source_header._program_is_effective(p)
        )[:1]
        program_id = getattr(program, "id", None)
        origin = getattr(program_id, "origin", None)
        if origin:
            program = self.env["ab_promo_program"].browse(int(origin))
        return program

    @staticmethod
    def _promo_return_qty_text(value):
        value = float(value or 0.0)
        return f"{value:.4f}".rstrip("0").rstrip(".") or "0"

    @staticmethod
    def _promo_return_default_factor(product):
        factor = float(product.uom_id.factor or 0.0) if product and product.uom_id else 0.0
        if factor <= 0.0:
            factor = 1.0
        return factor

    def _promo_return_qty_in_default_uom(self, line, qty_source):
        self.ensure_one()
        qty_source = float(qty_source or 0.0)
        if qty_source <= 0.0 or not line.product_id:
            return 0.0
        source_factor = float(line.source_uom_factor or 0.0) or 1.0
        default_factor = self._promo_return_default_factor(line.product_id)
        return qty_source * source_factor / default_factor

    def _promo_return_price_ref(self, source_header, line):
        self.ensure_one()
        if not source_header or not line.product_id:
            return 0.0
        default_factor = self._promo_return_default_factor(line.product_id)
        selected_factor = float(line.uom_id.factor or 0.0) if line.uom_id else 0.0
        if selected_factor <= 0.0:
            selected_factor = float(line.source_uom_factor or 0.0) or default_factor
        ratio = selected_factor / default_factor if default_factor > 0.0 else 1.0
        if ratio <= 0.0:
            ratio = 1.0
        return float(source_header._price_ref_from_line(line, ratio) or 0.0)

    def _promo_return_line_qty_source(self, line, mode="remaining"):
        self.ensure_one()
        sold_qty = float(line.qty_sold_source or 0.0)
        current_qty = float(line.max_returnable_source or 0.0)
        returned_qty = float(line._qty_to_source_unit() or 0.0)
        if mode == "current":
            return max(0.0, current_qty)
        if mode == "sold":
            return sold_qty
        if mode == "returned":
            return returned_qty
        return max(0.0, current_qty - returned_qty)

    def _promo_return_build_virtual_header(self, source_header, mode="remaining"):
        self.ensure_one()
        if not source_header:
            return self.env["ab_sales_header"].new({})

        line_commands = []
        for line in self.line_ids.filtered(lambda l: l.product_id and float(l.qty_sold_source or 0.0) > 0.0):
            qty_source = self._promo_return_line_qty_source(line, mode=mode)
            qty_default = self._promo_return_qty_in_default_uom(line, qty_source)
            if qty_default <= 1e-8:
                continue
            price_ref = self._promo_return_price_ref(source_header, line)
            default_uom = line.product_id.uom_id or line.uom_id
            line_commands.append(
                (0, 0, {
                    "product_id": line.product_id.id,
                    "uom_id": default_uom.id if default_uom else False,
                    "qty_str": self._promo_return_qty_text(qty_default),
                    "sell_price": price_ref,
                })
            )

        header = self.env["ab_sales_header"].new(
            {
                "store_id": source_header.store_id.id,
                "company_id": source_header.company_id.id,
                "customer_id": source_header.customer_id.id if source_header.customer_id else False,
                "line_ids": line_commands,
            }
        )
        if header.line_ids:
            header.line_ids._compute_qty()
            header.line_ids._compute_amount()
        return header

    def _promo_return_virtual_total(self, source_header, mode="remaining"):
        self.ensure_one()
        if not source_header:
            return 0.0

        virtual_header = self._promo_return_build_virtual_header(source_header, mode=mode)
        if virtual_header.line_ids:
            virtual_header._compute_amounts()

        amount_total = float(virtual_header.amount_total or 0.0)
        program = self._promo_return_get_program(source_header=source_header)
        if not program or not virtual_header.line_ids:
            return amount_total

        virtual_header.applied_program_ids = program
        virtual_header._compute_promo_totals()
        return float(virtual_header.amount_total_after_promo or amount_total or 0.0)

    def _promo_return_reprice_values(self):
        self.ensure_one()
        source_header = self._promo_return_get_source_header()
        if not source_header:
            raw_total = sum(float(line.qty or 0.0) * float(line.sell_price or 0.0) for line in self.line_ids)
            return {
                "source_header": source_header,
                "original_total": 0.0,
                "remaining_total": 0.0,
                "refund_total": raw_total,
            }

        original_total = self._promo_return_virtual_total(source_header, mode="current")
        remaining_total = self._promo_return_virtual_total(source_header, mode="remaining")
        refund_total = max(0.0, float(original_total or 0.0) - float(remaining_total or 0.0))
        return {
            "source_header": source_header,
            "original_total": float(original_total or 0.0),
            "remaining_total": float(remaining_total or 0.0),
            "refund_total": refund_total,
        }

    @api.depends(
        "line_ids.qty",
        "line_ids.sell_price",
        "line_ids.qty_sold_source",
        "line_ids.uom_id",
        "line_ids.source_uom_factor",
        "origin_header_id",
        "store_id",
    )
    def _compute_totals(self):
        super()._compute_totals()
        for rec in self:
            repriced = rec._promo_return_reprice_values()
            if repriced.get("source_header"):
                rec.total_return_value = float(repriced.get("refund_total") or 0.0)

    def _get_return_adjustments(self, cur, sth_id, total_value, net_return):
        self.ensure_one()
        adjustments = super()._get_return_adjustments(
            cur=cur,
            sth_id=sth_id,
            total_value=total_value,
            net_return=net_return,
        )
        repriced = self._promo_return_reprice_values()
        if not repriced.get("source_header"):
            return adjustments

        refund_total = float(repriced.get("refund_total") or 0.0)
        adjustments.update(
            {
                "total_bill_after_disc_delta": refund_total,
                "total_bill_net_delta": refund_total,
                "fcs_current_balance_delta": refund_total,
                "fh_value_delta": refund_total,
                "sales_return_payment_value": -refund_total,
            }
        )
        return adjustments

    def action_push_to_eplus_return(self):
        repriced_by_id = {}
        for rec in self:
            repriced_by_id[rec.id] = rec._promo_return_reprice_values()

        result = super().action_push_to_eplus_return()

        for rec in self:
            refund_total = float((repriced_by_id.get(rec.id) or {}).get("refund_total") or 0.0)
            if not rec.sales_return_id:
                continue
            conn = rec.get_connection()
            if not conn:
                continue
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                        UPDATE sales_return
                           SET returned_items_value = ?
                         WHERE sr_id = ?
                    """,
                    (
                        refund_total,
                        int(rec.sales_return_id),
                    ),
                )
                conn.commit()
            except Exception as exc:
                _logger.exception("Failed to update sales_return.returned_items_value for return %s", rec.id)
                raise UserError(
                    _(
                        "Return was saved, but updating sales_return.returned_items_value failed: %s"
                    ) % str(exc)
                )

        return result
