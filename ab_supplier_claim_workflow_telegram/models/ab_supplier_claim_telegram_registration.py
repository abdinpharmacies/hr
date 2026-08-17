import re

from odoo import _, api, fields, models


class AbSupplierClaimTelegramRegistration(models.Model):
    _name = 'ab_supplier_claim_telegram_registration'
    _description = 'Supplier Claim Telegram Registration'
    _rec_name = 'eplus_code'
    _order = 'write_date desc'

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
        search='_search_telegram_connected',
        compute_sudo=True,
    )
    telegram_chat_id = fields.Char(
        string='Telegram Chat ID',
        compute='_compute_telegram_link_fields',
        readonly=True,
        compute_sudo=True,
    )
    telegram_username = fields.Char(
        string='Telegram Username',
        compute='_compute_telegram_link_fields',
        readonly=True,
        compute_sudo=True,
    )
    linked_at = fields.Datetime(
        string='Linked At',
        compute='_compute_telegram_link_fields',
        readonly=True,
        compute_sudo=True,
    )
    manager_department = fields.Selection([
        ('inventory', 'Inventory'),
        ('purchase', 'Purchase'),
        ('suppliers', 'Suppliers'),
        ('bank_accounts', 'Bank Accounts'),
        ('tax_accounts', 'Tax Accounts'),
    ], string='Manager at')
    workflow_department = fields.Selection([
        ('inventory', 'Inventory'),
        ('purchase', 'Purchase'),
        ('suppliers', 'Suppliers'),
        ('bank_accounts', 'Bank Accounts'),
        ('tax_accounts', 'Tax Accounts'),
    ], string='Employee at', copy=False)
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
        chat_id = str(message_data.get('telegram_chat_id') or '').strip()
        telegram_user_id = str(message_data.get('telegram_user_id') or '').strip()
        username = (message_data.get('username') or '').strip()
        self.env['ab_hr_bot'].sudo().register_employee_chat(
            employee.id,
            chat_id,
            telegram_username=username,
            employee_ref_id=employee.accid or employee.id,
        )
        employee.sudo().write({
            'telegram_chat_id': chat_id or False,
            'telegram_user_id': telegram_user_id or chat_id or False,
            'telegram_username': username or False,
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

    @api.model
    def _sync_telegram_bot_users(self):
        links = self.env['ab_hr_bot'].sudo().search([
            ('employee_id', '!=', False),
            ('chat_id', '!=', False),
            ('chat_id', '!=', ''),
        ])
        employee_ids = [link.employee_id for link in links]
        employees = self.env['ab_hr_employee'].sudo().browse(employee_ids).exists()
        existing_employee_ids = set(self.sudo().search([
            ('employee_id', 'in', employees.ids or [0]),
        ]).mapped('employee_id').ids)
        created = 0
        for employee in employees:
            if employee.id in existing_employee_ids:
                continue
            self.sudo().create({'employee_id': employee.id})
            created += 1
        return created

    @api.onchange('manager_department')
    def _onchange_manager_department(self):
        for rec in self:
            if rec.manager_department:
                rec.workflow_department = rec.manager_department

    @api.model
    def _get_workflow_department_group_xmlids(self):
        return [
            ('inventory', 'ab_supplier_claim_workflow.supplier_claim_group_inventory'),
            ('purchase', 'ab_supplier_claim_workflow.supplier_claim_group_purchase'),
            ('suppliers', 'ab_supplier_claim_workflow.supplier_claim_group_suppliers'),
            ('tax_accounts', 'ab_supplier_claim_workflow.supplier_claim_group_tax_accounts'),
            ('bank_accounts', 'ab_supplier_claim_workflow.supplier_claim_group_bank_acc'),
        ]

    @api.model
    def _sync_workflow_group_employees(self):
        Employee = self.env['ab_hr_employee'].sudo()
        created = 0
        for dept_code, group_xmlid in self._get_workflow_department_group_xmlids():
            group = self.env.ref(group_xmlid, raise_if_not_found=False)
            if not group:
                continue
            employees = Employee.search([
                ('user_id', 'in', group.sudo().user_ids.ids or [0]),
                ('active', '=', True),
            ])
            for employee in employees:
                existing = self.sudo().search([('employee_id', '=', employee.id)], limit=1)
                if existing:
                    if existing.manager_department and existing.workflow_department != existing.manager_department:
                        existing.write({'workflow_department': existing.manager_department})
                    elif not existing.workflow_department:
                        existing.write({'workflow_department': dept_code})
                    continue
                self.sudo().create({
                    'employee_id': employee.id,
                    'workflow_department': dept_code,
                })
                created += 1
        return created

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        self._sync_telegram_bot_users()
        self._sync_workflow_group_employees()
        return super().web_search_read(domain, specification, offset=offset, limit=limit, order=order, count_limit=count_limit)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'eplus_code' in vals and not vals.get('employee_id'):
                employee = self._find_employee_by_telegram_code(vals['eplus_code'])
                if employee:
                    vals['employee_id'] = employee.id
            if vals.get('manager_department'):
                vals['workflow_department'] = vals['manager_department']
        records = super().create(vals_list)
        return records

    def write(self, vals):
        vals = dict(vals)
        if vals.get('manager_department'):
            vals['workflow_department'] = vals['manager_department']
        return super().write(vals)

    def action_clear_manager_department(self):
        self.write({'manager_department': False})
        return True

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

    @api.depends('employee_id')
    def _compute_telegram_connected(self):
        for rec in self:
            rec.telegram_connected = rec._employee_has_real_telegram_identity(rec.employee_id)

    @api.depends('employee_id')
    def _compute_telegram_link_fields(self):
        for rec in self:
            link = rec._get_employee_telegram_link(rec.employee_id)
            rec.telegram_chat_id = link.chat_id if link else False
            rec.telegram_username = link.telegram_username if link else False
            rec.linked_at = link.create_date if link else False

    @api.model
    def _search_telegram_connected(self, operator, value):
        linked_employee_ids = set(
            self.env['ab_hr_bot'].sudo().search([
                ('chat_id', '!=', False),
                ('chat_id', '!=', ''),
            ]).mapped('employee_id')
        )
        connected = operator not in ('!=', 'not in') if value else operator in ('!=', 'not in')
        return [('employee_id', 'in' if connected else 'not in', list(linked_employee_ids) or [0])]

    @api.model
    def _get_employee_telegram_link(self, employee):
        employee = employee.sudo().exists() if employee else employee
        if not employee:
            return self.env['ab_hr_bot']
        return self.env['ab_hr_bot'].sudo().search([
            ('employee_id', '=', employee.id),
            ('chat_id', '!=', False),
            ('chat_id', '!=', ''),
        ], limit=1)

    @api.model
    def _get_employee_telegram_chat_id(self, employee):
        link = self._get_employee_telegram_link(employee)
        return link.chat_id if link else False

    @api.model
    def _get_employee_telegram_username(self, employee):
        link = self._get_employee_telegram_link(employee)
        return link.telegram_username if link else False

    @api.model
    def _employee_has_real_telegram_identity(self, employee):
        return bool(employee and self._get_employee_telegram_link(employee))

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
        job_dept_map = {
            'نائب مدير المخازن': 'inventory',
            'مدير قسم حسابات الضرائب': 'tax_accounts',
            'مدير قسم حسابات الموردين': 'suppliers',
            'مدير قسم حسابات البنوك': 'bank_accounts',
            'نائب مدير قطاع المشتريات والتجارية': 'purchase',
        }
        created = 0
        for job_name, dept_code in job_dept_map.items():
            jobs = self.env['ab_hr_job'].sudo().search([('name', '=', job_name)])
            if not jobs:
                continue
            employees = self.env['ab_hr_employee'].sudo().search([('job_id', 'in', jobs.ids)])
            for employee in employees:
                existing = self.sudo().search([('employee_id', '=', employee.id)], limit=1)
                if existing:
                    if not existing.manager_department:
                        existing.write({'manager_department': dept_code})
                    continue
                rec = self.sudo().create({
                    'employee_id': employee.id,
                    'manager_department': dept_code,
                })
                if rec:
                    created += 1
        return {'created': created}

    @api.model
    def migrate_legacy_registration_data(self):
        return True

    @api.model
    def _cron_import_telegram_registrations(self):
        return True

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
