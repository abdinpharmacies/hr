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

    @api.onchange('manager_department')
    def _onchange_manager_department(self):
        DEPT_GROUP_MAP = {
            'inventory': 'ab_supplier_claim_cycle.supplier_claim_group_inventory',
            'purchase': 'ab_supplier_claim_cycle.supplier_claim_group_purchase',
            'suppliers': 'ab_supplier_claim_cycle.supplier_claim_group_suppliers',
            'bank_accounts': 'ab_supplier_claim_cycle.supplier_claim_group_bank_acc',
            'tax_accounts': 'ab_supplier_claim_cycle.supplier_claim_group_tax_accounts',
        }
        for rec in self:
            if not rec.manager_department or not rec.user_id:
                continue
            xml_id = DEPT_GROUP_MAP.get(rec.manager_department)
            if not xml_id:
                continue
            group = self.env.ref(xml_id, raise_if_not_found=False)
            if group and rec.user_id.id not in group.user_ids.ids:
                group.sudo().write({'user_ids': [(4, rec.user_id.id)]})

    def write(self, vals):
        old_depts = {}
        if 'manager_department' in vals:
            for rec in self:
                old_depts[rec.id] = rec.manager_department
        if 'telegram_chat_id' in vals and not vals['telegram_chat_id']:
            vals['telegram_chat_id'] = None
        result = super().write(vals)
        for rec in self:
            if rec.id in old_depts and old_depts[rec.id] != rec.manager_department:
                rec._onchange_manager_department()
        return result

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
    def import_existing_managers(self):
        try:
            Employee = self.env['ab_hr_employee'].sudo()
            Job = self.env['ab_hr_job'].sudo()
        except KeyError:
            return {'error': 'HR module not available'}
        JOB_GROUP_MAP = {
            'نائب مدير المخازن': 'ab_supplier_claim_cycle.supplier_claim_group_inventory',
            'مدير قسم حسابات الضرائب': 'ab_supplier_claim_cycle.supplier_claim_group_tax_accounts',
            'مدير قسم حسابات الموردين': 'ab_supplier_claim_cycle.supplier_claim_group_suppliers',
            'مدير قسم حسابات البنوك': 'ab_supplier_claim_cycle.supplier_claim_group_bank_acc',
            'نائب مدير قطاع المشتريات والتجارية': 'ab_supplier_claim_cycle.supplier_claim_group_purchase',
        }
        created = 0
        for job_name, group_xml_id in JOB_GROUP_MAP.items():
            jobs = Job.search([('name', '=', job_name)])
            if not jobs:
                continue
            employees = Employee.search([('job_id', 'in', jobs.ids)])
            group = self.env.ref(group_xml_id, raise_if_not_found=False)
            for emp in employees:
                existing = self.sudo().search([('employee_id', '=', emp.id)], limit=1)
                if existing:
                    continue
                rec = self.sudo().create({
                    'employee_id': emp.id,
                    'telegram_chat_id': str(emp.id),
                    'telegram_connected': False,
                    'linked_at': fields.Datetime.now(),
                })
                if group:
                    GROUP_TO_DEPT = {
                        'ab_supplier_claim_cycle.supplier_claim_group_inventory': 'inventory',
                        'ab_supplier_claim_cycle.supplier_claim_group_tax_accounts': 'tax_accounts',
                        'ab_supplier_claim_cycle.supplier_claim_group_suppliers': 'suppliers',
                        'ab_supplier_claim_cycle.supplier_claim_group_bank_acc': 'bank_accounts',
                        'ab_supplier_claim_cycle.supplier_claim_group_purchase': 'purchase',
                    }
                    rec.write({'manager_department': GROUP_TO_DEPT.get(group_xml_id)})
                    if emp.user_id and emp.user_id.id not in group.user_ids.ids:
                        group.sudo().write({'user_ids': [(4, emp.user_id.id)]})
                created += 1
        return {'created': created}

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
