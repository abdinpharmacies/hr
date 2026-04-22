# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AbSalesHeaderTotalInvoiceDiscount(models.Model):
    _inherit = "ab_sales_header"

    contract_allow_total_invoice_discount = fields.Boolean(
        related="contract_id.allow_total_invoice_discount",
        readonly=True,
    )
    total_invoice_discount = fields.Float(string="Total Invoice Discount", default=0.0)

    def _ab_contract_has_customer_contribution(self):
        self.ensure_one()
        contract = self.contract_id
        if not contract:
            return False
        return float(contract.paid_percentage or 0.0) > 0.0 or float(contract.paid_amount or 0.0) > 0.0

    def _ab_contract_get_effective_total_invoice_discount(self, total_after_discount=0.0, cust_pay=0.0):
        self.ensure_one()
        if not self.contract_id or not self.contract_id.allow_total_invoice_discount:
            return 0.0

        discount_value = max(0.0, float(self.total_invoice_discount or 0.0))
        if not discount_value:
            return 0.0

        total_cap = max(0.0, float(total_after_discount or 0.0))
        if not self._ab_contract_has_customer_contribution():
            return min(discount_value, total_cap)

        customer_cap = max(0.0, float(cust_pay or 0.0))
        if customer_cap:
            return min(discount_value, customer_cap)
        return min(discount_value, total_cap)

    def _ab_contract_apply_total_invoice_discount(self, total_after_discount, cust_pay, company_pay):
        self.ensure_one()
        effective_discount = self._ab_contract_get_effective_total_invoice_discount(
            total_after_discount=total_after_discount,
            cust_pay=cust_pay,
        )
        if not effective_discount:
            return total_after_discount, cust_pay, company_pay

        adjusted_total = max(0.0, float(total_after_discount or 0.0) - effective_discount)
        if not self._ab_contract_has_customer_contribution():
            return adjusted_total, float(cust_pay or 0.0), float(company_pay or 0.0)

        adjusted_cust_pay = max(0.0, float(cust_pay or 0.0) - effective_discount)
        return adjusted_total, adjusted_cust_pay, float(company_pay or 0.0)

    @api.onchange("contract_id")
    def _onchange_contract_id(self):
        res = super()._onchange_contract_id()
        if not self.contract_id or not self.contract_id.allow_total_invoice_discount:
            self.total_invoice_discount = 0.0
        return res

    @api.onchange("total_invoice_discount")
    def _onchange_total_invoice_discount(self):
        if self.total_invoice_discount and self.total_invoice_discount < 0.0:
            self.total_invoice_discount = 0.0

    @api.depends(
        "contract_id",
        "contract_id.max_bill_value",
        "line_ids.ab_contract_discount_amount",
        "line_ids.ab_contract_net_amount",
        "line_ids.ab_customer_amount",
        "line_ids.ab_company_amount",
        "line_ids.qty",
        "line_ids.sell_price",
        "total_invoice_discount",
        "contract_id.allow_total_invoice_discount",
    )
    def _compute_contract_totals(self):
        super()._compute_contract_totals()
        for rec in self.filtered("contract_id"):
            total_after_discount, cust_pay, company_pay = rec._ab_contract_apply_total_invoice_discount(
                rec.total_after_discount,
                rec.cust_pay,
                rec.company_pay,
            )
            rec.total_after_discount = total_after_discount
            rec.cust_pay = cust_pay
            rec.company_pay = company_pay

    def _compute_header_numbers(self, cur=None):
        totals = super()._compute_header_numbers(cur=cur)
        if not self.contract_id:
            return totals

        invoice_discount = self._ab_contract_get_effective_total_invoice_discount(
            total_after_discount=totals.get("total_bill_after_disc", 0.0),
            cust_pay=totals.get("total_bill_net", 0.0),
        )
        if not invoice_discount:
            return totals

        totals["total_bill_after_disc"] = self._to_2dec(
            max(0.0, float(totals.get("total_bill_after_disc", 0.0)) - invoice_discount)
        )
        if self._ab_contract_has_customer_contribution():
            totals["total_bill_net"] = self._to_2dec(
                max(0.0, float(totals.get("total_bill_net", 0.0)) - invoice_discount)
            )
        return totals
