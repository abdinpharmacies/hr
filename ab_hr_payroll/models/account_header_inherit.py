from odoo import api, fields, models


class AccountHeader(models.Model):
    _inherit = 'ab_accounting_je_header'

    salary_line_ids = fields.One2many('ab_hr_payroll', 'account_header_id')
