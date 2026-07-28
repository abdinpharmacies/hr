# -*- coding: utf-8 -*-

import logging

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from odoo.addons.ab_sales.models.ab_sales_return_header import PARAM_STR

_logger = logging.getLogger(__name__)


class AbSalesReturnHeaderRouter(models.Model):
    _inherit = "ab_sales_return_header"

    def _return_router_get_source_header(self):
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

    def _return_router_mode(self, source_header=False):
        self.ensure_one()
        source_header = source_header or self._return_router_get_source_header()
        if not source_header:
            return "original", source_header

        fields_map = getattr(source_header, "_fields", {}) or {}
        if "contract_id" in fields_map and source_header.contract_id:
            return "contract", source_header
        if "applied_program_ids" in fields_map and source_header.applied_program_ids:
            return "promo", source_header
        return "original", source_header

    @api.depends(
        "line_ids.qty",
        "line_ids.sell_price",
        "line_ids.max_returnable_qty",
        "line_ids.qty_sold_source",
        "line_ids.uom_id",
        "line_ids.source_uom_factor",
        "origin_header_id",
        "store_id",
        "total_sales_net",
    )
    def _compute_totals(self):
        super()._compute_totals()
        for rec in self:
            if rec._is_total_return_invoice():
                continue
            mode, source_header = rec._return_router_mode()
            if mode == "contract" and hasattr(rec, "_contract_return_reprice_values"):
                repriced = rec._contract_return_reprice_values()
                rec.total_return_value = float(repriced.get("refund_net") or 0.0)
            elif mode == "promo" and hasattr(rec, "_promo_return_reprice_values"):
                repriced = rec._promo_return_reprice_values()
                rec.total_return_value = float(repriced.get("refund_total") or 0.0)
            elif mode == "original" or not source_header:
                continue

    def _get_return_adjustments(self, cur, sth_id, total_value, net_return):
        self.ensure_one()
        adjustments = super()._get_return_adjustments(
            cur=cur,
            sth_id=sth_id,
            total_value=total_value,
            net_return=net_return,
        )
        if self._is_total_return_invoice():
            return adjustments

        mode, _source_header = self._return_router_mode()

        if mode == "contract" and hasattr(self, "_contract_return_reprice_values"):
            before_after_disc = False
            before_net = False
            try:
                cur.execute(
                    f"""
                        SELECT ISNULL(total_bill_after_disc, 0), ISNULL(total_bill_net, 0)
                          FROM sales_trans_h
                         WHERE sth_id = {PARAM_STR}
                    """,
                    (int(sth_id),),
                )
                row = cur.fetchone()
                if row:
                    before_after_disc = float(row[0] or 0.0)
                    before_net = float(row[1] or 0.0)
            except Exception:
                _logger.exception("Failed to read pre-return totals for contract return %s", self.id)

            repriced = self._contract_return_reprice_values(
                before_after_disc=before_after_disc,
                before_net=before_net,
            )
            refund_after_disc = float(repriced.get("refund_after_disc") or 0.0)
            refund_net = float(repriced.get("refund_net") or 0.0)
            adjustments.update(
                {
                    "total_bill_after_disc_delta": refund_after_disc,
                    "total_bill_net_delta": refund_net,
                    "fcs_current_balance_delta": refund_net,
                    "fh_value_delta": refund_net,
                    "sales_return_payment_value": -refund_net,
                }
            )
            return adjustments

        if mode == "promo" and hasattr(self, "_promo_return_reprice_values"):
            repriced = self._promo_return_reprice_values()
            refund_total = float(repriced.get("refund_total") or 0.0)
            adjustments.update(
                {
                    # "total_bill_after_disc_delta": refund_total,
                    "total_bill_net_delta": refund_total,
                    "fcs_current_balance_delta": refund_total,
                    "fh_value_delta": refund_total,
                    "sales_return_payment_value": -refund_total,
                }
            )
            return adjustments

        return adjustments

    def action_push_to_eplus_return(self):
        updates_by_id = {}
        for rec in self:
            if rec._is_total_return_invoice():
                continue
            mode, _source_header = rec._return_router_mode()
            if mode == "contract" and hasattr(rec, "_contract_return_reprice_values"):
                before_after_disc = False
                before_net = False
                conn = rec.get_connection()
                if conn and rec.origin_header_id:
                    try:
                        cur = conn.cursor()
                        cur.execute(
                            f"""
                                SELECT ISNULL(total_bill_after_disc, 0), ISNULL(total_bill_net, 0)
                                  FROM sales_trans_h
                                 WHERE sth_id = {PARAM_STR}
                            """,
                            (int(rec.origin_header_id),),
                        )
                        row = cur.fetchone()
                        if row:
                            before_after_disc = float(row[0] or 0.0)
                            before_net = float(row[1] or 0.0)
                    except Exception:
                        _logger.exception(
                            "Failed to read pre-return totals before push for contract return %s",
                            rec.id,
                        )
                repriced = rec._contract_return_reprice_values(
                    before_after_disc=before_after_disc,
                    before_net=before_net,
                )
                updates_by_id[rec.id] = float(repriced.get("refund_net") or 0.0)
            elif mode == "promo" and hasattr(rec, "_promo_return_reprice_values"):
                repriced = rec._promo_return_reprice_values()
                updates_by_id[rec.id] = float(repriced.get("refund_total") or 0.0)

        result = super().action_push_to_eplus_return()

        for rec in self:
            if rec.id not in updates_by_id:
                continue
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
                        float(updates_by_id.get(rec.id) or 0.0),
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

