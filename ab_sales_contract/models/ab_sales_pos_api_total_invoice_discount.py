# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError


class AbSalesPosApiTotalInvoiceDiscount(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def pos_contract_totals(self, contract_id=None, lines=None, total_invoice_discount=0.0):
        self._require_models("ab_sales_header", "ab_sales_line", "ab_contract")

        try:
            contract_id = int(contract_id or 0)
        except Exception:
            contract_id = 0

        if not contract_id:
            return {
                "discount": 0.0,
                "total_after_discount": 0.0,
                "cust_pay": 0.0,
                "company_pay": 0.0,
                "allow_total_invoice_discount": False,
            }

        contract = self.env["ab_contract"].browse(contract_id).exists()
        if not contract:
            raise UserError(_("Invalid contract."))

        header = self.env["ab_sales_header"].new({
            "contract_id": contract.id,
            "total_invoice_discount": float(total_invoice_discount or 0.0),
        })

        line_records = self.env["ab_sales_line"].browse()
        for line in lines or []:
            product_id = line.get("product_id")
            if not product_id:
                continue
            qty_str = line.get("qty_str") or str(line.get("qty") or 1)
            try:
                qty_str = str(qty_str)
            except Exception:
                qty_str = "1"
            try:
                sell_price = float(line.get("sell_price") or 0.0)
            except Exception:
                sell_price = 0.0
            line_records |= self.env["ab_sales_line"].new({
                "header_id": header,
                "product_id": int(product_id),
                "qty_str": qty_str,
                "sell_price": sell_price,
            })

        header.line_ids = line_records
        if line_records:
            line_records._compute_qty()
        header._ab_contract_recompute_lines()
        header._compute_contract_totals()

        return {
            "discount": float(header.discount or 0.0),
            "total_after_discount": float(header.total_after_discount or 0.0),
            "cust_pay": float(header.cust_pay or 0.0),
            "company_pay": float(header.company_pay or 0.0),
            "allow_total_invoice_discount": bool(contract.allow_total_invoice_discount),
        }
