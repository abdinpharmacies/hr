# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError


class AbSalesPosApiContract(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def pos_contract_totals(self, contract_id=None, lines=None, total_invoice_discount=0.0,
                            store_id=None, applied_program_id=None, manual_clear=False, customer_id=None):
        self._require_models("ab_sales_header", "ab_sales_line", "ab_contract")

        try:
            contract_id = int(contract_id or 0)
        except Exception:
            contract_id = 0

        if not contract_id:
            return {
                "allow_total_invoice_discount": False,
                "allow_promotions": False,
                "total_invoice_discount_source": "our_company",
                "discount": 0.0,
                "total_after_discount": 0.0,
                "cust_pay": 0.0,
                "company_pay": 0.0,
            }

        contract = self.env["ab_contract"].browse(contract_id).exists()
        if not contract:
            raise UserError(_("Invalid contract."))
        contract.check_access('read')
        contract._check_allow_promotions()
        if store_id:
            store = self.env['ab_store'].browse(int(store_id)).exists()
            if not store:
                raise UserError(_("Store is required."))
            store.check_access('read')
            allowed = self.env['ab_sales_header']._get_allowed_store_ids()
            if allowed and store.id not in allowed:
                raise UserError(_("Store %s is not allowed for sales.") % store.display_name)
            self.env['ab_sales_header']._ab_contract_validate_store_pair(contract, store)

        try:
            total_invoice_discount = max(0.0, float(total_invoice_discount or 0.0))
        except Exception:
            total_invoice_discount = 0.0

        header = self.env["ab_sales_header"].new({
            "contract_id": contract.id,
            "customer_id": customer_id or False,
            "store_id": int(store_id) if store_id else False,
            "total_invoice_discount": total_invoice_discount,
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
                "uom_id": line.get('uom_id') or False,
            })

        header.line_ids = line_records
        if line_records:
            line_records._compute_qty()
            line_records._compute_amount()
        promotion = {}
        if contract.allow_promotions and 'applied_program_ids' in header._fields and store_id:
            promotion = self.pos_promotions(
                store_id=store_id, lines=lines, applied_program_id=applied_program_id,
                manual_clear=manual_clear, contract_id=contract.id,
                total_invoice_discount=total_invoice_discount, customer_id=customer_id,
            )
            program_id = promotion.get('applied_program_id')
            header.applied_program_ids = [(6, 0, [program_id] if program_id else [])]
        header._ab_contract_recompute_lines()
        header._compute_contract_totals()

        return {
            **promotion,
            "allow_promotions": bool(contract.allow_promotions),
            "allow_total_invoice_discount": bool(contract.allow_total_invoice_discount),
            "total_invoice_discount_source": contract.total_invoice_discount_source or "our_company",
            "discount": float(header.discount or 0.0),
            "total_after_discount": float(header.total_after_discount or 0.0),
            "cust_pay": float(header.cust_pay or 0.0),
            "company_pay": float(header.company_pay or 0.0),
        }
