# -*- coding: utf-8 -*-
import datetime
import itertools
from collections.abc import Iterable

from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError, AccessError
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
                                readonly=False,
                                store=True,
                                )

    child_ids = fields.One2many(
        'ab_hr_employee', 'parent_id',
        string='Children')

    name = fields.Char(required=False)
    costcenter_id = fields.Many2one('ab_costcenter', index=True, )
    user_id = fields.Many2one('ab_users', string='Related User',
                              )
    cc_id = fields.Many2one('ab_costcenter')

    parent_department_id = fields.Many2one(related='department_id.parent_id', string='Superior Department')
    accid = fields.Char(related='costcenter_id.code', string='ePlus Code')
    barcode = fields.Char(string="Badge ID", help="ID used for employee identification.",
                          groups="base.group_user", copy=False)
    bc_id = fields.Integer(related='costcenter_id.bc_id', string='ePlus ID')
    user_line_owner = fields.Many2one('ab_users')
    payment_name = fields.Char(groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_accountant')
    payment_no = fields.Char(groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_accountant')

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
        for rec in self:
            rec.supervision_type = False

    def _search_supervision_type(self, operator, value):
        return [(0, '=', 1)]

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
              select distinct employee_id
              from ab_hr_job_occupied job
              where job.termination_date is null \
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
        # self.flush()
        sql = """
              select distinct employee_id
              from ab_hr_job_occupied job
                       left join ab_hr_job hj on job.job_id = hj.id
              where job.termination_date is null
                and hj.internal_job = True \
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
        if not isinstance(value, str) and isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
            string_values = [item for item in value if isinstance(item, str)]
            if len(string_values) == 1:
                value = string_values[0]
        mod_name = get_modified_name(value)
        if not isinstance(value, str):
            return super()._search_display_name(operator, value)
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
