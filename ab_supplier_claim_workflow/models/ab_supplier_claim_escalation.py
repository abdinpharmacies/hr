from odoo import fields, models


class SupplierClaimEscalation(models.Model):
    _name = 'ab.supplier.claim.escalation'
    _description = 'Supplier Claim Escalation'
    _order = 'escalation_time desc'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', string='Claim', required=True, ondelete='cascade',
                               index=True)
    manager_id = fields.Many2one('res.users', string='Manager', required=True, index=True)
    department_name = fields.Char(string='Department')
    current_stage = fields.Char(string='Stage at Escalation')
    escalation_time = fields.Datetime(string='Escalation Time', default=fields.Datetime.now, required=True)
    status = fields.Selection(
        selection=[('pending', 'Pending'), ('acknowledged', 'Acknowledged')],
        default='pending', string='Status', required=True, tracking=True)
    acknowledged_at = fields.Datetime(string='Acknowledged At', readonly=True)
    acknowledged_by = fields.Many2one('res.users', string='Acknowledged By', readonly=True)
    notes = fields.Text(string='Notes')
    method = fields.Selection(
        selection=[('odoo_activity', 'Odoo Activity'), ('internal_fallback', 'Internal Fallback')],
        string='Notification Method', readonly=True)

    def action_acknowledge(self):
        for rec in self:
            rec.write({
                'status': 'acknowledged',
                'acknowledged_at': fields.Datetime.now(),
                'acknowledged_by': self.env.user.id,
            })
