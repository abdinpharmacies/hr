from odoo import _, api, fields, models


class SupplierClaimStageHistory(models.Model):
    _name = 'ab_supplier_claim_stage_history'
    _description = 'Supplier Claim Stage History'
    _order = 'sequence, create_date'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', string='Claim', required=True, ondelete='cascade', index=True)
    stage = fields.Selection([
        ('secretarial', 'Secretarial'),
        ('inventory', 'Inventory'),
        ('purchase', 'Purchase'),
        ('suppliers', 'Suppliers'),
        ('tax_accounts', 'Tax Accounts'),
        ('bank_acc', 'Bank Account'),
        ('sign_check', 'Sign Check'),
        ('supplier_notification', 'Supplier Notification'),
        ('closed', 'Closed'),
    ], required=True)
    sequence = fields.Integer(default=0)
    decision = fields.Selection([
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated'),
    ], default='pending', required=True)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    action_date = fields.Datetime(string='Action Date', default=fields.Datetime.now)
    notes = fields.Text(string='Notes')
