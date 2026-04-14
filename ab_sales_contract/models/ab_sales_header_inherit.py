import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.ab_sales.models.ab_sales_header import PARAM_STR


class AbSalesHeaderContract(models.Model):
    _inherit = "ab_sales_header"

    _logger = logging.getLogger(__name__)

    contract_id = fields.Many2one("ab_contract", string="Contract")

    # Stored totals for clarity on the header.
    discount = fields.Float(
        string="Total Discount",
        compute="_compute_contract_totals",
        store=True,
        readonly=True,
    )
    total_after_discount = fields.Float(
        string="Total After Discount",
        compute="_compute_contract_totals",
        store=True,
        readonly=True,
    )
    cust_pay = fields.Float(
        string="Customer Pay",
        compute="_compute_contract_totals",
        readonly=True,
    )
    company_pay = fields.Float(
        string="Company Pay",
        compute="_compute_contract_totals",
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Contract validation
    # -------------------------------------------------------------------------
    def _ab_contract_validate(self):
        missing_contract_serials = set()
        for rec in self:
            contract = rec.contract_id
            if contract:
                if not contract.active:
                    raise ValidationError(_("The selected contract is not active."))
                continue
            customer_serial = rec.customer_id.eplus_serial
            if customer_serial:
                missing_contract_serials.add(str(customer_serial))

        if missing_contract_serials:
            has_contract = self.env["ab_contract"].sudo().search(
                [("eplus_cust_id", "in", list(missing_contract_serials))],
                limit=1,
            )
            if has_contract:
                raise ValidationError(_("Please choose contract from contract field not customer field"))

    @api.constrains('contract_id', 'customer_id')
    def _check_ab_contract_allowed(self):
        self._ab_contract_validate()

    # -------------------------------------------------------------------------
    # Pricing recomputation (header + lines)
    # -------------------------------------------------------------------------
    def _ab_contract_recompute_lines(self):
        """
        Update stored contract pricing fields on lines whenever contract/customer/line inputs change.

        This is invoked from:
        - header onchange(contract/customer)
        - line onchange(product/qty/price)
        - line create/write (see `ab_sales_line_inherit`)
        """
        for header in self:
            header._ab_contract_recompute_lines_single()

    def _ab_contract_recompute_lines_single(self):
        self.ensure_one()
        header = self

        contract = header.contract_id
        if not contract:
            for line in header.line_ids:
                gross = float(line.qty or 0.0) * float(line.sell_price or 0.0)
                line.with_context(ab_skip_contract_pricing=True).write({
                    "discount": 0.0,
                    "ab_contract_discount_source": "none",
                    "ab_contract_copay_mode": False,
                    "ab_contract_copay_percent": 0.0,
                    "ab_contract_gross_amount": gross,
                    "ab_contract_discount_amount": 0.0,
                    "ab_contract_net_amount": gross,
                    "ab_customer_amount": 0.0,
                    "ab_company_amount": 0.0,
                }) if line.id else line.update({
                    "discount": 0.0,
                    "ab_contract_discount_source": "none",
                    "ab_contract_copay_mode": False,
                    "ab_contract_copay_percent": 0.0,
                    "ab_contract_gross_amount": gross,
                    "ab_contract_discount_amount": 0.0,
                    "ab_contract_net_amount": gross,
                    "ab_customer_amount": 0.0,
                    "ab_company_amount": 0.0,
                })
            return

        header._ab_contract_validate()
        discount_rule = header.contract_id.discount_percentage_rule

        # 1) Resolve discount percent per line (contract table -> origin defaults -> 0).
        line_data = []
        for line in header.line_ids:
            gross = float(line.qty or 0.0) * float(line.sell_price or 0.0)
            discount_pct, discount_source = line._ab_contract_get_discount_percent(contract)
            discount_pct = max(0.0, min(100.0, float(discount_pct or 0.0)))
            line_data.append({
                "line": line,
                "gross": gross,
                "discount_pct": discount_pct,
                "discount_source": discount_source,
            })

        paid_percentage = float(contract.paid_percentage or 0.0)
        paid_amount = float(contract.paid_amount or 0.0)

        # 2) Determine effective copay percent (based on gross).
        if paid_percentage > 0.0:
            effective_copay_pct = max(0.0, min(100.0, paid_percentage))
            copay_source = "percentage"
        elif paid_amount > 0.0:
            # Convert "fixed copay amount" into an effective percentage based on the current header lines.
            basis_total = 0.0
            for d in line_data:
                basis_total += d["gross"]
            effective_copay_pct = 0.0 if basis_total <= 0.0 else min(100.0,
                                                                     max(0.0, (paid_amount / basis_total) * 100.0))
            copay_source = "amount"
        else:
            effective_copay_pct = 0.0
            copay_source = "none"

        # 3) Apply per-line pricing.
        for d in line_data:
            line = d["line"]
            gross = d["gross"]
            discount_pct = d["discount_pct"]

            # Discount always applied on gross
            discount_amount = gross * (discount_pct / 100.0)
            net = gross - discount_amount

            base_customer = gross * (effective_copay_pct / 100.0)
            base_company = gross - base_customer

            if discount_rule == "person":
                customer_amount = max(0.0, base_customer - discount_amount)
                customer_amount = min(net, customer_amount)
                company_amount = net - customer_amount
            elif discount_rule == "all":
                if copay_source == "percentage" and gross > 0.0:
                    customer_discount = discount_amount * (base_customer / gross)
                    customer_amount = max(0.0, base_customer - customer_discount)
                    customer_amount = min(net, customer_amount)
                    company_amount = net - customer_amount
                else:
                    company_amount = max(0.0, base_company - discount_amount)
                    company_amount = min(net, company_amount)
                    customer_amount = net - company_amount
            else:
                company_amount = max(0.0, base_company - discount_amount)
                company_amount = min(net, company_amount)
                customer_amount = net - company_amount

            vals = {
                "discount": discount_pct,
                "ab_contract_discount_source": d["discount_source"],
                "ab_contract_copay_mode": False,
                "ab_contract_copay_percent": effective_copay_pct,
                "ab_contract_gross_amount": gross,
                "ab_contract_discount_amount": discount_amount,
                "ab_contract_net_amount": net,
                "ab_customer_amount": customer_amount,
                "ab_company_amount": company_amount,
            }

            if line.id:
                line.with_context(ab_skip_contract_pricing=True).write(vals)
            else:
                line.update(vals)

        header.check_total_bill_vs_cust_pay()

    @api.onchange("contract_id")
    def _onchange_contract_id(self):
        self._ab_contract_recompute_lines()

    # -------------------------------------------------------------------------
    # Totals
    # -------------------------------------------------------------------------
    @api.depends(
        "contract_id",
        "contract_id.max_bill_value",
        "line_ids.ab_contract_discount_amount",
        "line_ids.ab_contract_net_amount",
        "line_ids.ab_customer_amount",
        "line_ids.ab_company_amount",
        "line_ids.qty",
        "line_ids.sell_price",
    )
    def _compute_contract_totals(self):
        for rec in self:
            if rec.contract_id:
                rec.discount = sum(rec.line_ids.mapped("ab_contract_discount_amount"))
                total_after_discount = sum(rec.line_ids.mapped("ab_contract_net_amount"))
                gross_total = sum(
                    float(l.ab_contract_gross_amount or (float(l.qty or 0.0) * float(l.sell_price or 0.0)))
                    for l in rec.line_ids
                )
                base_cust_pay = sum(rec.line_ids.mapped("ab_customer_amount"))
                base_company_pay = sum(rec.line_ids.mapped("ab_company_amount"))

                cap = float(rec.contract_id.max_bill_value or 0.0)
                if 0.0 < cap < gross_total:
                    overage = gross_total - cap
                    paid_percentage = float(rec.contract_id.paid_percentage or 0.0)
                    paid_amount = float(rec.contract_id.paid_amount or 0.0)
                    discount_rule = rec.contract_id.discount_percentage_rule or "company"

                    if paid_percentage > 0.0:
                        base_customer = cap * (paid_percentage / 100.0)
                    elif paid_amount > 0.0:
                        base_customer = min(paid_amount, cap)
                    else:
                        base_customer = 0.0

                    base_company = cap - base_customer
                    cap_discount = 0.0
                    if gross_total > 0.0 and rec.discount:
                        cap_discount = rec.discount * (cap / gross_total)
                    cap_discount = min(cap, max(0.0, cap_discount))
                    net_cap = cap - cap_discount

                    if discount_rule == "person":
                        cust_pay_cap = max(0.0, base_customer - cap_discount)
                        cust_pay_cap = min(net_cap, cust_pay_cap)
                        company_pay = net_cap - cust_pay_cap
                    elif discount_rule == "all":
                        if cap > 0.0:
                            customer_discount = cap_discount * (base_customer / cap)
                        else:
                            customer_discount = 0.0
                        cust_pay_cap = max(0.0, base_customer - customer_discount)
                        cust_pay_cap = min(net_cap, cust_pay_cap)
                        company_pay = net_cap - cust_pay_cap
                    else:
                        company_pay = max(0.0, base_company - cap_discount)
                        company_pay = min(net_cap, company_pay)
                        cust_pay_cap = net_cap - company_pay

                    cust_pay = cust_pay_cap + overage
                else:
                    cust_pay = base_cust_pay
                    company_pay = base_company_pay

                rec.total_after_discount = total_after_discount
                rec.cust_pay = cust_pay
                rec.company_pay = company_pay
            else:
                gross_total = sum(
                    float(l.qty or 0.0) * float(l.sell_price or 0.0) for l in rec.line_ids
                )
                rec.discount = 0.0
                rec.total_after_discount = gross_total
                rec.cust_pay = 0.0
                rec.company_pay = 0.0

    @api.depends(
        "line_ids",
        "line_ids.qty",
        "line_ids.sell_price",
        "line_ids.ab_contract_gross_amount",
        "line_ids.net_amount",
        "contract_id",
        "cust_pay",
    )
    def compute_totals(self):
        super().compute_totals()
        for header in self:
            if header.contract_id:
                header.total_net_amount = float(header.cust_pay or 0.0)

    # -------------------------------------------------------------------------
    # E-Plus push totals (keep DB header totals consistent when contract is set)
    # -------------------------------------------------------------------------
    def _compute_header_numbers(self, cur=None):
        """
        Override `ab_sales.ab_sales_header._compute_header_numbers` to include
        contract discounts while honoring UoM conversion when a cursor is available.
        """
        total_bill = 0.0
        total_bill_after_disc = 0.0
        total_bill_net = 0.0

        for line in self.line_ids:
            qty = float(line.qty or 0.0)
            price_selected = float(line.sell_price or 0.0)
            scale = 1.0
            if cur and line.product_id:
                _item_factor, _uom_factor, ratio = self._get_line_uom_context(cur, line)
                price_ref = self._price_ref_from_line(line, ratio)
                price_selected = float(price_ref) * float(ratio or 1.0)
                if line.sell_price:
                    scale = price_selected / float(line.sell_price or 1.0)

            gross_line = qty * price_selected
            total_bill += gross_line

            if self.contract_id:
                net_line = float(line.ab_contract_net_amount or gross_line) * scale
                cust_line = float(line.ab_customer_amount or 0.0) * scale
                total_bill_after_disc += net_line
                total_bill_net += cust_line
            else:
                total_bill_after_disc += gross_line
                total_bill_net += gross_line

        if self.contract_id:
            cap = float(self.contract_id.max_bill_value or 0.0)
            if 0.0 < cap < total_bill:
                overage = total_bill - cap
                paid_percentage = float(self.contract_id.paid_percentage or 0.0)
                paid_amount = float(self.contract_id.paid_amount or 0.0)
                discount_rule = self.contract_id.discount_percentage_rule or "company"

                if paid_percentage > 0.0:
                    base_customer = cap * (paid_percentage / 100.0)
                elif paid_amount > 0.0:
                    base_customer = min(paid_amount, cap)
                else:
                    base_customer = 0.0

                base_company = cap - base_customer
                discount_total = max(0.0, total_bill - total_bill_after_disc)
                cap_discount = 0.0
                if total_bill > 0.0 and discount_total:
                    cap_discount = discount_total * (cap / total_bill)
                cap_discount = min(cap, max(0.0, cap_discount))
                net_cap = cap - cap_discount

                if discount_rule == "person":
                    cust_pay_cap = max(0.0, base_customer - cap_discount)
                    cust_pay_cap = min(net_cap, cust_pay_cap)
                    company_pay = net_cap - cust_pay_cap
                elif discount_rule == "all":
                    if cap > 0.0:
                        customer_discount = cap_discount * (base_customer / cap)
                    else:
                        customer_discount = 0.0
                    cust_pay_cap = max(0.0, base_customer - customer_discount)
                    cust_pay_cap = min(net_cap, cust_pay_cap)
                    company_pay = net_cap - cust_pay_cap
                else:
                    company_pay = max(0.0, base_company - cap_discount)
                    company_pay = min(net_cap, company_pay)
                    cust_pay_cap = net_cap - company_pay

                total_bill_net = cust_pay_cap + overage

        total_des_mon = max(0.0, total_bill - total_bill_after_disc)
        total_dis_per = 0.0 if not total_bill else (total_des_mon / total_bill) * 100.0
        total_des_mon = 0  # تصفير القيمة لكن بعد حساب النسبة
        total_dis_per = 0

        return {
            "no_of_items": len(self.line_ids),
            "total_bill": self._to_2dec(total_bill),
            "total_bill_after_disc": self._to_2dec(total_bill_after_disc),
            "total_bill_net": self._to_2dec(total_bill_net),
            "total_dis_per": self._to_2dec(total_dis_per),
            "total_des_mon": self._to_2dec(total_des_mon),  # self._to_2dec(total_des_mon), # تصفير آخر للقيمة احتياطا
            "total_tax": 0.0,
        }

    def _insert_sales_trans_h(self, cur, totals, emp_code, pc_name, bill_typ):
        if self.contract_id:
            bill_typ = '5'
        sth_id = super()._insert_sales_trans_h(cur, totals, emp_code, pc_name, bill_typ)
        if not self.contract_id:
            return sth_id

        insurance_name = self.customer_insurance_name
        insurance_number = self.customer_insurance_number
        contract = self.contract_id
        contract_serial = getattr(contract, "eplus_serial", False) or contract.id or 0
        contract_customer_id = contract.eplus_cust_id
        try:
            contract_serial = int(contract_serial)
        except (TypeError, ValueError):
            contract_serial = int(contract.id or 0)

        update_sql = f"""
            UPDATE sales_trans_h
               SET fh_contract_id = {PARAM_STR},
                   fh_company_part = {PARAM_STR},
                   fh_medins_rec_name = {PARAM_STR},
                   fh_medins_ins_num = {PARAM_STR}
             WHERE sth_id = {PARAM_STR}
        """
        cur.execute(
            update_sql,
            (
                contract_serial,
                self._to_2dec(float(self.company_pay or 0.0)),
                insurance_name,
                insurance_number,
                int(sth_id),
            ),
        )

        if contract_customer_id:
            cur.execute(
                f"UPDATE sales_trans_h SET cust_id = {PARAM_STR} WHERE sth_id = {PARAM_STR}",
                (int(contract_customer_id), int(sth_id)),
            )

        return sth_id

    def _insert_sales_deliv_info(self, cur, sth_id, emp_code):
        super()._insert_sales_deliv_info(cur, sth_id, emp_code)
        if not self.contract_id:
            return

        contract_customer_id = self.contract_id.eplus_cust_id
        if contract_customer_id:
            cur.execute(
                f"UPDATE sales_deliv_info SET cust_id = {PARAM_STR} WHERE sth_id = {PARAM_STR}",
                (int(contract_customer_id), int(sth_id)),
            )

    def _get_sales_trans_d_discount(self, line, batch, batch_gross_total):
        if not self.contract_id:
            return super()._get_sales_trans_d_discount(line, batch, batch_gross_total)

        line_discount_pct = float(line.discount or 0.0)
        line_discount_amount = 0  # float(line.ab_contract_discount_amount or 0.0)

        allocated_dis_mon = 0.0
        if batch_gross_total > 0.0 and line_discount_amount:
            batch_gross = float(batch["qty_for_d"]) * float(batch["price_for_d"] or 0.0)
            allocated_dis_mon = (batch_gross / batch_gross_total) * line_discount_amount

        return allocated_dis_mon, line_discount_pct

    # -------------------------------------------------------------------------
    # Safety validation
    # -------------------------------------------------------------------------
    def check_total_bill_vs_cust_pay(self):
        for record in self:
            if record.line_ids and (record.total_after_discount or 0.0) < (record.cust_pay or 0.0):
                raise ValidationError(
                    _("The total bill after discount cannot be less than the customer's liability.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.contract_id:
                rec._ab_contract_validate()
            rec._ab_contract_recompute_lines()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "contract_id" in vals:
            for rec in self:
                if rec.contract_id:
                    rec._ab_contract_validate()
                rec._ab_contract_recompute_lines()
        return res
