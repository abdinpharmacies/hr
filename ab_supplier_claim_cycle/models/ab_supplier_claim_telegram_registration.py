from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbSupplierClaimTelegramRegistration(models.Model):
    _name = 'ab_supplier_claim_telegram_registration'
    _description = 'Supplier Claim Telegram Registration'
    _rec_name = 'eplus_code'
    _order = 'linked_at desc'

    employee_id = fields.Many2one('ab_hr_employee', string='Employee', required=True)
    eplus_code = fields.Char(
        string='E-Plus Code',
        compute='_compute_eplus_code', inverse='_inverse_eplus_code',
        store=True, compute_sudo=True, prefetch=False)
    employee_name = fields.Char(string='Employee Name', related='employee_id.name', store=False)
    user_id = fields.Many2one('res.users', string='Related User', related='employee_id.user_id', store=False)
    work_phone = fields.Char(string='Work Phone', related='employee_id.work_phone', store=False)
    department_id = fields.Many2one('ab_hr_department', string='Department', related='employee_id.department_id', store=False)
    superior_department_id = fields.Many2one('ab_hr_department', string='Superior Department', related='employee_id.department_id.parent_id', store=False)
    job_id = fields.Many2one('ab_hr_job', string='Job', related='employee_id.job_id', store=False)
    is_working = fields.Boolean(string='Is Working', compute='_compute_is_working', store=False)
    telegram_connected = fields.Boolean(string='Telegram Connected', default=False)
    telegram_chat_id = fields.Char(string='Telegram Chat ID')
    telegram_username = fields.Char(string='Telegram Username')
    linked_at = fields.Datetime(string='Linked At', default=fields.Datetime.now)
    manager_department = fields.Selection([
        ('inventory', 'Inventory'),
        ('purchase', 'Purchase'),
        ('suppliers', 'Suppliers'),
        ('bank_accounts', 'Bank Accounts'),
        ('tax_accounts', 'Tax Accounts'),
    ], string='Manager at')
    active = fields.Boolean(default=True)

    _uniq_employee = models.Constraint(
        'UNIQUE(employee_id)',
        _('This employee is already registered. Each employee can have only one Telegram link.'),
    )
    _uniq_chat = models.Constraint(
        'UNIQUE(telegram_chat_id)',
        _('This Telegram account is already linked.'),
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'eplus_code' in vals and not vals.get('employee_id'):
                employee = self.env['ab_hr_employee'].sudo().search([
                    ('accid', '=', vals['eplus_code'])], limit=1)
                if employee:
                    vals['employee_id'] = employee.id
            if 'telegram_chat_id' in vals and not vals['telegram_chat_id']:
                vals['telegram_chat_id'] = None
        return super().create(vals_list)

    @api.depends('employee_id')
    def _compute_eplus_code(self):
        for rec in self:
            rec.eplus_code = rec.employee_id.accid

    def _inverse_eplus_code(self):
        for rec in self:
            if rec.eplus_code:
                employee = self.env['ab_hr_employee'].sudo().search([
                    ('accid', '=', rec.eplus_code)], limit=1)
                if employee:
                    rec.employee_id = employee.id

    @api.depends('employee_id.job_status')
    def _compute_is_working(self):
        for rec in self:
            rec.is_working = rec.employee_id.job_status == 'active'

    def write(self, vals):
        if 'telegram_chat_id' in vals and not vals['telegram_chat_id']:
            vals['telegram_chat_id'] = None
        return super().write(vals)

    @api.model
    def register_from_telegram(self, eplus_code, chat_id, username=None):
        try:
            Employee = self.env['ab_hr_employee'].sudo()
        except KeyError:
            return {'error': 'HR module not available'}
        employee = Employee.search([('accid', '=', str(eplus_code).strip())], limit=1)
        if not employee:
            return {'error': 'Employee not found with this E-Plus code'}
        existing_chat = self.sudo().search([('telegram_chat_id', '=', str(chat_id))], limit=1)
        if existing_chat:
            return {'error': 'Telegram account already linked.'}
        existing = self.sudo().search([('employee_id', '=', employee.id)], limit=1)
        if existing:
            existing.write({
                'telegram_chat_id': str(chat_id),
                'telegram_username': (username or '').strip() or False,
                'linked_at': fields.Datetime.now(),
                'telegram_connected': True,
            })
            return {
                'success': True,
                'id': existing.id,
                'employee_name': employee.name,
                'eplus_code': employee.accid,
                'updated': True,
            }
        rec = self.sudo().create({
            'employee_id': employee.id,
            'telegram_chat_id': str(chat_id),
            'telegram_username': (username or '').strip() or False,
            'telegram_connected': True,
            'linked_at': fields.Datetime.now(),
        })
        return {
            'success': True,
            'id': rec.id,
            'employee_name': employee.name,
            'eplus_code': employee.accid,
        }

    @api.model
    def _cron_import_telegram_registrations(self):
        icp = self.env['ir.config_parameter'].sudo()
        bot_token = icp.get_param('supplier_claim.telegram_bot_token')
        if not bot_token:
            return
        from ..services import telegram_service
        last_offset = int(icp.get_param(
            'ab_supplier_claim_cycle.telegram_last_update_id', '0'))
        updates = telegram_service.get_updates(bot_token, offset=last_offset + 1)
        if not updates:
            return
        max_update_id = last_offset
        try:
            Employee = self.env['ab_hr_employee'].sudo()
        except KeyError:
            return
        for update in updates:
            try:
                update_id = update.get('update_id', 0)
                if update_id > max_update_id:
                    max_update_id = update_id
                msg = update.get('message', {})
                chat = msg.get('chat', {})
                chat_id = chat.get('id')
                username = chat.get('username', '')
                text = (msg.get('text', '') or '').strip()
                if not chat_id or not text:
                    continue
                employee = Employee.sudo().search([('accid', '=', text)], limit=1)
                if not employee:
                    continue
                existing = self.sudo().search([
                    '|',
                    ('employee_id', '=', employee.id),
                    ('telegram_chat_id', '=', str(chat_id)),
                ], limit=1)
                if existing:
                    if not existing.telegram_connected or existing.telegram_chat_id != str(chat_id):
                        existing.write({
                            'telegram_chat_id': str(chat_id),
                            'telegram_connected': True,
                            'telegram_username': (username or '').strip() or False,
                            'linked_at': fields.Datetime.now(),
                        })
                    continue
                self.sudo().create({
                    'employee_id': employee.id,
                    'telegram_chat_id': str(chat_id),
                    'telegram_username': (username or '').strip() or False,
                    'telegram_connected': True,
                    'linked_at': fields.Datetime.now(),
                })
            except Exception:
                continue
        if max_update_id > last_offset:
            icp.set_param(
                'ab_supplier_claim_cycle.telegram_last_update_id',
                str(max_update_id))

    def action_open_bot(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://t.me/abdin_supplier_claim_bot',
            'target': 'new',
        }
