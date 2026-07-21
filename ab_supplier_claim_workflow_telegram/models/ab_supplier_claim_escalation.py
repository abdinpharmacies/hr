from odoo import _, fields, models


class SupplierClaimEscalation(models.Model):
    _inherit = 'ab.supplier.claim.escalation'

    manager_telegram_badge = fields.Char(
        string='Telegram',
        compute='_compute_manager_telegram_badge',
    )

    def _compute_manager_telegram_badge(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'supplier_claim.telegram_dev_override_enabled', 'False'
        ) == 'True'
        dev_user = self.env['res.users']
        if enabled:
            email = self.env['ir.config_parameter'].sudo().get_param(
                'supplier_claim.telegram_dev_override_email', ''
            )
            if email:
                dev_user = self.env['res.users'].sudo().search([
                    '|', ('login', '=', email), ('email', '=', email)
                ], limit=1)

        employees = self.env['ab_hr_employee'].sudo().search([
            ('user_id', 'in', self.mapped('manager_id').ids),
        ])
        user_to_telegram = {
            employee.user_id.id: bool(employee.telegram_chat_id and employee.telegram_user_id)
            for employee in employees
        }
        for rec in self:
            if enabled and dev_user and rec.manager_id == dev_user:
                rec.manager_telegram_badge = '\U0001F7E0 ' + _('Telegram Connected (DEV)')
            elif user_to_telegram.get(rec.manager_id.id):
                rec.manager_telegram_badge = '\U0001F7E0 ' + _('Telegram Connected')
            else:
                rec.manager_telegram_badge = '\u26AA ' + _('Telegram Not Connected')
