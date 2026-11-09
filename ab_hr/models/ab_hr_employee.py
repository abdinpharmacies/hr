# -*- coding: utf-8 -*-
import datetime
import itertools

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError, ValidationError
from .extra_functions import get_modified_name

CC_MIRRORED_FIELDS = ['mobile_phone', 'work_email', 'work_phone', 'english_name', 'birthday', 'religion', 'gender',
                      'identification_id']


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
                                compute="_compute_parent_id",
                                readonly=False,
                                store=True,
                                )

    child_ids = fields.One2many(
        'ab_hr_employee', 'parent_id',
        string='Children')

    name = fields.Char(required=True)
    costcenter_id = fields.Many2one('ab_costcenter', index=True,
                                    readonly=lambda self: not self.user.has_group(
                                        'ab_hr.group_ab_hr_co')
                                    )
    user_id = fields.Many2one('res.users', string='Related User',
                              readonly=lambda self: not self.user.has_group('base.group_system'))
    cc_id = fields.Many2one('ab_costcenter')

    parent_department_id = fields.Many2one(related='department_id.parent_id', string='Superior Department')
    accid = fields.Char(related='costcenter_id.code', string='ePlus Code')
    barcode = fields.Char(string="Badge ID", help="ID used for employee identification.",
                          groups="base.group_user", copy=False)
    bc_id = fields.Integer(related='costcenter_id.bc_id', string='ePlus ID')

    work_phone = fields.Char(groups='ab_hr.group_ab_hr_secretary',
                             compute='_compute_costcenter_info', compute_sudo=True,
                             inverse='_inverse_costcenter_info', store=True, )
    graduate = fields.Char()

    # Costcenter Fields (كلها computed + inverse + store)
    work_email = fields.Char(
        compute='_compute_costcenter_info', compute_sudo=True,
        inverse='_inverse_costcenter_info', store=True,
    )

    mobile_phone = fields.Char(
        string='Work Mobile',
        compute='_compute_costcenter_info', compute_sudo=True,
        inverse='_inverse_costcenter_info', store=True,
    )
    english_name = fields.Char(
        compute='_compute_costcenter_info', compute_sudo=True,
        inverse='_inverse_costcenter_info', store=True,
    )
    religion = fields.Selection(
        selection=[('muslim', 'Muslim'), ('christian', 'Christian'), ('other', 'Other')],
        compute='_compute_costcenter_info', compute_sudo=True,
        inverse='_inverse_costcenter_info', store=True,
    )
    gender = fields.Selection(
        selection=[('male', 'Male'), ('female', 'Female')],
        compute='_compute_costcenter_info', compute_sudo=True,
        inverse='_inverse_costcenter_info', store=True,
    )
    identification_id = fields.Char(
        compute='_compute_costcenter_info', compute_sudo=True,
        inverse='_inverse_costcenter_info', store=True,
        groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_personnel_spec,ab_hr.group_ab_hr_payroll_accountant',
    )
    birthday = fields.Date(
        string='Birthdate',
        compute='_compute_costcenter_info', compute_sudo=True,
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
                                           compute='_compute_main_job_data',
                                           readonly=True)

    # COMPUTED STORED FIELDS
    job_id = fields.Many2one('ab_hr_job', compute='_compute_main_job_data', store=True)
    department_id = fields.Many2one('ab_hr_department', compute='_compute_main_job_data', store=True)

    mod_name = fields.Char(compute='_compute_mod_name', store=True)

    # COMPUTED SEARCHABLE FIELDS
    hiring_date = fields.Date(related='main_occupied_job_id.hiring_date')
    termination_date = fields.Date(related='main_occupied_job_id.termination_date')
    issue_date = fields.Date(related='main_occupied_job_id.issue_date')
    job_status = fields.Selection(related='main_occupied_job_id.job_status')
    territory = fields.Selection(related='main_occupied_job_id.territory')
    is_working = fields.Boolean(compute='_compute_main_job_data', compute_sudo=True, search='_search_is_working')
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

    @api.depends('costcenter_id',
                 'costcenter_id.mobile_phone',
                 'costcenter_id.work_email',
                 'costcenter_id.work_phone',
                 'costcenter_id.birthday',
                 'costcenter_id.english_name',
                 'costcenter_id.religion',
                 'costcenter_id.gender',
                 'costcenter_id.identification_id', )
    def _compute_costcenter_info(self):
        for rec in self:
            for fld in CC_MIRRORED_FIELDS:
                val = getattr(rec.costcenter_id, fld, None)
                if val:
                    setattr(rec, fld, val)

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

    @api.depends('manual_manager', 'department_id.manager_id', 'department_id.parent_id.manager_id', 'job_occupied_ids')
    def _compute_parent_id(self):
        for rec in self:
            if rec.manual_manager and rec.parent_id.internal_working_employee:
                continue
            rec.parent_id = rec.compute_responsible(rec.department_id, rec.id)

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

    @api.depends('job_id')
    def _compute_is_working(self):
        for rec in self:
            rec.is_working = bool(rec.job_id)

    def _search_is_working(self, operator, val):
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        self.flush_model()
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
        # Odoo 19 canonicalizes Boolean searches to membership domains.
        if operator in ('in', 'not in'):
            values = set(val)
            if not values or values == {False, True}:
                matches_all = bool(values) == (operator == 'in')
                return [(1, '=', 1)] if matches_all else [(0, '=', 1)]
            val = True in values
            operator = '=' if operator == 'in' else '!='
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        self.flush_model()
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

    @api.depends('name')
    def _compute_mod_name(self):
        for rec in self:
            rec.mod_name = get_modified_name(rec.name)

    _ab_hr_employees_employee_unique = models.Constraint('check(1=1)', 'Employee CAN NOT BE DUPLICATED!')

    @api.depends('job_occupied_ids')
    def _compute_main_job_data(self):
        for rec in self:
            jobs = rec.job_occupied_ids.search([('employee_id', '=', rec.id),
                                                ('job_status', '=', 'active'),
                                                ('is_main_job', '=', True),
                                                ('job_id.internal_job', '=', True),
                                                ], order='hiring_date desc')
            if not jobs:
                jobs = rec.job_occupied_ids.search([('employee_id', '=', rec.id),
                                                    ('job_status', '=', 'active'),
                                                    ], order='hiring_date desc')
            if not jobs:
                jobs = rec.job_occupied_ids.search([
                    ('employee_id', '=', rec.id),
                    ('is_main_job', '=', True),
                ], order='hiring_date desc')

            if not jobs:
                jobs = rec.job_occupied_ids.search([('employee_id', '=', rec.id), ], order='hiring_date desc')

            if jobs:
                target_job = jobs[0]
                rec.main_occupied_job_id = target_job.id
                rec.job_id = target_job.job_id.id
                rec.department_id = target_job.workplace.id
                rec.is_working = target_job.job_status == 'active'
            else:
                rec.main_occupied_job_id = False
                rec.job_id = False
                rec.department_id = False
                rec.is_working = False

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        mod_name = get_modified_name(name)
        args += ['|', '|',
                 ('mod_name', operator, mod_name),
                 ('name', operator, name),
                 ('accid', '=ilike', name),
                 ]

        ids = (self.with_user(name_get_uid) if name_get_uid else self).search(args, limit=limit).ids
        return ids

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Expose the existing search order through the Odoo 19 public API."""
        ids = self._name_search(name, args=domain, operator=operator, limit=limit)
        return [(record.id, record.display_name) for record in self.browse(ids)]

    @api.model
    def _search_display_name(self, operator, value):
        """Keep code/barcode/name matching in relational search domains too."""
        if operator in ('in', 'not in') and isinstance(value, (list, tuple)):
            domain = fields.Domain.OR(self._search_display_name('=', item) for item in value)
            return list(~domain if operator == 'not in' else domain)
        ids = self._name_search(value or '', operator=operator, limit=None)
        return [('id', 'in', ids)]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        vals = []
        docs = self.env['ab_hr_emp_doc'].search([])

        for doc in docs:
            vals.append((0, 0, {'emp_doc_id': doc.id, 'status': 'missing'}))
        res.update({'emp_doc_status_ids': vals})
        return res

    def btn_add_docs(self):
        docs = self.env['ab_hr_emp_doc'].search([])
        self.ensure_one()

        for doc in docs:

            if doc.id not in self.emp_doc_status_ids.mapped('emp_doc_id.id'):
                self.emp_doc_status_ids.create({'emp_doc_id': doc.id, 'status': 'missing'})

    def btn_add_job(self):

        return {
            'name': _("Create New Job"),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_hr_job_wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_employee_id': self.id,
                'default_type_of_action': '1',
            }
        }

    def btn_update_user_name(self):
        if self.env.user.has_group('base.group_system'):
            self.user_id.name = self.name

    def write(self, values):
        res = super().write(values)
        if 'user_id' in values:
            for rec in self:
                if rec.costcenter_id:
                    rec.sudo().costcenter_id.user_id = rec.user_id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_hr_employees(values)
        return records

    def _create_one_ab_hr_employees(self, values):
        res = super().create(values)
        if res.costcenter_id and res.user_id:
            res.sudo().costcenter_id.user_id = res.user_id
        return res
