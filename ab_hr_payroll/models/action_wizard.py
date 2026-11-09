# -*- coding: utf-8 -*-
import datetime
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .constants import ACTION_TAKEN_ERR
import itertools
from collections import Counter

NO_OF_ALLOWED_EMPLOYEES = 100

# abdin_payroll_group_chat_id = -1001673991062
# testing_bot_group_chat_id = -787017235
CHAT_ID_KEY = "telegram_payroll_group_chat_id"


######################################################################################################################
class ActionWizard(models.Model):
    """Relation Many2many with payroll module"""
    _name = "ab_hr_action_wizard"
    _description = "ab_hr_action_wizard"
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'abdin_et.extra_tools', 'abdin_telegram']
    _rec_name = 'explain'
    _order = 'id desc'
    explain = fields.Char(required=True, tracking=True)
    payroll_month = fields.Date()
    date_begin = fields.Date()
    date_end = fields.Date()
    confirm_deletion = fields.Text()
    no_of_records = fields.Text()
    status = fields.Selection(
        selection=lambda self: self._get_selection_from_payroll())
    action_status = fields.Selection(
        selection=lambda self: self._get_selection_from_payroll(), store=True)
    action_taken = fields.Boolean(default=False, readonly=True)
    max_ratio = fields.Float(default=1.5)
    min_ratio = fields.Float(default=0.5)
    employee_id = fields.Many2many("ab_hr_employee", string="Employee")
    job_id = fields.Many2many('ab_hr_job')
    workplace = fields.Many2many('ab_hr_department')
    store_ids = fields.Many2many("ab_store")
    section = fields.Many2many("ab_hr_section")
    payment_type_id = fields.Many2one(
        'ab_hr_payment_type', string="Payment Type", )

    set_payment_type_id = fields.Many2one(
        'ab_hr_payment_type', string="Set Payment Type", )

    section_type = fields.Selection(related="section.type", store=True)
    section_value1 = fields.Float()
    section_value2 = fields.Float()
    pasted_salaries = fields.Text()
    pasted_type = fields.Selection(selection=[('employee', 'Employees'), ('salary_id', 'Salary IDs')],
                                   default='employee')
    user_line_owner = fields.Many2one('res.users', string="Payment Method",
                                      domain=lambda self: [('account_auth_ids', '!=', False)], )

    set_user_line_owner = fields.Many2one('res.users', string="Set user who will pay",
                                          domain=lambda self: [('account_auth_ids', '!=', False)], )

    comparing_start_month = fields.Date()
    comparing_end_month = fields.Date()
    for_entry_count = fields.Integer(
        compute='_compute_status_count', compute_sudo=True)
    for_manager_count = fields.Integer(
        compute='_compute_status_count', compute_sudo=True)
    suspended_salaries_count = fields.Integer(
        compute='_compute_status_count', compute_sudo=True)
    negative_salaries_count = fields.Integer(
        compute='_compute_status_count', compute_sudo=True)
    paid_count = fields.Integer(
        compute='_compute_status_count', compute_sudo=True)

    for_reviewer_count = fields.Integer(
        compute='_compute_status_count', compute_sudo=True)

    # add_exceptions = fields.Boolean()
    exceptions = fields.Text()

    def _compute_status_count(self):
        cr = self.env.cr
        cr.execute("""
        SELECT 
            status,
            count(DISTINCT (employee_id)) as count_employees
        from ab_hr_payroll group by status""")
        statuses = cr.fetchall()
        for_entry = for_manager = for_reviewer = suspended_salaries = negative_salaries = paid = 0

        for rec in self:
            for status in statuses:
                if status[0] == 'for_entry':
                    for_entry = status[1]
                if status[0] == 'for_manager':
                    for_manager = status[1]
                if status[0] == 'for_reviewer':
                    for_reviewer = status[1]
                if status[0] == 'suspended_salaries':
                    suspended_salaries = status[1]
                if status[0] == 'negative_salaries':
                    negative_salaries = status[1]
                if status[0] == 'paid':
                    paid = status[1]
            rec.for_entry_count = for_entry
            rec.for_manager_count = for_manager
            rec.for_reviewer_count = for_reviewer
            rec.suspended_salaries_count = suspended_salaries
            rec.negative_salaries_count = negative_salaries
            rec.paid_count = paid

    def btn_sal_payment_type(self):
        """
        Set Payment type: Salary - Payback - Firing - ...
        """
        self.ensure_one()
        for sal in self.web_progress_iter(self.sal_ids, msg="In Progress ..."):
            if sal.payment_type_id != self.set_payment_type_id:
                sal.payment_type_id = self.set_payment_type_id
        msg = _("""<span class='h4 text-success'>%s</span> Employees 
            <br> Set to <span class='h4 text-success'>%s</span>""") % (
            self._count_employees(self.sal_ids), self.set_payment_type_id.name)
        self.message_post(body=str(msg))

    sal_ids = fields.Many2many(
        comodel_name='ab_hr_payroll',
        string='Salaries records')
    confirm = fields.Selection([('no', 'No'), ('yes', 'Yes')], default='no')
    active = fields.Boolean(default=True)

    ##############################################################################################################
    sal_ids_text = fields.Text(
        compute='_compute_sal_ids_text', store=True, compute_sudo=True)

    @api.depends('sal_ids')
    def _compute_sal_ids_text(self):
        for rec in self:
            rec.sal_ids_text = ','.join([str(sal_id)
                                         for sal_id in rec.sal_ids.ids])

    ##############################################################################################################
    salaries_html = fields.Html(
        compute='_compute_salaries_html', compute_sudo=True)

    salaries_compare_html = fields.Html(readonly=True)

    ##############################################################################################################
    sal_count = fields.Integer(compute='_compute_sal_count',
                               string="Employees Count", compute_sudo=True, store=True)

    @api.depends('sal_ids')
    def _compute_sal_count(self):
        for action in self:
            sals = self.env['ab_hr_payroll'].sudo().read_group(
                [('id', 'in', [int(sal_id)
                               for sal_id in action.sal_ids_text.split(',') if sal_id.isnumeric()])],
                ['employee_id', 'section_value:sum'],
                ['employee_id', ]
            )

            action.sal_count = len(sals)

    ##############################################################################################################
    @staticmethod
    def _count_employees(sal_ids) -> int:
        return len(set(sal_ids.mapped('employee_id.id')))

    ##############################################################################################################
    def _get_selection_from_payroll(self):
        payroll_model = self.env['ab_hr_payroll']
        selection = payroll_model.fields_get(allfields=['status'])[
            'status']['selection']
        return selection

    ##############################################################################################################
    # GLOBAL VARIABLES
    customer_cycle = None
    domain_ok = 1
    criteria_alert = 1

    ##############################################################################################################
    # CONSTRAINS VIA OVERRIDE WRITE METHOD

    def write(self, vals):
        res = super().write(vals)
        allowed_fields = {'explain', 'set_user_line_owner', 'min_ratio', 'max_ratio', 'salaries_html',
                          'salaries_compare_html', 'comparing_start_month', 'comparing_end_month'}

        if not (
                'action_taken' in vals.keys()
                or bool(self.action_taken) is False
                or set(vals).issubset(allowed_fields)
        ):
            raise UserError(
                """YOU ALREADY DO ACTION ON THIS RECORD, PLEASE DUPLICATE ACTION AND MAKE NEW ONE!""")

        if not (self.create_uid.id == self._uid or set(vals).issubset(allowed_fields)):
            raise UserError(_('YOU CAN NOT EDIT ANOTHER USER ACTION!'))

        return res

    @api.constrains('explain')
    def action_wizard_constrains(self):
        """Add constrains
        1. Explain > 5 chars
        """
        for rec in self:
            if len(rec.explain) < 5:
                raise UserError("""Explain must be more than 5 chars!""")

    # ******************************************************************************************************
    def print_report_excel(self):
        """_summary_

        Returns:
            action: odoo xml id = report_query_xls123 in same module
        """
        self.ensure_one()
        action = self.env.ref('ab_hr_payroll.ab_hr_salary_details_report')
        action[0].report_file = self.slugify(self.explain)
        action[0].name = self.slugify(self.explain)
        return action.report_action(self)

    ##############################################################################################################
    # Search Button Method #######################################################################################

    def search_button(self):
        """ Search for salaries records

        Returns:
            dict: action_wizard odoo form view in main window 
        """
        self.ensure_one()
        domain = self.get_salaries_domain()
        if domain and domain[0]:
            salaries = self.env['ab_hr_payroll'].search(domain)
            self.write({'sal_ids': [(6, 0, salaries.ids), ], })
        self.confirm = 'no'

        return {
            'name': _('.'),
            "type": "ir.actions.act_window",
            "res_model": "ab_hr_action_wizard",
            "views": [[False, "form"]],
            "res_id": self.id,
            "target": "main",
            "context": {'domain_ok': self.domain_ok, 'criteria_alert': self.criteria_alert,
                        'form_view_initial_mode': 'edit'},
        }

    ##############################################################################################################
    def btn_show_payroll_report(self):
        """From headers' buttons show for_entry, for pay or ... 
        Returns:
            dict: ab_hr_payroll_report pivot view in current window
        """
        self.ensure_one()
        status = self.env.context.get('status')
        domain = [('status', '=', status)]
        return {
            "name": '.',
            "type": "ir.actions.act_window",
            "res_model": "ab_hr_payroll_report",
            "views": [[False, "pivot"], [False, "list"], [False, "form"], ],
            "target": "current",
            "domain": domain,
        }

    ##############################################################################################################
    def filter_button(self):
        self.ensure_one()
        if len(self.sudo().sal_ids.ids) < 1000:
            domain = [('id', 'in', self.sudo().sal_ids.ids)]
        else:
            status = self.sudo().sal_ids[0].status
            domain = self.get_salaries_domain(with_status=False)
            domain.append(('status', '=', status))
        return {
            "name": '.',
            "type": "ir.actions.act_window",
            "res_model": "ab_hr_payroll",
            "views": [[False, "pivot"], [False, "list"], [False, "form"], ],
            "target": "current",
            "domain": domain,
        }

    ##############################################################################################################
    def report_button(self):
        self.ensure_one()
        if len(self.sudo().sal_ids.ids) < 1000:
            domain = [('id', 'in', self.sudo().sal_ids.ids)]
        else:
            status = self.sudo().sal_ids[0].status
            domain = self.get_salaries_domain(with_status=False)
            domain.append(('status', '=', status))

        return {
            "name": '.',
            "type": "ir.actions.act_window",
            "res_model": "ab_hr_payroll_report",
            "views": [[False, "pivot"], [False, "list"], [False, "form"], ],
            "target": "current",
            "domain": domain,
        }

    ##############################################################################################################
    def copy(self, default=None):
        if not default:
            default = {}
        default['action_taken'] = False
        default['action_status'] = None
        default['explain'] = "%s %s" % (self.explain or '', " 👉")

        res = super(ActionWizard, self).copy(default=default)
        return res

    ##############################################################################################################
    def reset_criteria_button(self):
        self.ensure_one()
        self.date_begin = False
        self.date_end = False
        self.store_id = False
        self.store_id = False

    ##############################################################################################################
    def button_delete_salaries(self):
        self.ensure_one()
        if self.action_taken:
            return self.ab_msg(title="ERROR", message=ACTION_TAKEN_ERR)

        act_context = self.env.context.get('action')
        sal = len(self.sal_ids)
        message = _("""You will  
        <span class='h4 text-danger'>DELETE %s</span> record(s) ,
        <br/>
        are you sure?""") % sal

        return self.ab_msg(title="Confirm", message=message, mode='ok-cancel',
                           model_name=self._name, rec_id=self.id, fn_method='execute_deletion')

    @api.model
    def copy_record(self, rec_id, *args, **kwargs):
        record = self.browse(rec_id)
        res = record.copy()
        return res.button_action_salaries()
        # return {
        #     "name": '.',
        #     "type": "ir.actions.act_window",
        #     "views": [[False, "form"]],
        #     'res_id': res.id,
        #     "res_model": "ab_hr_action_wizard",
        #     "target": "current",
        #     "context": {'form_view_initial_mode': 'edit'},
        # }

    @api.model
    def execute_deletion(self, rec_id, *args, **kwargs):
        """ 
        Delete salaries records.
        Allowed for_entry group
        """
        i = 0
        record = self.browse(rec_id)
        sals = record.sal_ids
        for sal in self.web_progress_iter(sals, 'Action in progress..'):
            if sal.status == 'for_entry':
                i += 1
                # خلي ده آخر حاجة
                sal.unlink()

        self.env.cr.commit()
        if i > 0:
            # NO NEED TO SUDO() HERE

            record.action_taken = True

        message = _("""<span class='h4 text-success'>%s</span> 
        record(s) <span class='h4 text-danger'>DELETED</span> 
        by user <span class='h4 font-italic text-muted'>%s</span>""") % (i, self.env.user.name)
        record.message_post(body=str(message))
        return self.ab_msg(_('Done'), message=message)

    # OVERRIDE MESSAGE_POST TO SEND TELEGRAM MESSAGE
    def message_post(self, **kwargs):
        """Override method to send by telegram bot too"""
        message = super().message_post(**kwargs)
        msg = message.body

        before = """<b>Noted by:</b> %s\n<b>on action:</b> %s\n\n""" % (message.author_id.name, self.explain)

        self.send_by_bot(self.get_chat_id(CHAT_ID_KEY), msg=msg, before=before)
        return message

    def button_action_salaries(self):
        """Change status of salaries records
        Returns:
            ab_msg: Confirm action
        """
        self.ensure_one()
        if not self.create_uid.id == self._uid or self.action_taken:
            message = _(
                """YOU CAN NOT MODIFY THIS ACTION, DO YOU WANT TO COPY IT?""")
            return self.ab_msg(title="Confirm", message=message, mode='ok-cancel',
                               model_name=self._name, rec_id=self.id, fn_method='copy_record')

        act_context = self.env.context.get('action')
        sals = self.sal_ids.filtered(lambda r: r.status != act_context)
        if act_context == 'for_manager':
            employees = sals.mapped('employee_id')
            suspended_or_negative = self.env['ab_hr_payroll_report'].search([
                ('employee_id', 'in', employees.ids),
                ('status', 'in', ['negative_salaries', 'suspended_salaries']),
            ])

            codes = suspended_or_negative.mapped('employee_id.costcenter_id.code')
            final_codes = set(codes) - (set(self.exceptions.split(",")) if self.exceptions else set())
            if final_codes:
                final_codes_comma_sep = ','.join(final_codes)
                msg = _("There are negative or suspended employees in current actions\n"
                        "Please write their codes - COPY/PASTE - in Exception fields\n"
                        "Codes are: %s" % final_codes_comma_sep)
                raise ValidationError(msg)

        no_of_emps = self._count_employees(sals)

        message = _("""You will change 
        <span class='h4 text-danger'>%s</span> Employees to status 
        <span class='h4 text-danger'>%s</span>,
        <br/>
        are you sure?""") % (no_of_emps, act_context)

        return self.ab_msg(title="Confirm", message=message, mode='ok-cancel',
                           model_name=self._name, rec_id=self.id,
                           fn_method='_execute_action', action=act_context, no_of_emps=no_of_emps)

    # الدالة دي بيتم استدعائها من ab_msg
    # بيكون فيها نوع الاكشن مثلا (for_review,for_collect, ...)
    # وبيكون فيها رقم الريكورد بتاع الاكشن مثلا ab_hr_action_wizard(302,)

    @api.model
    def _execute_action(self, rec_id, action, no_of_emps=0, *args, **kwargs):
        record = self.browse(rec_id)
        sals = record.sal_ids.filtered(lambda r: r.status != action)

        # ASK USER TO SET PAYMENT TYPE
        if self.env.user.has_group('ab_hr.group_ab_hr_payroll_specialist'):
            if any(not sal.payment_type_id for sal in sals):
                raise UserError("Set 👉🏻👉🏻 Payment Type 👈🏻👈🏻, PLEASE 🌹")
        for sal in self.web_progress_iter(sals, 'Action in progress..'):
            if not sal.status == action:
                if sal.status == 'paid':
                    continue

                # خلي ده آخر حاجة
                sal.write({'status': action})

        if no_of_emps > 0:
            # NO NEED TO SUDO() HERE
            record.action_status = action
            record.action_taken = True

        message = _("""<span class='h4 text-success'>%s</span> employee%s <br> changed to status 
        <span class='h4 text-success'>%s</span> successfully 
        <br>
        by user <span class='h4 font-italic text-muted'>%s</span>""") % (
            no_of_emps, 's' if no_of_emps > 1 else '', action, self.env.user.name)
        record.message_post(body=str(message))
        return self.ab_msg(_('Done'), message=message, model_name=self._name, rec_id=record.id,
                           fn_method='_return_action_wizard_view')

    def _return_action_wizard_view(self, rec_id, *args, **kwargs):
        return {
            "name": '.',
            "type": "ir.actions.act_window",
            "views": [[False, "form"]],
            'res_id': rec_id,
            "res_model": "ab_hr_action_wizard",
            "target": "current",
            "context": {'form_view_initial_mode': 'edit'},
        }

    def btn_create_je(self):
        if self.env.user.has_group('ab_hr.group_ab_hr_manager'):
            self._create_je()
            no_of_emps = self._count_employees(self.sal_ids)
            message = _("""<span class='h4 text-success'>%s</span> employee%s <br> changed to status 
            <span class='h4 text-success'>%s</span> successfully 
            <br>
            by user <span class='h4 font-italic text-muted'>%s</span>""") % (
                no_of_emps, 's' if no_of_emps > 1 else '', 'Paid', self.env.user.name)
            self.message_post(body=str(message))

    def _create_je(self):
        costcenter_admin_id = self.env['ab_costcenter'].sudo().search([('code', '=', 1)]).id
        if not all(sal.status == 'for_manager' for sal in self.sal_ids):
            raise UserError(_("Salary lines must be 'for manager'"))
        str_sal_ids = ','.join(str(sal_id) for sal_id in self.sal_ids.ids)
        sql = """
        select 
            date_trunc('month', prl.due_date),
            prl.store_id,
            sum(prl.section_value), 
            section.debit_account_id 
        from ab_hr_payroll prl
        join ab_hr_section section on prl.section = section.id
        where prl.id in ({0})
        group by date_trunc('month', due_date), store_id, section.debit_account_id
        """.format(str_sal_ids)
        self.flush_model()
        self.env.cr.execute(sql, tuple(self.sal_ids.ids))
        salaries_list = self.env.cr.fetchall()
        salary_lines = [(0, 0,
                         {
                             "due_date": sal[0],
                             "store_id": sal[1] or 78,
                             "explain": 'Salaries HR',
                             "credit_val": sal[2] * -1 if sal[2] < 0 else 0,
                             "debit_val": sal[2] if sal[2] > 0 else 0,
                             "account_id": sal[3],
                             "costcenter_id": costcenter_admin_id,
                         }) for sal in salaries_list]

        sql = """
        select 
            date_trunc('month', prl.due_date),
            prl.store_id,
            hr.costcenter_id,
            sum(prl.section_value) , 
            section.credit_account_id
        from ab_hr_payroll prl
        join ab_hr_employee hr on prl.employee_id = hr.id
        join ab_hr_section section on prl.section = section.id
        where prl.id in ({0})
        group by date_trunc('month', prl.due_date), prl.store_id,hr.costcenter_id, section.credit_account_id
        """.format(str_sal_ids)
        self.flush_model()
        self.env.cr.execute(sql, tuple(self.sal_ids.ids))
        due_salaries_list = self.env.cr.fetchall()

        due_salaries_lines = [(0, 0,
                               {
                                   "due_date": sal[0],
                                   "store_id": sal[1] or 78,
                                   "costcenter_id": sal[2],
                                   "explain": 'Due Salaries',
                                   "debit_val": sal[3] * -1 if sal[3] < 0 else 0,
                                   "credit_val": sal[3] if sal[3] > 0 else 0,
                                   "account_id": sal[4],
                               }
                               ) for sal in due_salaries_list]

        account_header = self.env['ab_accounting_je_header'].sudo()
        account_header_id = account_header.create({"account_id": 365, "doctype_id": 7,
                                                   "line_ids": [*salary_lines, *due_salaries_lines]})
        account_header_id.btn_post_je()
        account_header_id.sudo_confirm_all_je()
        self.sal_ids.account_header_id = account_header_id.id

        self.sal_ids.status = 'paid'

    ##############################################################################################################

    def get_salaries_domain(self, with_status=True):  # pylint: disable=too-many-branches
        """Get domain from action wizard search criteria

        Args:
            with_status (bool, optional): If False that's mean this is a report or filter button. Defaults to True.

        Returns:
            _type_: _description_
        """        """"""
        domain = []
        if self.date_begin and self.date_end:
            domain.extend([
                ('due_date', '>=', self.date_begin.replace(day=1)),
                ('due_date', '<=', self.last_day_of_month(self.date_end))
            ])

        if self.payroll_month:
            domain.extend([
                ('due_date', '>=', self.payroll_month.replace(day=1)),
                ('due_date', '<=', self.last_day_of_month(self.payroll_month))
            ])

        if self.status and with_status:
            domain.extend([('status', '=', self.status)])

        if self.payment_type_id:
            domain.append(('payment_type_id', '=', self.payment_type_id.id))

        if self.user_line_owner:
            domain.append(('user_line_owner', '=', self.user_line_owner.id))

        if self.store_ids:
            domain.append(('store_id', 'in', self.store_ids.ids))

        if self.employee_id:
            domain.append(('employee_id', 'in', self.employee_id.ids))

        if self.job_id:
            domain.append(('job_id', 'in', self.job_id.ids))

        if self.workplace:
            domain.append(('workplace', 'in', self.workplace.ids))

        if self.section:
            domain.append(('section', 'in', self.section.ids))
        if self.pasted_salaries:
            if self.pasted_type == 'employee':
                employees = self.pasted_salaries.split('\n')
                try:
                    employees = [code.strip()
                                 for code in employees if not code == '']
                except Exception:
                    self.domain_ok = 0
                    domain.clear()
                else:
                    # if no errors and pasted_employees not empty
                    if employees:
                        domain.append(('employee_id.accid', 'in', employees))
            elif self.pasted_type == 'salary_id':
                salaries = self.pasted_salaries.split('\n')
                try:
                    salaries = [int(num.strip())
                                for num in salaries if not num == '']
                except Exception:
                    self.domain_ok = 0
                    domain.clear()
                else:
                    # if no errors and pasted_salaries not empty
                    if salaries:
                        domain.append(('id', 'in', salaries))

        return domain

    def _compute_salaries_html(self):
        for rec in self:
            data = self._get_salaries_html()
            data['NO_OF_ALLOWED_EMPLOYEES'] = False
            if len(data['rows']) > NO_OF_ALLOWED_EMPLOYEES:
                data['rows'] = data['rows'][0:NO_OF_ALLOWED_EMPLOYEES]
                data['NO_OF_ALLOWED_EMPLOYEES'] = NO_OF_ALLOWED_EMPLOYEES
            html = self.env['ir.qweb']._render('ab_hr_payroll.template_salaries_report', data)
            rec.salaries_html = html

    def btn_print_pdf_salaries_html(self):
        action = self.env.ref('ab_hr_payroll.action_pdf_salaries')
        data = self._get_salaries_html()
        return action.report_action(self, data=data)

    def btn_browse_salaries_compare_html(self):
        data = self._get_salaries_compare_html()
        data['NO_OF_ALLOWED_EMPLOYEES'] = False
        if len(data['rows']) > NO_OF_ALLOWED_EMPLOYEES:
            data['rows'] = data['rows'][0:NO_OF_ALLOWED_EMPLOYEES]
            data['NO_OF_ALLOWED_EMPLOYEES'] = NO_OF_ALLOWED_EMPLOYEES

        html = self.env['ir.qweb']._render('ab_hr_payroll.template_salaries_compare_report', data)
        self.salaries_compare_html = html

    def btn_browse_issues_salaries_compare_html(self):
        data = self._get_salaries_compare_html()
        data['rows'] = [row for row in data['rows'] if row[-1]]
        html = self.env['ir.qweb']._render('ab_hr_payroll.template_salaries_compare_report', data)

        self.salaries_compare_html = html

    def btn_print_pdf_salaries_compare_html(self):
        action = self.env.ref('ab_hr_payroll.action_pdf_salaries_compare')
        data = self._get_salaries_compare_html()
        return action.report_action(self, data=data)

    def _get_salaries_compare_html(self):
        self = self.sudo()
        employee_ids_text = ",".join(str(emp_id) for emp_id in set(self.sal_ids.sudo().mapped('employee_id.id'))) or "0"
        sql = """
            SELECT
                sd.employee_id,
                sum(sd.section_value) as salary_value,
                date_trunc('month', sd.due_date)::date as due_month    
            FROM ab_hr_payroll sd
            JOIN ab_hr_employee he on sd.employee_id = he.id
            JOIN ab_hr_section ahs on sd.section = ahs.id
                    WHERE ahs.type='hr'  
                    and date_trunc('month', sd.due_date) between %s and %s 
                    and sd.employee_id in ({})
            GROUP BY
                sd.employee_id,
                date_trunc('month', sd.due_date)
                    
            ORDER BY
                sd.employee_id,due_month
        """.format(employee_ids_text)

        cr = self.env.cr
        comparing_start_month = (self.comparing_start_month
                                 or datetime.date.today().replace(day=1) - relativedelta(months=4))
        comparing_end_month = (self.comparing_end_month
                               or datetime.date.today().replace(day=1))

        cr.execute(sql, (comparing_start_month, comparing_end_month))

        sals = cr.fetchall()
        mentioned_months = set(sal[-1] for sal in sals)
        due_months = sorted(list(mentioned_months))

        headers = ['Code', 'Name', 'Job', 'Workplace',
                   'Hiring Date',
                   'Issue Date',
                   'Termination Date',
                   *due_months,
                   'Warning']
        rows = []

        groups = itertools.groupby(sals, lambda x: x[0])
        for g_key, sub_iter in groups:
            salaries = {due_month: 0.001 for due_month in due_months}
            sub = list(sub_iter)
            employee = self.env['ab_hr_employee'].browse(sub[0][0])
            emp_code = employee.accid
            emp_name = employee.name
            if not employee.is_working:
                job_occupied = self.env['ab_hr_job_occupied'].search([
                    ('employee_id', '=', employee.id), ], order='termination_date desc', limit=1)
            else:
                job_occupied = self.env['ab_hr_job_occupied'].search(
                    [('employee_id', '=', employee.id), ('termination_date', '=', False)],
                    order='hiring_date desc',
                    limit=1)

            job_name = job_occupied.job_id.name
            workplace_name = job_occupied.workplace.name
            termination_date = job_occupied.termination_date
            issue_date = job_occupied.issue_date
            hiring_date = job_occupied.hiring_date

            for line in sub:
                salary = line[1]
                due_month = line[2]
                salaries[due_month] = salary
            salaries_list = list(salaries.values())
            ratio = salaries_list[-1] / salaries_list[-2]
            last_month = due_months[-1]
            salary_issue = ''

            if termination_date:
                if ratio > self.max_ratio:
                    salary_issue = 'HIGH SALARY ISSUE'
            elif ratio > self.max_ratio and hiring_date and (last_month - hiring_date) > datetime.timedelta(days=45):
                salary_issue = 'HIGH SALARY ISSUE'
            elif ratio < self.min_ratio:
                salary_issue = 'LOW SALARY ISSUE'

            rows.append(
                (emp_code, emp_name, job_name, workplace_name, hiring_date, issue_date, termination_date,
                 *salaries.values(),
                 salary_issue))

        return {
            'headers': headers,
            'rows': rows,
        }

    def btn_export_excel_salaries(self):
        action = self.env.ref('ab_hr_payroll.action_salaries_xlsx')
        action[0].name = "Salaries Report"

        return action.report_action(self)

    def btn_export_excel_salaries_compare(self):
        action = self.env.ref('ab_hr_payroll.action_salaries_compare_xlsx')
        action[0].name = "Salaries Compare Report"
        return action.report_action(self)

    ###########################################################################
    def _get_salaries_html(self):
        payroll_model = self.env['ab_hr_payroll'].sudo()
        selection = payroll_model.fields_get(allfields=['status'])[
            'status']['selection']
        sal_ids = self.sal_ids_text or '0'
        sql = """
            SELECT DISTINCT ON (sd.employee_id,sd.status)  
                sd.employee_id,
                sd.status,
                sd.job_id,
                sd.workplace,
                sum(sd.section_value) as salary_value,
                sd.user_line_owner,
                sd.payment_type_id
            FROM ab_hr_payroll sd
                    WHERE id in ({})
            GROUP BY
                sd.employee_id,
                sd.status,
                sd.job_id,
                sd.workplace,
                sd.user_line_owner,
                sd.payment_type_id
            ORDER BY
                sd.employee_id
        """.format(sal_ids)

        cr = self.env.cr
        cr.execute(sql)

        sals = cr.fetchall()
        headers = ['Code', 'Name', 'Job', 'Workplace', 'Status', 'Payment Method', 'Payment Type', 'Salary', ]
        rows = []
        i = 0
        for sal in sals:
            i += 1
            employee = self.env['ab_hr_employee'].browse(sal[0])
            emp_code = employee.accid
            emp_name = employee.name
            status = [v for (k, v) in selection if k == sal[1]][0]
            job = self.env['ab_hr_job'].browse(sal[2]).name
            workplace = self.env['ab_hr_department'].browse(sal[3]).name
            salary = sal[4]
            user_line_owner = self.env['res.users'].browse(
                sal[5]).name
            payment_type_id = self.env['ab_hr_payment_type'].browse(
                sal[6]).name
            rows.append((emp_code, emp_name, job, workplace, status, user_line_owner, payment_type_id, salary))

        return {
            'headers': headers,
            'rows': rows,
        }
