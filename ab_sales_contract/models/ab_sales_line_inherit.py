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
