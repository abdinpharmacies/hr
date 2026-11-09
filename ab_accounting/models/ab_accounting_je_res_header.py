from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class AbAccountingJeHeader(models.Model):
    _name = 'ab_accounting_je_header'
    _inherit = ['ab_accounting_je_header']

    res_header_ref = fields.Char(index=True)
    res_header_id = fields.Integer(index=True)


class AbAccountingJeLine(models.Model):
    _name = 'ab_accounting_je_line'
    _inherit = ['ab_accounting_je_line', 'abdin_et.extra_tools']

    res_header_ref = fields.Char(related='header_id.res_header_ref')
    res_header_id = fields.Integer(related='header_id.res_header_id')


class AbAccountingJeLineQry(models.Model):
    _name = 'ab_accounting_je_line_qry'
    _inherit = 'ab_accounting_je_line_qry'

    res_header_ref = fields.Char(related='header_id.res_header_ref')
    res_header_id = fields.Integer(related='header_id.res_header_id', string='Res Header ID')
