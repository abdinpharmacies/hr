import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import config

_logger = logging.getLogger(__name__)


class SupplierClaimCycle(models.Model):
    _inherit = 'ab_supplier_claim_cycle'

    show_telegram_connect_button = fields.Boolean(
        compute='_compute_show_telegram_connect_button',
        string='Show Telegram Connect Button',
    )

    @api.depends('status')
    def _compute_show_telegram_connect_button(self):
        Employee = self.env['ab_hr_employee'].sudo()
        employee = Employee.search([('user_id', '=', self.env.user.id)], limit=1)
        show = bool(
            employee
            and not self.env['ab_supplier_claim_telegram_registration']._employee_has_real_telegram_identity(employee)
            and self.env['ab_supplier_claim_telegram_registration'].sudo().search_count([
                ('employee_id', '=', employee.id),
                ('manager_department', '!=', False),
            ], limit=1)
        )
        for rec in self:
            rec.show_telegram_connect_button = show

    def _is_dev_override_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'supplier_claim.telegram_dev_override_enabled', 'False'
        ) == 'True'

    def _get_dev_override_user(self):
        email = self.env['ir.config_parameter'].sudo().get_param(
            'supplier_claim.telegram_dev_override_email', ''
        )
        if not email:
            return self.env['res.users']
        return self.env['res.users'].sudo().search([
            '|', ('login', '=', email), ('email', '=', email)
        ], limit=1)

    @api.model
    def get_telegram_bot_url(self):
        response = self.env['ab_telegram_bot'].sudo()._call_telegram_api('getMe')
        bot_username = ((response or {}).get('result') or {}).get('username')
        if not bot_username:
            raise UserError(_("Telegram bot username could not be resolved from the active bot token."))
        bot_username = bot_username.strip().lstrip('@')
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('telegram.bot.username', bot_username)
        icp.set_param('supplier_claim.telegram_bot_username', bot_username)
        return 'https://t.me/%s' % bot_username

    def action_open_telegram_bot(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.get_telegram_bot_url(),
            'target': 'new',
        }

    def _build_escalation_telegram_message(self, stage_key=None):
        self.ensure_one()
        stage = stage_key or self.status
        stage_label = self._get_stage_label(stage) if hasattr(self, '_get_stage_label') else stage
        return '\n'.join([
            _('🚨 <b>Claim Escalation Alert</b>'),
            '',
            _('<b>Claim Number:</b> %s') % self.display_name,
            _('<b>Supplier:</b> %s') % (self.supplier_id.display_name if self.supplier_id else 'N/A'),
            _('<b>Department:</b> %s') % stage_label,
            '',
            _('Please review immediately.'),
            '',
            _('Open Odoo and check'),
        ])

    def _build_claim_created_telegram_message(self):
        self.ensure_one()
        return '\n'.join([
            _('🧾 <b>New Supplier Claim</b>'),
            '',
            _('<b>Claim Number:</b> %s') % self.display_name,
            _('<b>Supplier:</b> %s') % (self.supplier_id.display_name if self.supplier_id else 'N/A'),
            _('<b>Amount:</b> %(amount)s %(currency)s') % {
                'amount': '{:,.2f}'.format(self.amount_of_check or 0.0),
                'currency': self.currency_id.symbol or '',
            },
            '',
            _('A new supplier claim was registered. Please follow it in Odoo.'),
        ])

    def _build_department_turn_telegram_message(self, stage_key):
        self.ensure_one()
        stage_label = self._get_stage_label(stage_key) if hasattr(self, '_get_stage_label') else stage_key
        return '\n'.join([
            _('📌 <b>Supplier Claim Turn Started</b>'),
            '',
            _('<b>Claim Number:</b> %s') % self.display_name,
            _('<b>Supplier:</b> %s') % (self.supplier_id.display_name if self.supplier_id else 'N/A'),
            _('<b>Department:</b> %s') % stage_label,
            '',
            _('This claim is now waiting for your department action.'),
        ])

    @api.model
    def _get_secretarial_fallback_lang(self):
        group = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_user', raise_if_not_found=False)
        if not group:
            return self.env.lang
        secretarial_user = group.sudo().user_ids.filtered(lambda user: user.active and user.lang).sorted('id')[:1]
        return secretarial_user.lang or self.env.lang

    @api.model
    def _get_telegram_recipient_lang(self, user=None):
        return (user and user.lang) or self._get_secretarial_fallback_lang()

    def _notify_claim_created_to_module_users(self):
        result = super()._notify_claim_created_to_module_users()
        self._send_claim_created_telegram_notifications()
        return result

    def _send_claim_created_telegram_notifications(self):
        if config['test_enable']:
            return False
        Registration = self.env['ab_supplier_claim_telegram_registration'].sudo()
        TelegramBot = self.env['ab_telegram_bot'].sudo()
        for claim in self:
            registrations = Registration.search([
                ('active', '=', True),
                ('workflow_department', '!=', False),
                ('telegram_connected', '=', True),
            ])
            sent_chat_ids = set()
            for registration in registrations:
                chat_id = Registration._get_employee_telegram_chat_id(registration.employee_id)
                if not chat_id or chat_id in sent_chat_ids:
                    continue
                lang = claim._get_telegram_recipient_lang(registration.employee_id.user_id)
                text = claim.with_context(lang=lang)._build_claim_created_telegram_message()
                TelegramBot.send_message(chat_id, text, parse_mode='HTML')
                sent_chat_ids.add(chat_id)
        return True

    def _notify_department_turn_started(self, stage_key):
        result = super()._notify_department_turn_started(stage_key)
        self._send_department_turn_telegram_notifications(stage_key)
        return result

    def _send_department_turn_telegram_notifications(self, stage_key):
        if config['test_enable']:
            return False
        dept_code = {
            'inventory': 'inventory',
            'purchase': 'purchase',
            'suppliers': 'suppliers',
            'tax_accounts': 'tax_accounts',
            'bank_acc': 'bank_accounts',
        }.get(stage_key)
        if not dept_code:
            return False

        Registration = self.env['ab_supplier_claim_telegram_registration'].sudo()
        TelegramBot = self.env['ab_telegram_bot'].sudo()
        for claim in self:
            registrations = Registration.search([
                ('active', '=', True),
                ('workflow_department', '=', dept_code),
                ('telegram_connected', '=', True),
            ])
            sent_chat_ids = set()
            for registration in registrations:
                chat_id = Registration._get_employee_telegram_chat_id(registration.employee_id)
                if not chat_id or chat_id in sent_chat_ids:
                    continue
                lang = claim._get_telegram_recipient_lang(registration.employee_id.user_id)
                text = claim.with_context(lang=lang)._build_department_turn_telegram_message(stage_key)
                TelegramBot.send_message(chat_id, text, parse_mode='HTML')
                sent_chat_ids.add(chat_id)
        return True

    def _send_external_escalation_notification(self, manager, stage_key=None):
        self.ensure_one()
        employee = self.env['ab_hr_employee'].sudo().search([
            ('user_id', '=', manager.id),
        ], limit=1)
        chat_id = self.env['ab_supplier_claim_telegram_registration'].sudo()._get_employee_telegram_chat_id(employee)
        if not chat_id:
            _logger.info('Telegram skipped: no verified Telegram identity for user %s', manager.display_name)
            return False
        text = self.with_context(lang=self._get_telegram_recipient_lang(manager))._build_escalation_telegram_message(stage_key=stage_key)
        return self.env['ab_telegram_bot'].sudo().send_message(chat_id, text, parse_mode='HTML')

    def _resolve_escalation_details(self, stage_key=None):
        parent = super()
        if hasattr(parent, '_resolve_escalation_details'):
            result = parent._resolve_escalation_details(stage_key=stage_key)
        else:
            result = {
                'managers': [],
                'manager_users': [],
                'users': [],
                'group_xmlid': False,
            }
        self.ensure_one()
        dept_code = {
            'inventory': 'inventory',
            'purchase': 'purchase',
            'suppliers': 'suppliers',
            'tax_accounts': 'tax_accounts',
            'bank_acc': 'bank_accounts',
        }.get(stage_key or self.status)
        if not dept_code:
            return result

        # In the Telegram extension, a department escalation manager is valid
        # only when explicitly configured in Telegram Senders and connected.
        result['managers'] = []
        result['manager_users'] = []
        registrations = self.env['ab_supplier_claim_telegram_registration'].sudo().search([
            ('manager_department', '=', dept_code),
            ('telegram_connected', '=', True),
        ])
        telegram_managers = self.env['ab_hr_employee']
        telegram_manager_users = self.env['res.users']
        for reg in registrations:
            if (
                reg.employee_id
                and reg.employee_id.user_id
                and reg._employee_has_real_telegram_identity(reg.employee_id)
            ):
                telegram_managers |= reg.employee_id
                telegram_manager_users |= reg.employee_id.user_id
        if telegram_manager_users:
            result['managers'] = list(telegram_managers)
            result['manager_users'] = list(telegram_manager_users)
        stage_groups = self._get_stage_group_xmlids() if hasattr(self, '_get_stage_group_xmlids') else {}
        group_xmlid = stage_groups.get(stage_key or self.status)
        if group_xmlid:
            result['group_xmlid'] = group_xmlid
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if group:
                result['users'] = list(group.sudo().user_ids)
        return result

    def _format_no_escalation_managers_note(self, department, time):
        self.ensure_one()
        return _(
            'No managers are connected to Telegram yet for the %(dept)s department.\n'
            'Time: %(time)s'
        ) % {
            'dept': self._telegram_stage_display_label(department),
            'time': time,
        }

    def _format_no_telegram_managers_note(self, time):
        return _(
            'No managers connected to Telegram yet in this department.\n'
            'Time: %(time)s'
        ) % {'time': time}

    def _format_no_telegram_managers_for_department_note(self, department, time):
        return _(
            'No managers are connected to Telegram yet for the %(dept)s department.\n'
            'Time: %(time)s'
        ) % {
            'dept': self._telegram_stage_display_label(department),
            'time': time,
        }

    def _format_department_manager_not_connected_note(self, time):
        return _(
            'The manager assigned to this department is still not connected to Telegram.\n'
            'Time: %(time)s'
        ) % {'time': time}

    def _get_display_history_notes(self, notes):
        notes = notes or ''
        lines = notes.splitlines()
        if not lines:
            parent = super()
            return parent._get_display_history_notes(notes) if hasattr(parent, '_get_display_history_notes') else notes

        title = lines[0].strip()
        if title == 'No managers connected to Telegram yet in this department.':
            return self._format_no_telegram_managers_note(self._telegram_note_time_value(lines))
        no_manager_prefix = 'No managers are connected to Telegram yet for the '
        no_manager_suffix = ' department.'
        if title.startswith(no_manager_prefix) and title.endswith(no_manager_suffix):
            department = title[len(no_manager_prefix):-len(no_manager_suffix)]
            return self._format_no_telegram_managers_for_department_note(
                department,
                self._telegram_note_time_value(lines),
            )
        if title == 'The manager assigned to this department is still not connected to Telegram.':
            return self._format_department_manager_not_connected_note(self._telegram_note_time_value(lines))
        parent = super()
        return parent._get_display_history_notes(notes) if hasattr(parent, '_get_display_history_notes') else notes

    def _telegram_stage_display_label(self, department):
        self.ensure_one()
        if hasattr(self, '_get_display_stage_label'):
            return self._get_display_stage_label(department)
        return department or ''

    def _telegram_note_time_value(self, lines):
        if hasattr(self, '_get_note_time_value'):
            return self._get_note_time_value(lines)
        return ''
