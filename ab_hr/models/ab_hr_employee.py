# -*- coding: utf-8 -*-
import datetime
import itertools
import logging
import re

from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError
from .extra_functions import get_modified_name

CC_MIRRORED_FIELDS = ['mobile_phone', 'work_email', 'work_phone', 'english_name', 'birthday', 'religion', 'gender',
                      'identification_id']

_logger = logging.getLogger(__name__)


class Employees(models.Model):
    _name = 'ab_hr_employee'
    _description = 'ab_hr_employee'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _parent_store = True
    _parent_name = "parent_id"  # optional if field is 'parent_id'
    parent_path = fields.Char(index=True)

    parent_id = fields.Many2one('ab_hr_employee', string='Manager',
                                ondelete='restrict',
                                index=True,
                                readonly=False,
                                store=True,
                                )

    child_ids = fields.One2many(
        'ab_hr_employee', 'parent_id',
        string='Children')

    name = fields.Char(required=True)
    costcenter_id = fields.Many2one('ab_costcenter', index=True, )
    user_id = fields.Many2one('res.users', string='Related User',
                              )
    cc_id = fields.Many2one('ab_costcenter')

    parent_department_id = fields.Many2one(related='department_id.parent_id', string='Superior Department')
    accid = fields.Char(related='costcenter_id.code', string='ePlus Code')
    barcode = fields.Char(string="Badge ID", help="ID used for employee identification.",
                          groups="base.group_user", copy=False)
    bc_id = fields.Integer(related='costcenter_id.bc_id', string='ePlus ID')
    user_line_owner = fields.Many2one('res.users', domain=lambda self: [('account_auth_ids', '!=', False)], )
    payment_name = fields.Char(groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_accountant')
    payment_no = fields.Char(groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_accountant')
    telegram_chat_id = fields.Char(
        string="Telegram Chat ID",
        groups="ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_sheet_admin",
        copy=False,
    )
    telegram_user_id = fields.Char(
        string="Telegram User ID",
        groups="ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_sheet_admin",
        copy=False,
    )
    telegram_username = fields.Char(
        string="Telegram Username",
        groups="ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_sheet_admin",
        copy=False,
    )
    telegram_linked_at = fields.Datetime(
        string="Telegram Linked At",
        groups="ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_sheet_admin",
        readonly=True,
        copy=False,
    )

    work_phone = fields.Char(groups='ab_hr.group_ab_hr_secretary',
                             inverse='_inverse_costcenter_info', store=True, )
    graduate = fields.Char()

    # Costcenter Fields (كلها computed + inverse + store)
    work_email = fields.Char(
        inverse='_inverse_costcenter_info', store=True,
    )

    mobile_phone = fields.Char(
        string='Work Mobile',

        inverse='_inverse_costcenter_info', store=True,
    )
    english_name = fields.Char(

        inverse='_inverse_costcenter_info', store=True,
    )
    religion = fields.Selection(
        selection=[('muslim', 'Muslim'), ('christian', 'Christian'), ('other', 'Other')],

        inverse='_inverse_costcenter_info', store=True,
    )
    gender = fields.Selection(
        selection=[('male', 'Male'), ('female', 'Female')],

        inverse='_inverse_costcenter_info', store=True,
    )
    identification_id = fields.Char(

        inverse='_inverse_costcenter_info', store=True,
        groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_personnel_spec,ab_hr.group_ab_hr_payroll_accountant',
    )
    birthday = fields.Date(
        string='Birthdate',

        inverse='_inverse_costcenter_info', store=True,
        groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_personnel_spec,ab_hr.group_ab_hr_payroll_accountant',
    )
    # One2many fields
    job_occupied_ids = fields.One2many(
        comodel_name='ab_hr_job_occupied',
        inverse_name='employee_id',
        readonly=True)
    emp_history_ids = fields.One2many(comodel_name='ab_hr_emp_history', inverse_name='employee_id')
    emp_doc_status_ids = fields.One2many(comodel_name='ab_hr_emp_doc_status', inverse_name='employee_id')

    main_occupied_job_id = fields.Many2one('ab_hr_job_occupied',
                                           store=True,

                                           readonly=True)

    # COMPUTED STORED FIELDS
    job_id = fields.Many2one('ab_hr_job', store=True)
    department_id = fields.Many2one('ab_hr_department', store=True)

    mod_name = fields.Char(store=True)

    # COMPUTED SEARCHABLE FIELDS
    hiring_date = fields.Date(related='main_occupied_job_id.hiring_date')
    termination_date = fields.Date(related='main_occupied_job_id.termination_date')
    issue_date = fields.Date(related='main_occupied_job_id.issue_date')
    job_status = fields.Selection(related='main_occupied_job_id.job_status')
    territory = fields.Selection(related='main_occupied_job_id.territory')
    is_working = fields.Boolean(search='_search_is_working')
    is_docs_complete = fields.Boolean(compute='_compute_is_docs_complete')

    address_text = fields.Char(string='Address: ')
    khazna_subscription = fields.Boolean(default=False, groups='ab_hr.group_ab_hr_co')
    active = fields.Boolean(default=True)

    # insurance Fields
    insurance_info_ids = fields.One2many('ab_hr_insurance_info', inverse_name='employee_id')
    insurance_status = fields.Boolean(store=True, )
    insurance_type = fields.Selection(selection=[('abdin', 'Abdin Pharmacies'), ('other', 'Other')])
    insurance_branch = fields.Char()
    insurance_no = fields.Char()
    insurance_start = fields.Date()
    internal_working_employee = fields.Boolean(compute='_compute_internal_working_employee',
                                               search='_search_internal_working_employee',
                                               compute_sudo=True)

    parent_internal_working_employee = fields.Boolean(related='parent_id.internal_working_employee',
                                                      string='Manager is Wroking?')
    manual_manager = fields.Boolean(default=False)
    supervision_type = fields.Selection([
        ('direct', 'Direct'),
        ('indirect', 'Indirect'),
        ('indirect_to_subordinate', 'Indirect to subordinate'),
        ('myself', 'Myself'),
        ('workplace_manager_job', 'Workplace manager job'),
        ('other', 'Other'),
    ], string="Supervision Type",
        compute="_compute_supervision_type",
        search="_search_supervision_type")

    @api.depends('parent_id', 'department_id')
    def _compute_supervision_type(self):
        curr_user = self.env.user
        curr_employees = self.search([('user_id', '=', curr_user.id)])

        is_reviewer = curr_user.has_group('ab_hr.group_ab_hr_payroll_reviewer')
        is_co = curr_user.has_group('ab_hr.group_ab_hr_co')
        is_recruiter = curr_user.has_group('ab_hr.group_ab_hr_recruiter')

        children = False

        for rec in self:
            # two levels up
            direct_parent = rec.parent_id
            indirect_parent = rec.parent_id.parent_id

            if rec.user_id.id == curr_user.id:
                rec.supervision_type = 'myself'
            elif direct_parent in curr_employees:
                rec.supervision_type = 'direct'
            elif indirect_parent in curr_employees:
                rec.supervision_type = 'indirect'
            elif is_reviewer or is_co or (
                    is_recruiter and rec.job_id and curr_user in rec.job_id.access_history_user_ids):
                rec.supervision_type = 'other'
            else:
                if not children:
                    children = self.search([('id', 'child_of', curr_employees.ids)])
                if rec in children:
                    rec.supervision_type = 'indirect_to_subordinate'
                else:
                    rec.supervision_type = False

    def _search_supervision_type(self, operator, value):
        valid_ops = ('=', '!=', 'in', 'not in')
        if operator not in valid_ops:
            return [('id', '=', 0)]

        if operator in ('in', 'not in'):
            requested = set(value or [])
        else:
            requested = {value} if value is not False else {False}

        env = self.env
        Employee = self
        Job = env['ab_hr_job']
        search_emp = Employee.search

        curr_user = env.user

        curr_emp_ids = set(search_emp([('user_id', '=', curr_user.id)]).ids)

        ids_myself = set(curr_emp_ids)
        ids_direct = set()
        ids_indirect = set()
        if curr_emp_ids:
            ids_direct = set(search_emp([('parent_id', 'in', list(curr_emp_ids))]).ids)
            ids_indirect = set(search_emp([('parent_id.parent_id', 'in', list(curr_emp_ids))]).ids)

        is_reviewer = curr_user.has_group('ab_hr.group_ab_hr_payroll_reviewer')
        is_co = curr_user.has_group('ab_hr.group_ab_hr_co')
        is_recruiter = curr_user.has_group('ab_hr.group_ab_hr_recruiter')

        ids_early = ids_myself | ids_direct | ids_indirect
        ids_other = set()

        all_emp_ids = set(search_emp([]).ids)  # do once if you’ll need it anyway

        if is_reviewer or is_co:
            ids_other = all_emp_ids - ids_early
        elif is_recruiter:
            job_ids = Job.search([('access_history_user_ids', 'in', curr_user.id)]).ids
            if job_ids:
                ids_other = set(search_emp([('job_id', 'in', job_ids)]).ids) - ids_early

        ids_indirect_to_subordinate = set()
        if curr_emp_ids:
            children_ids = set(search_emp([('id', 'child_of', list(curr_emp_ids))]).ids)
            ids_indirect_to_subordinate = children_ids - ids_early - ids_other

        buckets = {
            'myself': ids_myself,
            'direct': ids_direct,
            'indirect': ids_indirect,
            'other': ids_other,
            'indirect_to_subordinate': ids_indirect_to_subordinate,
        }

        all_positive = set().union(*buckets.values())
        ids_false = all_emp_ids - all_positive

        def resolve_ids(req_set):
            res = set()
            for tag in req_set:
                if tag is False:
                    res |= ids_false
                elif tag in buckets:
                    res |= buckets[tag]
            return res

        target_ids = resolve_ids(requested)

        if operator in ('=', 'in'):
            return [('id', 'in', list(target_ids))] if target_ids else [('id', '=', 0)]
        else:
            return [] if not target_ids else [('id', 'not in', list(target_ids))]

    @api.model
    def _normalize_telegram_employee_code(self, value):
        return re.sub(r"[^0-9A-Za-z]+", "", value or "").upper()

    @api.model
    def _extract_telegram_employee_code(self, text):
        cleaned = (text or "").strip()
        if not cleaned:
            return False
        normalized = " ".join(cleaned.replace("_", " ").replace("-", " ").split())
        parts = normalized.split()
        if len(parts) == 1 and self._normalize_telegram_employee_code(parts[0]) and any(char.isdigit() for char in parts[0]):
            return parts[0]
        command_words = {"employee", "emp", "code", "link", "hr", "موظف", "كود", "ربط"}
        if not any(part.lower() in command_words for part in parts):
            return False
        candidates = [part for part in parts if part.lower() not in command_words]
        return candidates[-1] if candidates else False

    @api.model
    def _find_employee_by_telegram_code(self, code):
        normalized_code = self._normalize_telegram_employee_code(code)
        if not normalized_code:
            return self
        fields_to_check = [field for field in ("barcode", "identification_id", "accid") if field in self._fields]
        employee = self.sudo().search([("costcenter_id.code", "=", code), ("active", "=", True)], limit=2)
        if len(employee) == 1:
            return employee
        for field_name in fields_to_check:
            employee = self.sudo().search([(field_name, "=", code), ("active", "=", True)], limit=2)
            if len(employee) == 1:
                return employee
        candidates = self.sudo().search([("active", "=", True)])
        matched = candidates.filtered(
            lambda emp: (
                self._normalize_telegram_employee_code(emp.costcenter_id.code) == normalized_code
                or any(self._normalize_telegram_employee_code(emp[field_name]) == normalized_code for field_name in fields_to_check)
            )
        )
        if len(matched) == 1:
            return matched
        return self

    @api.model
    def _find_telegram_chat_message_by_employee_code(self, code):
        if "ab_telegram_chat_message" not in self.env:
            return False
        normalized_code = self._normalize_telegram_employee_code(code)
        if not normalized_code:
            return False
        messages = self.env["ab_telegram_chat_message"].sudo().search(
            [
                ("chat_type", "=", "private"),
                ("content_text", "!=", False),
            ],
            order="message_datetime desc, id desc",
            limit=100,
        )
        return messages.filtered(
            lambda message: self._normalize_telegram_employee_code(message.content_text) == normalized_code
        )[:1]

    @api.model
    def link_employee_from_telegram_chat_message(self, code):
        message = self._find_telegram_chat_message_by_employee_code(code)
        if not message:
            return {"handled": False}
        return self.bot_process_employee_telegram_link(
            telegram_user_id=message.telegram_user_id,
            telegram_chat_id=message.telegram_chat_id,
            text=message.content_text,
            username=message.username,
        )

    @api.model
    def _prepare_employee_telegram_message_data(self, message):
        message = message or {}
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if sender.get("is_bot") or chat.get("type") != "private":
            return False
        text = (message.get("text") or "").strip()
        if not text:
            return False
        return {
            "telegram_user_id": str(sender.get("id") or chat.get("id") or "").strip(),
            "telegram_chat_id": str(chat.get("id") or "").strip(),
            "text": text,
            "username": (sender.get("username") or "").strip(),
        }

    @api.model
    def _get_message_from_telegram_update(self, update):
        update = update or {}
        return update.get("message") or update.get("edited_message") or {}

    @api.model
    def import_employee_telegram_updates(self, limit=100, acknowledge=True):
        """One-time Telegram import for HR employee chat IDs.

        Employees send their HR code to the bot. This method pulls pending
        Telegram updates, matches the message text to an employee code, and
        stores the Telegram identifiers on ab_hr_employee.
        """
        result = {
            "updates_seen": 0,
            "linked": 0,
            "ignored": 0,
            "not_employee_code": 0,
            "employee_not_found": 0,
            "employee_not_active": 0,
            "errors": [],
            "linked_employee_ids": [],
        }
        if "ab.telegram.service" not in self.env:
            result["errors"].append(_("Telegram service is not installed."))
            return result

        updates = self.env["ab.telegram.service"].sudo().get_updates(limit=limit, timeout=0)
        result["updates_seen"] = len(updates)
        last_update_id = False
        for update in updates:
            if update.get("update_id") is not None:
                last_update_id = update["update_id"]
            message_data = self._prepare_employee_telegram_message_data(
                self._get_message_from_telegram_update(update)
            )
            if not message_data:
                result["ignored"] += 1
                continue
            code = self._extract_telegram_employee_code(message_data["text"])
            if not code:
                result["not_employee_code"] += 1
                continue
            employee = self._find_employee_by_telegram_code(code)
            if not employee:
                result["employee_not_found"] += 1
                result["errors"].append(_("No active employee was found for code: %s") % code)
                continue
            payload = self.bot_process_employee_telegram_link(**message_data)
            note = payload.get("note")
            if note == "employee_telegram_linked":
                result["linked"] += 1
                result["linked_employee_ids"].append(employee.id)
            elif note == "employee_not_active":
                result["employee_not_active"] += 1
                result["errors"].append(payload.get("text") or _("Employee is not active."))
            elif note == "employee_not_found":
                result["employee_not_found"] += 1
                result["errors"].append(payload.get("text") or _("Employee was not found."))
            else:
                result["ignored"] += 1

        if acknowledge and last_update_id is not False:
            self.env["ab.telegram.service"].sudo().get_updates(
                offset=last_update_id + 1,
                limit=1,
                timeout=0,
            )
            result["acknowledged_to"] = last_update_id + 1
        result["linked_employee_ids"] = list(dict.fromkeys(result["linked_employee_ids"]))
        return result

    @api.model
    def _cron_import_employee_telegram_updates(self):
        if "ab.telegram.service" not in self.env:
            return False
        result = self.sudo().import_employee_telegram_updates(limit=100, acknowledge=True)
        if result.get("updates_seen") or result.get("linked") or result.get("errors"):
            _logger.info(
                "ab_hr: employee Telegram import updates_seen=%s linked=%s ignored=%s not_employee_code=%s "
                "employee_not_found=%s employee_not_active=%s errors=%s",
                result.get("updates_seen"),
                result.get("linked"),
                result.get("ignored"),
                result.get("not_employee_code"),
                result.get("employee_not_found"),
                result.get("employee_not_active"),
                result.get("errors"),
            )
        return result

    @api.model
    def bot_process_employee_telegram_link(
        self,
        telegram_user_id,
        telegram_chat_id,
        text,
        username="",
        **kwargs
    ):
        code = self._extract_telegram_employee_code(text)
        if not code:
            return {"handled": False}
        employee = self._find_employee_by_telegram_code(code)
        if not employee:
            return {
                "handled": True,
                "text": _("No active employee was found for code: %s") % code,
                "note": "employee_not_found",
            }
        if employee.job_status and employee.job_status != "active":
            return {
                "handled": True,
                "text": _("Employee code %s is not active.") % code,
                "note": "employee_not_active",
            }
        employee.sudo().write({
            "telegram_chat_id": str(telegram_chat_id or "").strip() or False,
            "telegram_user_id": str(telegram_user_id or "").strip() or False,
            "telegram_username": (username or "").strip() or False,
            "telegram_linked_at": fields.Datetime.now(),
        })
        if "ab_hr_bot" in self.env:
            self.env["ab_hr_bot"].sudo().try_register_employee_chat(
                employee.id,
                str(telegram_chat_id or "").strip(),
                telegram_username=(username or "").strip() or False,
            )
        return {
            "handled": True,
            "text": _("Telegram account linked to employee %s.") % employee.display_name,
            "note": "employee_telegram_linked",
        }

    def _check_edit_rights(self):
        if not self.env.user.has_group('ab_hr.group_ab_hr_co'):
            raise AccessError(_("You don't have permission to edit these fields."))

    def _inverse_costcenter_info(self):
        self._check_edit_rights()

        for rec in self.filtered('costcenter_id'):
            cc = rec.costcenter_id.sudo()
            vals = {}
            for fld in CC_MIRRORED_FIELDS:
                current = getattr(cc, fld, False)
                new_val = rec[fld] or False
                if current != new_val:
                    vals[fld] = new_val

            if vals:
                # context اختياري لتفادي أي منطق ترابطي خاص بك إن لزم
                cc.with_context(from_employee_inverse=True).write(vals)

    @api.model
    def compute_responsible(self, department, employee_self_id):
        parent = False

        if department.manager_id and department.manager_id.id != employee_self_id:
            parent = department.manager_id
        if not parent:
            parent = department.parent_id.manager_id
        if not parent:
            parent = department.parent_id.parent_id.manager_id

        if parent:
            return parent.id
        else:
            return False

    def _search_is_working(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        sql = """
            select distinct employee_id from ab_hr_job_occupied job 
                where job.termination_date is null
        """
        self.env.cr.execute(sql)
        employees = self.env.cr.fetchall()
        employee_ids = [row[0] for row in employees]
        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', employee_ids)]

    @api.depends('job_id')
    def _compute_internal_working_employee(self):
        for rec in self:
            curr_job = rec.job_occupied_ids.filtered(lambda job: job.job_id.internal_job and not job.termination_date)
            rec.internal_working_employee = bool(curr_job)

    def _search_internal_working_employee(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        self.flush()
        sql = """
            select distinct employee_id 
            from ab_hr_job_occupied job
            left join ab_hr_job hj on job.job_id = hj.id
                where job.termination_date is null and hj.internal_job=True 
        """
        self.env.cr.execute(sql)
        employees = self.env.cr.fetchall()
        employee_ids = list(itertools.chain.from_iterable(employees))
        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', employee_ids)]

    @api.depends('emp_doc_status_ids')
    def _compute_is_docs_complete(self):
        #  doc.status are (missing, existing, excluded, temp_excluded)
        for rec in self:
            is_docs_complete = False
            for doc in rec.emp_doc_status_ids:
                is_doc_expired = doc.expiry_date and doc.expiry_date < datetime.date.today()
                is_doc_missing = doc.status == 'missing'
                if is_doc_missing or is_doc_expired:
                    is_docs_complete = False
                    break
                else:
                    is_docs_complete = True
            rec.is_docs_complete = is_docs_complete

    @api.model
    def _search_display_name(self, operator, value):
        mod_name = get_modified_name(value)
        return [
            '|', '|',
            ('mod_name', operator, mod_name),
            ('name', operator, value),
            ('accid', '=ilike', value),
        ]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        vals = []
        docs = self.env['ab_hr_emp_doc'].search([])

        for doc in docs:
            vals.append((0, 0, {'emp_doc_id': doc.id, 'status': 'missing'}))
        res.update({'emp_doc_status_ids': vals})
        return res

    def write(self, values):
        res = super().write(values)
        if 'user_id' in values:
            for rec in self:
                if rec.costcenter_id:
                    rec.sudo().costcenter_id.user_id = rec.user_id
        return res

    @api.model
    def create(self, values):
        res = super().create(values)
        if res.costcenter_id and res.user_id:
            res.sudo().costcenter_id.user_id = res.user_id
        return res
