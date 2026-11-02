from odoo import api, fields, models


class AbSalesLineContract(models.Model):
    _inherit = "ab_sales_line"

    # Passive snapshots populated by branch uploads; reporting views stay read-only.
    discount = fields.Float(string="Contract Discount %", readonly=True)

    ab_contract_discount_source = fields.Char(
        string="Discount Source",
    )

    ab_contract_copay_mode = fields.Char(
        string="Copay Mode",
    )
    ab_contract_copay_percent = fields.Float(string="Copay %", readonly=True)

    ab_contract_gross_amount = fields.Float(string="Gross Amount", readonly=True)
    ab_contract_discount_amount = fields.Float(string="Discount Amount", readonly=True)
    ab_contract_net_amount = fields.Float(string="Net Amount", readonly=True)
    ab_customer_amount = fields.Float(string="Customer Amount", readonly=True)
    ab_company_amount = fields.Float(string="Company Amount", readonly=True)
