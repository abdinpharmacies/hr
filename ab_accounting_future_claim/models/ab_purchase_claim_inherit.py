from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbPurchaseClaim(models.Model):
    _name = 'ab_purchase_claim'
    _inherit = 'ab_purchase_claim'

    future_je_ids = fields.Many2many('ab_accounting_future',
                                     compute='_compute_future_je_ids',
                                     string='Future JEs',
                                     compute_sudo=True)

    @api.depends('costcenter_id', 'account_id')
    def _compute_future_je_ids(self):
        self = self.sudo()
        for rec in self:
            rec.future_je_ids = self.env['ab_accounting_future'].sudo().search([
                '|',
                ('account_id', '=', rec.account_id.id),
                ('sett_account_id', '=', rec.account_id.id),
                ('costcenter_id', '=', rec.costcenter_id.id),
                ('je_created', '=', False),
            ])
