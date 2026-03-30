import logging

from odoo import models

from odoo.addons.ab_sales.models.ab_sales_return_header import PARAM_STR

_logger = logging.getLogger(__name__)


class AbSalesReturnHeaderContract(models.Model):
    _inherit = "ab_sales_return_header"

    @staticmethod
    def _ab_clamp_discount_pct(discount_pct):
        try:
            value = float(discount_pct or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        return max(0.0, min(100.0, value))

    def _get_return_adjustments(self, cur, sth_id, total_value, net_return):
        adjustments = super()._get_return_adjustments(
            cur=cur,
            sth_id=sth_id,
            total_value=total_value,
            net_return=net_return,
        )
        self.ensure_one()

        try:
            cur.execute(
                f"""
                    SELECT
                        ISNULL(fh_contract_id, 0),
                        ISNULL(total_bill_after_disc, 0),
                        ISNULL(total_bill_net, 0)
                    FROM sales_trans_h
                    WHERE sth_id = {PARAM_STR}
                """,
                (int(sth_id),),
            )
            header_row = cur.fetchone()
            if not header_row:
                return adjustments

            fh_contract_id = int(header_row[0] or 0)
            total_bill_after_disc = float(header_row[1] or 0.0)
            total_bill_net = float(header_row[2] or 0.0)
            if not fh_contract_id:
                return adjustments

            cur.execute(
                f"""
                    SELECT std_id, ISNULL(itm_dis_per, 0)
                    FROM sales_trans_d
                    WHERE sth_id = {PARAM_STR}
                """,
                (int(sth_id),),
            )
            discount_by_std = {
                int(std_id): self._ab_clamp_discount_pct(dis_per)
                for std_id, dis_per in cur.fetchall()
                if std_id is not None
            }

            total_after_discount_return = 0.0
            total_sold_qty = 0.0
            total_return_qty = 0.0
            for line in self.line_ids:
                sold_qty = float(line.qty_sold_source or line._qty_to_source_unit(line.qty_sold or 0.0))
                back_qty = float(line._qty_to_source_unit() or 0.0)
                total_sold_qty += sold_qty
                total_return_qty += back_qty
                if back_qty <= 0.0:
                    continue

                line_gross = back_qty * float(line._price_to_source_unit(line.sell_price or 0.0))
                discount_pct = discount_by_std.get(int(line.std_id or 0), 0.0)
                line_after_discount = line_gross * (1.0 - (discount_pct / 100.0))
                total_after_discount_return += line_after_discount

            cash_delta = total_after_discount_return
            if total_bill_after_disc > 0.0:
                liability_ratio = max(0.0, total_bill_net / total_bill_after_disc)
                cash_delta = total_after_discount_return * liability_ratio

            if abs(total_return_qty - total_sold_qty) < 0.01:
                cash_delta = total_bill_net

            adjustments.update({
                "total_bill_after_disc_delta": max(0.0, total_after_discount_return),
                "total_bill_net_delta": max(0.0, cash_delta),
                "fcs_current_balance_delta": max(0.0, cash_delta),
                "fh_value_delta": max(0.0, cash_delta),
                "sales_return_payment_value": -max(0.0, cash_delta),
            })
        except Exception as ex:
            _logger.warning("Contract return adjustments fallback to defaults: %s", repr(ex))

        return adjustments
