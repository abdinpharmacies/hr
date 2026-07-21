import re

from odoo import _, api, fields, models


class AbSupplierClaimTelegramRegistration(models.Model):
    _name = 'ab_supplier_claim_telegram_registration'
    _description = 'Supplier Claim Telegram Registration'
    _rec_name = 'eplus_code'
    _order = 'linked_at desc'

    employee_id = fields.Many2one('ab_hr_employee', string='Employee', required=True)
    eplus_code = fields.Char(
        string='E-Plus Code',
        compute='_compute_eplus_code',
        inverse='_inverse_eplus_code',
        store=True,
        compute_sudo=True,
        prefetch=False,
    )
    employee_name = fields.Char(string='Employee Name', related='employee_id.name', store=False)
    user_id = fields.Many2one('res.users', string='Related User', related='employee_id.user_id', store=False)
    work_phone = fields.Char(string='Work Phone', related='employee_id.work_phone', store=False)
    department_id = fields.Many2one('ab_hr_department', string='Department', related='employee_id.department_id', store=False)
    superior_department_id = fields.Many2one(
        'ab_hr_department',
        string='Superior Department',
        related='employee_id.department_id.parent_id',
        store=False,
    )
    job_id = fields.Many2one('ab_hr_job', string='Job', related='employee_id.job_id', store=False)
    is_working = fields.Boolean(string='Is Working', compute='_compute_is_working', store=False)
    telegram_connected = fields.Boolean(
        string='Telegram Connected',
        compute='_compute_telegram_connected',
        store=True,
        compute_sudo=True,
    )
    telegram_chat_id = fields.Char(
        string='Telegram Chat ID',
        related='employee_id.telegram_chat_id',
        readonly=True,
        store=False,
    )
    telegram_username = fields.Char(
        string='Telegram Username',
        related='employee_id.telegram_username',
        readonly=True,
        store=False,
    )
    linked_at = fields.Datetime(
        string='Linked At',
        related='employee_id.telegram_linked_at',
        readonly=True,
        store=True,
    )
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

    @api.model
    def _normalize_telegram_employee_code(self, value):
        return re.sub(r'[^0-9A-Za-z]+', '', value or '').upper()

    @api.model
    def _extract_telegram_employee_code(self, text):
        cleaned = (text or '').strip()
        if not cleaned:
            return False
        normalized = ' '.join(cleaned.replace('_', ' ').replace('-', ' ').split())
        parts = normalized.split()
        if (
            len(parts) == 1
            and self._normalize_telegram_employee_code(parts[0])
            and any(char.isdigit() for char in parts[0])
        ):
            return parts[0]
        command_words = {'employee', 'emp', 'code', 'link', 'hr', 'موظف', 'كود', 'ربط'}
        if not any(part.lower() in command_words for part in parts):
            return False
        candidates = [part for part in parts if part.lower() not in command_words]
        return candidates[-1] if candidates else False

    @api.model
    def _find_employee_by_telegram_code(self, code):
        normalized_code = self._normalize_telegram_employee_code(code)
        if not normalized_code:
            return self.env['ab_hr_employee']
        Employee = self.env['ab_hr_employee'].sudo()
        employee = Employee.search([('costcenter_id.code', '=', code), ('active', '=', True)], limit=2)
        if len(employee) == 1:
            return employee
        fields_to_check = [field for field in ('barcode', 'identification_id', 'accid') if field in Employee._fields]
        for field_name in fields_to_check:
            employee = Employee.search([(field_name, '=', code), ('active', '=', True)], limit=2)
            if len(employee) == 1:
                return employee
        candidates = Employee.search([('active', '=', True)])
        matched = candidates.filtered(
            lambda emp: (
                self._normalize_telegram_employee_code(emp.costcenter_id.code) == normalized_code
                or any(
                    self._normalize_telegram_employee_code(emp[field_name]) == normalized_code
                    for field_name in fields_to_check
                )
            )
        )
        if len(matched) == 1:
            return matched
        return self.env['ab_hr_employee']

    @api.model
    def _link_employee_from_telegram_message(self, message_data):
        code = self._extract_telegram_employee_code(message_data.get('text'))
        if not code:
            return {'handled': False}
        employee = self._find_employee_by_telegram_code(code)
        if not employee:
            return {
                'handled': True,
                'text': _('No active employee was found for code: %s') % code,
                'note': 'employee_not_found',
            }
        if employee.job_status and employee.job_status != 'active':
            return {
                'handled': True,
                'text': _('Employee code %s is not active.') % code,
                'note': 'employee_not_active',
            }
        employee.sudo().write({
            'telegram_chat_id': str(message_data.get('telegram_chat_id') or '').strip() or False,
            'telegram_user_id': str(message_data.get('telegram_user_id') or '').strip() or False,
            'telegram_username': (message_data.get('username') or '').strip() or False,
            'telegram_linked_at': fields.Datetime.now(),
        })
        self.sudo()._ensure_registration_from_employee(employee)
        return {
            'handled': True,
            'text': _('Telegram account linked to employee %s.') % employee.display_name,
            'note': 'employee_telegram_linked',
            'employee_id': employee.id,
        }

    @api.model
    def _ensure_registration_from_employee(self, employee):
        if not employee:
            return self
        existing = self.sudo().search([('employee_id', '=', employee.id)], limit=1)
        if existing:
            return existing
        return self.sudo().create({'employee_id': employee.id})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'eplus_code' in vals and not vals.get('employee_id'):
                employee = self._find_employee_by_telegram_code(vals['eplus_code'])
                if employee:
                    vals['employee_id'] = employee.id
        records = super().create(vals_list)
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'manager_department' in vals:
            self._onchange_manager_department()
        return result

    @api.depends('employee_id')
    def _compute_eplus_code(self):
        for rec in self:
            rec.eplus_code = rec.employee_id.accid

    def _inverse_eplus_code(self):
        for rec in self:
            if rec.eplus_code:
                employee = self._find_employee_by_telegram_code(rec.eplus_code)
                if employee:
                    rec.employee_id = employee.id

    @api.depends('employee_id.job_status')
    def _compute_is_working(self):
        for rec in self:
            rec.is_working = rec.employee_id.job_status == 'active'

    @api.depends('employee_id.telegram_chat_id', 'employee_id.telegram_user_id')
    def _compute_telegram_connected(self):
        for rec in self:
            rec.telegram_connected = rec._employee_has_real_telegram_identity(rec.employee_id)

    @api.model
    def _employee_has_real_telegram_identity(self, employee):
        return bool(
            employee
            and (employee.telegram_chat_id or '').strip()
            and (employee.telegram_user_id or '').strip()
        )

    @api.onchange('manager_department')
    def _onchange_manager_department(self):
        dept_group_map = {
            'inventory': 'ab_supplier_claim_workflow.supplier_claim_group_inventory',
            'purchase': 'ab_supplier_claim_workflow.supplier_claim_group_purchase',
            'suppliers': 'ab_supplier_claim_workflow.supplier_claim_group_suppliers',
            'bank_accounts': 'ab_supplier_claim_workflow.supplier_claim_group_bank_acc',
            'tax_accounts': 'ab_supplier_claim_workflow.supplier_claim_group_tax_accounts',
        }
        for rec in self:
            if not rec.manager_department or not rec.user_id:
                continue
            xml_id = dept_group_map.get(rec.manager_department)
            if not xml_id:
                continue
            group = self.env.ref(xml_id, raise_if_not_found=False)
            if group and rec.user_id.id not in group.user_ids.ids:
                group.sudo().write({'user_ids': [(4, rec.user_id.id)]})

    @api.model
    def register_from_telegram(self, eplus_code, chat_id, username=None):
        payload = self._link_employee_from_telegram_message({
            'telegram_user_id': chat_id,
            'telegram_chat_id': chat_id,
            'text': str(eplus_code or '').strip(),
            'username': username,
        })
        if not payload.get('handled') or payload.get('note') != 'employee_telegram_linked':
            return {'error': payload.get('text') or _('Employee not found with this E-Plus code')}
        employee = self.env['ab_hr_employee'].sudo().browse(payload.get('employee_id')).exists()
        rec = self._ensure_registration_from_employee(employee)
        return {
            'success': True,
            'id': rec.id,
            'employee_name': employee.name,
            'eplus_code': employee.accid,
            'updated': True,
        }

    @api.model
    def _ensure_registration_from_employee_code(self, text):
        return self._ensure_registration_from_employee(self._find_employee_by_telegram_code(text))

    @api.model
    def import_existing_managers(self):
        job_group_map = {
            'نائب مدير المخازن': 'ab_supplier_claim_workflow.supplier_claim_group_inventory',
            'مدير قسم حسابات الضرائب': 'ab_supplier_claim_workflow.supplier_claim_group_tax_accounts',
            'مدير قسم حسابات الموردين': 'ab_supplier_claim_workflow.supplier_claim_group_suppliers',
            'مدير قسم حسابات البنوك': 'ab_supplier_claim_workflow.supplier_claim_group_bank_acc',
            'نائب مدير قطاع المشتريات والتجارية': 'ab_supplier_claim_workflow.supplier_claim_group_purchase',
        }
        group_to_dept = {
            'ab_supplier_claim_workflow.supplier_claim_group_inventory': 'inventory',
            'ab_supplier_claim_workflow.supplier_claim_group_tax_accounts': 'tax_accounts',
            'ab_supplier_claim_workflow.supplier_claim_group_suppliers': 'suppliers',
            'ab_supplier_claim_workflow.supplier_claim_group_bank_acc': 'bank_accounts',
            'ab_supplier_claim_workflow.supplier_claim_group_purchase': 'purchase',
        }
        created = 0
        for job_name, group_xml_id in job_group_map.items():
            jobs = self.env['ab_hr_job'].sudo().search([('name', '=', job_name)])
            if not jobs:
                continue
            employees = self.env['ab_hr_employee'].sudo().search([('job_id', 'in', jobs.ids)])
            group = self.env.ref(group_xml_id, raise_if_not_found=False)
            for employee in employees:
                existing = self.sudo().search([('employee_id', '=', employee.id)], limit=1)
                if existing:
                    if not existing.manager_department:
                        existing.write({'manager_department': group_to_dept.get(group_xml_id)})
                    continue
                rec = self.sudo().create({
                    'employee_id': employee.id,
                    'manager_department': group_to_dept.get(group_xml_id),
                })
                if group and employee.user_id and employee.user_id.id not in group.user_ids.ids:
                    group.sudo().write({'user_ids': [(4, employee.user_id.id)]})
                if rec:
                    created += 1
        return {'created': created}

    @api.model
    def migrate_legacy_registration_data(self):
        self.search([])._compute_telegram_connected()
        return True

    @api.model
    def _cron_import_telegram_registrations(self):
        icp = self.env['ir.config_parameter'].sudo()
        if icp.get_param('telebot_webhook_url'):
            return
        last_offset = int(icp.get_param('ab_supplier_claim_cycle.telegram_last_update_id', '0'))
        telegram_service = self.env['ab_telegram_service'].sudo()
        updates = telegram_service.get_updates(offset=last_offset + 1)
        if not updates:
            return
        max_update_id = last_offset
        for update in updates:
            update_id = update.get('update_id', 0)
            if update_id > max_update_id:
                max_update_id = update_id
            message = update.get('message') or {}
            text = (message.get('text') or '').strip()
            if not text:
                continue
            result = telegram_service.dispatch_webhook_payload(update) or {}
            if result.get('reason') == 'employee_telegram_linked':
                self._ensure_registration_from_employee_code(text)
        if max_update_id > last_offset:
            icp.set_param('ab_supplier_claim_cycle.telegram_last_update_id', str(max_update_id))

    def action_open_bot(self):
        self.ensure_one()
        bot_username = self.env['ir.config_parameter'].sudo().get_param(
            'supplier_claim.telegram_bot_username', ''
        ) or self.env['ir.config_parameter'].sudo().get_param(
            'telegram.bot.username', 'AbdinDevBot'
        )
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://t.me/%s' % bot_username,
            'target': 'new',
        }
