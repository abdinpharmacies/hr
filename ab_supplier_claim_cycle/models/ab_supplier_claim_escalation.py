from odoo import _, api, fields, models


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

    manager_telegram_badge = fields.Char(
        string='Telegram',
        compute='_compute_manager_telegram_badge',
    )

    def _compute_manager_telegram_badge(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'supplier_claim.telegram_dev_override_enabled', 'False') == 'True'
        dev_user = self.env['res.users']
        if enabled:
            email = self.env['ir.config_parameter'].sudo().get_param(
                'supplier_claim.telegram_dev_override_email', '')
            if email:
                dev_user = self.env['res.users'].sudo().search([
                    '|', ('login', '=', email), ('email', '=', email)
                ], limit=1)
        Employee = self.env.get('ab_hr_employee')
        user_to_telegram = {}
        if Employee:
            employees = Employee.sudo().search([('user_id', 'in', self.mapped('manager_id').ids)])
            user_to_telegram = {e.user_id.id: bool(e.telegram_chat_id) for e in employees}
        for rec in self:
            if enabled and dev_user and rec.manager_id == dev_user:
                rec.manager_telegram_badge = '\U0001F7E0 Telegram Connected (DEV)'
            elif user_to_telegram.get(rec.manager_id.id):
                rec.manager_telegram_badge = '\U0001F7E0 Telegram Connected'
            else:
                rec.manager_telegram_badge = '\u26AA Telegram Not Connected'

    def action_acknowledge(self):
        for rec in self:
            rec.write({
                'status': 'acknowledged',
                'acknowledged_at': fields.Datetime.now(),
                'acknowledged_by': self.env.user.id,
            })