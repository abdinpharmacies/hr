from odoo import api, fields, models


class AuditCoverage(models.Model):
    _name = 'ab_inventory_audit_coverage'
    _inherit = 'ab_inventory_audit_child'
    _description = 'Audit Product Coverage'
    _rec_name = 'product_id'

    product_id = fields.Many2one('ab_product', required=True, ondelete='restrict', index=True)
    origin = fields.Selection([('opening', 'Opening Scope'), ('additional', 'Additional Scope')], required=True)
    decision = fields.Selection([('included', 'Included'), ('pending', 'Pending Decision'),
                                 ('excluded', 'Excluded')], required=True, default='included')
    decision_reason = fields.Text()
    state = fields.Selection([('unresolved', 'Unresolved'), ('complete', 'Complete'),
                              ('excluded', 'Excluded')], compute='_compute_state')
    _product_unique = models.Constraint('UNIQUE(audit_id, product_id)', 'This product already has coverage.')

    @api.depends('decision', 'audit_id.line_ids.state', 'audit_id.observation_ids.state')
    def _compute_state(self):
        audits = self.sudo().audit_id
        outcomes = {}
        for line in audits.line_ids:
            if line.physical_absence and line.state == 'excluded':
                continue
            outcomes.setdefault((line.audit_id.id, line.product_id.id), []).append(line.state)
        pending = {(item.audit_id.id, item.product_id.id) for item in audits.observation_ids if item.state == 'pending'}
        for coverage in self:
            key = (coverage.audit_id.id, coverage.product_id.id)
            states = outcomes.get(key, [])
            if coverage.decision == 'excluded':
                coverage.state = 'excluded'
            elif not states or key in pending or any(state not in ('accepted', 'excluded') for state in states):
                coverage.state = 'unresolved'
            elif 'excluded' in states:
                coverage.state = 'excluded'
            else:
                coverage.state = 'complete' if coverage.decision == 'included' else 'unresolved'


class AuditObservation(models.Model):
    _name = 'ab_inventory_audit_observation'
    _inherit = 'ab_inventory_audit_child'
    _description = 'Unidentified Stock Observation'
    _rec_name = 'product_id'

    product_id = fields.Many2one('ab_product', required=True, ondelete='restrict')
    counter_id = fields.Many2one('res.users', required=True)
    observed_at = fields.Datetime(required=True, default=fields.Datetime.now)
    quantity = fields.Float(required=True, digits=(16, 6))
    uom_id = fields.Many2one('ab_product_uom', required=True, ondelete='restrict')
    exp_date = fields.Date()
    no_expiry = fields.Boolean()
    selling_price = fields.Float(digits=(16, 3))
    notes = fields.Text(required=True)
    state = fields.Selection([('pending', 'Pending Decision'), ('included', 'Included'),
                              ('excluded', 'Excluded')], required=True, default='pending')
    decision_reason = fields.Text()
    decided_by = fields.Many2one('res.users')
    decided_at = fields.Datetime()
    line_id = fields.Many2one('ab_inventory_audit_line', ondelete='restrict')
