import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbAccountingSupplierPaymentLine(models.Model):
    _name = 'ab_purchase_claim_dist_line'
    _description = 'ab_purchase_claim_dist_line'

    claim_id = fields.Many2one('ab_purchase_claim', required=True)
    account_id = fields.Many2one('ab_accounting_account_guide')
    supplier_id = fields.Many2one(related='claim_id.costcenter_id')

    value = fields.Float(digits=(16, 2))

    active = fields.Boolean(default=True)

    payment_type_id = fields.Many2one('ab_supplier_payment_type')

    claim_month = fields.Date(related='claim_id.claim_month')
    due_date = fields.Date(compute='_compute_due_date_and_value')

    supplier_bracket_id = fields.Many2one('ab_supplier_bracket', compute='_compute_supplier_bracket')
    termination_day = fields.Integer(related='supplier_bracket_id.termination_day')
    credit_days = fields.Integer(related='supplier_bracket_id.credit_days')

    discount = fields.Float(related='supplier_bracket_id.discount')

    discount_value = fields.Float(compute='_compute_discount_value')

    supplier_payment_type_ids = fields.One2many('ab_supplier_payment_type',
                                                compute='_compute_supplier_payment_type_ids')
    notes = fields.Text()

    @api.depends('discount', 'value')
    def _compute_discount_value(self):
        for rec in self:
            rec.discount_value = rec.value * (rec.discount / 100)

    @api.depends('supplier_id', 'claim_id.costcenter_id')
    def _compute_supplier_payment_type_ids(self):
        for rec in self:
            supplier_brackets = self.env['ab_supplier_bracket'].search(
                [('supplier_id', '=', rec.supplier_id.id)])

            rec.supplier_payment_type_ids = supplier_brackets.mapped('payment_type_id')

    @api.constrains('value')
    def _constrains_ab_purchase_claim_dist_line(self):
        for rec in self:
            if rec.value < 0:
                raise ValidationError(_("VALUE CAN NOT BE NEGATIVE"))

    @api.depends('payment_type_id', 'value', 'claim_id.claim_month')
    def _compute_supplier_bracket(self):
        credit_model = self.env['ab_supplier_bracket']
        for rec in self:
            supplier_bracket = credit_model.search([
                ('supplier_id', '=', rec.supplier_id.id),
                ('payment_type_id', '=', rec.payment_type_id.id),
                ('withdrawal_bracket', '<=', rec.value),
            ], limit=1, order='withdrawal_bracket DESC')

            rec.supplier_bracket_id = supplier_bracket.id

    @api.depends('payment_type_id', 'value', 'claim_month')
    def _compute_due_date_and_value(self):
        for rec in self:
            due_date = rec.claim_month + datetime.timedelta(days=rec.supplier_bracket_id.termination_day)
            if rec.claim_month:
                due_date = rec.claim_month + datetime.timedelta(days=rec.credit_days)

            rec.due_date = due_date

    def btn_remove_line_from_claim(self):
        self.write({'claim_id': False})
