import datetime
import logging

from odoo import models, fields, api, _  # noqa
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def get_first_of_month(date: str):
    claim_month_list = date.split('-')
    claim_month_list[2] = '1'
    return '-'.join(claim_month_list)


class AccountingSupplierClaimLine(models.Model):
    _name = 'ab_purchase_claim_line'
    _description = 'ab_purchase_claim_line'

    name = fields.Char(required=True)
    claim_id = fields.Many2one('ab_purchase_claim')
    account_id = fields.Many2one('ab_accounting_account_guide')

    debit_val = fields.Float(digits=(16, 2))
    credit_val = fields.Float(digits=(16, 2))
    doc_type = fields.Selection(
        selection=[('payment', 'Payment'),
                   ('other', 'Other'),
                   ], default='other')

    doc_auto_code = fields.Char(compute='_compute_doc_auto_code')
    active = fields.Boolean(default=True)

    claim_supplier_id = fields.Many2one('ab_costcenter', compute='_compute_claim_supplier_id', required=True,
                                        store=True,
                                        readonly=False)

    actual_supplier_id = fields.Many2one('ab_costcenter',
                                         compute='_compute_actual_supplier_id',
                                         store=True,
                                         readonly=False,
                                         required=True)

    payment_type_id = fields.Many2one('ab_supplier_payment_type')

    other_type = fields.Selection(
        selection=[('later_goods_compensation', 'Later Goods Compensation'),
                   ('former_goods_compensation', 'Former Goods Compensation'),
                   ('cash_compensation', 'Cash Compensation'),
                   ('marketing_discount', 'Marketing Discount'),
                   ('trade_discount', 'Trade Discount'),
                   ])

    event_month = fields.Date()
    claim_month = fields.Date()

    notes = fields.Text()

    @api.depends('claim_id.costcenter_id')
    def _compute_claim_supplier_id(self):
        for rec in self:
            if rec.claim_id.costcenter_id:
                rec.claim_supplier_id = rec.claim_id.costcenter_id.id

    @api.depends('claim_supplier_id')
    def _compute_actual_supplier_id(self):
        for rec in self:
            rec.actual_supplier_id = rec.claim_supplier_id.id

    @api.depends('claim_id', 'doc_type')
    def _compute_doc_auto_code(self):
        # doc_auto_code = ''
        for rec in self:
            if rec.doc_type == 'payment':
                doc_auto_code = f"{rec.claim_id.id}-1"
            else:
                doc_auto_code = f"{rec.claim_id.id}-2"

            rec.doc_auto_code = doc_auto_code

    def btn_remove_line_from_claim(self):
        self.write({'claim_id': False})

    def write(self, values):
        # if claim_month exists, make it 1st of month
        if 'claim_month' in values and values['claim_month']:
            values['claim_month'] = get_first_of_month(values['claim_month'])
        res = super().write(values)
        return res
