from odoo import api, fields, models, _


class ab_supplier_claim_cycle(models.Model):
    _name = 'ab_supplier_claim_cycle'
    _description = 'ab_supplier_claim_cycle'
    _rec_name = 'supplier_id'
    _inherit = ['mail.thread']

    supplier_id = fields.Many2one("ab_costcenter", required=True, tracking=True, domain=[("code", "=like", "1-%")])
    num_of_invoice = fields.Integer(required=True, tracking=True)
    status = fields.Selection(
        selection=[('inventory', 'Inventory'),
                    ('purchase', 'Purchase'),
                   ('suppliers', 'Suppliers'),
                   ('bank_acc', 'Bank Acc'),
                   ('sign_check', 'Sign check'),
                   ('closed', 'Closed')],
        default='inventory', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    area = fields.Selection(
        selection=[('south', 'South'),
                   ('north', 'North'),
                   ], required=True)
    amount_of_check = fields.Char(required=True)
    type_of_invoice = fields.Selection(
        selection=[('original', 'Original'),
                   ('copy', 'Copy'),
                   ], required=True)

    def btn_status(self):
        status = self.env.context.get('action')
        self.status = status
