from odoo import api, fields, models


class AbSalesLineContract(models.Model):
    _inherit = "ab_sales_line"

    # NOTE: These are stored fields (not computed) and are updated by the header recompute
    # hook (see `ab_sales_header_inherit._ab_contract_recompute_lines`).
    discount = fields.Float(string="Contract Discount %", readonly=True)

    ab_contract_discount_source = fields.Selection(
        selection=[
            ("rule", "Contract Rule"),
            ("origin", "Contract Origin Default"),
            ("none", "No Discount"),
        ],
        string="Discount Source",
        readonly=True,
    )

    ab_contract_copay_mode = fields.Selection(
        selection=[
            ("before_discount", "Copay Before Discount"),
            ("after_discount", "Copay After Discount"),
        ],
        string="Copay Mode",
        readonly=True,
    )
    ab_contract_copay_percent = fields.Float(string="Copay %", readonly=True)

    ab_contract_gross_amount = fields.Float(string="Gross Amount", readonly=True)
    ab_contract_discount_amount = fields.Float(string="Discount Amount", readonly=True)
    ab_contract_net_amount = fields.Float(string="Net Amount", readonly=True)
    ab_customer_amount = fields.Float(string="Customer Amount", readonly=True)
    ab_company_amount = fields.Float(string="Company Amount", readonly=True)

    # -------------------------------------------------------------------------
    # Contract discount resolution helpers
    # -------------------------------------------------------------------------
    def _ab_contract_get_discount_percent(self, contract):
        """
        Resolve contract discount % for this line.

        Order:
          1) `ab_contract_product_origin` (contract + product_card)
          2) Contract default discount by product card origin
          3) 0
        """
        self.ensure_one()
        if not contract or not self.product_id:
            return 0.0, "none"

        product_card = self.product_id.product_card_id
        if product_card:
            rule = self.env["ab_contract_product_origin"].search(
                [
                    ("contract_id", "=", contract.id),
                    ("product_card_id", "=", product_card.id),
                ],
                limit=1,
            )
            # A rule with 0% is still a valid explicit match (should not fallback).
            if rule:
                return float(rule.discount or 0.0), "rule"

        origin = self.product_id.origin
        origin_discount = 0.0
        if origin == "local":
            origin_discount = contract.local_product_discount
        elif origin == "imported":
            origin_discount = contract.imported_product_discount
        elif origin == "special_imported":
            origin_discount = contract.special_import_product_discount
        elif origin == "chemical":
            origin_discount = contract.local_made_product_discount
        elif origin == "other":
            origin_discount = contract.other_product_discount

        origin_discount = float(origin_discount or 0.0)
        return origin_discount, ("origin" if origin_discount else "none")

    # -------------------------------------------------------------------------
    # Integration hooks (keep in-sync when lines change)
    # -------------------------------------------------------------------------
    @api.onchange("product_id", "qty_str", "sell_price")
    def _onchange_ab_contract_recompute(self):
        for line in self:
            if line.header_id:
                line.header_id._ab_contract_recompute_lines()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Avoid recursion when the header recompute itself writes line fields.
        if not self.env.context.get("ab_skip_contract_pricing"):
            records.mapped("header_id")._ab_contract_recompute_lines()
        return records

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("ab_skip_contract_pricing"):
            return res

        fields_trigger = {"product_id", "qty_str", "sell_price", "header_id"}
        if fields_trigger.intersection(vals.keys()):
            self.mapped("header_id")._ab_contract_recompute_lines()
        return res

    @api.depends("qty", "sell_price", "header_id.contract_id", "ab_contract_net_amount")
    def _compute_net_amount(self):
        """
        Keep `ab_sales` totals correct:
        - Without contract: net = qty * sell_price (existing behavior)
        - With contract: net = stored `ab_contract_net_amount` (fallback to gross if missing)
        """
        for rec in self:
            gross = float(rec.qty or 0.0) * float(rec.sell_price or 0.0)
            if rec.header_id.contract_id:
                rec.net_amount = float(rec.ab_contract_net_amount or gross)
            else:
                rec.net_amount = gross

