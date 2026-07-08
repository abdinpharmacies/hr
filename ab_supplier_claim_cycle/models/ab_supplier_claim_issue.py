from odoo import _, api, fields, models


class SupplierClaimIssue(models.Model):
    _name = 'ab.supplier.claim.issue'
    _description = 'Supplier Claim Blocking Issue'
    _order = 'date desc, id desc'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', string='Claim', required=True, ondelete='cascade', index=True)
    title = fields.Char(string='Title', required=True)
    description = fields.Text(string='Description')
    user_id = fields.Many2one('res.users', string='Reported By', default=lambda self: self.env.user, required=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now, required=True)
    resolved = fields.Boolean(string='Resolved', default=False)
    resolved_by = fields.Many2one('res.users', string='Resolved By', readonly=True)
    resolved_date = fields.Datetime(string='Resolved Date', readonly=True)
    stage = fields.Char(string='Stage', required=True)

    def action_resolve(self):
        self.ensure_one()
        self.write({
            'resolved': True,
            'resolved_by': self.env.user.id,
            'resolved_date': fields.Datetime.now(),
        })
        self.claim_id._compute_workflow_access()
        return {'type': 'ir.actions.act_window_close'}
