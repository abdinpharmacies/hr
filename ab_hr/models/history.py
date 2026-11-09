from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
import datetime
from .extra_functions import get_modified_name


class EmployeeHistory(models.Model):
    _name = 'ab_hr_emp_history'
    _description = 'History'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'abdin_et.extra_tools']
    _rec_name = 'employee_id'
    _order = 'action_date desc'

    employee_id = fields.Many2one('ab_hr_employee',
                                  readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_co'),
                                  tracking=True,
                                  index=True)
    job_id = fields.Many2one('ab_hr_job_occupied', index=True)
    issue_date = fields.Date(related='job_id.issue_date')

    accid = fields.Char(related='employee_id.accid')
    action_date = fields.Date(required=True, readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_co'),
                              tracking=True, index=True)
    is_issue_as_action = fields.Boolean(compute='_compute_is_issue_as_action', compute_sudo=True,
                                        search='_search_is_issue_as_action')

    def _compute_is_issue_as_action(self):
        for rec in self:
            rec.is_issue_as_action = rec.action_date == rec.issue_date

    def _search_is_issue_as_action(self, operator, val):
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

        history = self.env['ab_hr_emp_history'].search([('job_id.issue_date', '!=', False)]).sudo()
        ids = [rec.id for rec in history if rec.action_date == rec.job_id.issue_date]

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', ids)]

    action_type = fields.Many2one('ab_hr_history_action_type', required=True,
                                  readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_co'),
                                  tracking=True,
                                  index=True)

    notes = fields.Text(tracking=True)

    def get_default_workplace(self):
        return self.employee_id.department_id.id

    def get_default_job(self):
        return self.employee_id.job_id.id

    old_workplace = fields.Many2one('ab_hr_department',
                                    string='Workplace',
                                    required=True, store=True,
                                    default=get_default_workplace,
                                    readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_co'),
                                    tracking=True)

    old_job_title = fields.Many2one('ab_hr_job',
                                    string='Job Title',
                                    required=True, store=True,
                                    default=get_default_job,
                                    readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_co'),
                                    tracking=True)

    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')],
                                 tracking=True,
                                 required=True, string='Territory')
    new_workplace = fields.Many2one('ab_hr_department',
                                    readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_co'),
                                    tracking=True,
                                    string="New Workplace")
    workplace_region = fields.Many2one(related='old_workplace.workplace_region')
    parent_department_id = fields.Many2one(related='old_workplace.parent_id', string='Superior Department')

    new_job_title = fields.Many2one('ab_hr_job', readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_co'),
                                    tracking=True,
                                    string='New Job Title')
    new_territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')], tracking=True,
                                     string="New Territory")

    attached_file = fields.Binary(readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_co'))

    attached_link = fields.Char(readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_co'))

    payroll_action_month = fields.Char(compute="_compute_payroll_action_month", store=True)

    is_applied = fields.Boolean(default=False,
                                readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_payroll_specialist'),
                                tracking=True)
    alt_job_id = fields.Many2one('ab_hr_emp_history', string='Alternative Job')
    history_diff = fields.Integer(compute='_compute_history_diff')
    start_fir_date = fields.Date(compute='_compute_start_fir_date', store=True, string='Start Firing Date')
    replacement_date = fields.Date(related='alt_job_id.action_date', string="Replacement Date")
    termination_date = fields.Date(related='job_id.termination_date', string="Termination Date")
    active = fields.Boolean(default=True)

    def btn_archive(self):
        self.ensure_one()
        if not self.active:
            raise ValidationError(_("Record is already archived."))
        if self.env.user.has_group('ab_hr.group_ab_hr_co'):
            self.sudo().active = False
        else:
            raise ValidationError(_("You must have coordinator authority to archive"))

    def _compute_history_diff(self):
        for rec in self:
            if rec.start_fir_date:
                diff = datetime.date.today() - rec.start_fir_date
                rec.history_diff = diff.days
            else:
                rec.history_diff = 0

    @api.depends('action_date', 'action_type.action_date_type', 'alt_job_id.action_date')
    def _compute_start_fir_date(self):
        for rec in self:
            default_firing_date = rec.action_date + datetime.timedelta(days=30)
            if rec.alt_job_id and rec.alt_job_id.action_date <= default_firing_date:
                rec.start_fir_date = rec.alt_job_id.action_date
            elif rec.action_type.action_date_type == 'pending_issue':
                rec.start_fir_date = default_firing_date
            elif rec.action_type.action_date_type == 'direct_issue':
                rec.start_fir_date = rec.action_date
            else:
                rec.start_fir_date = None

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, '%s/%s/%s' % (
                rec.action_type.name, rec.employee_id.name, rec.old_job_title.name)))
        return res

    @api.depends('action_type', 'employee_id', 'old_job_title')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        mod_name = get_modified_name(name)
        args += ['|', '|',
                 ('employee_id.name', operator, name),
                 ('action_type.name', operator, mod_name),
                 ('id', '=ilike', name),
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

    def btn_is_applied(self):
        if self.env.user.has_group("ab_hr.group_ab_hr_payroll_specialist"):
            self.sudo().is_applied = not self.is_applied

    @api.depends('action_type', 'action_type.is_overlapped', 'action_date')
    def _compute_payroll_action_month(self):
        for rec in self:
            if rec.action_date:
                month1 = rec.action_date.month
                action_year1 = rec.action_date.year
                if rec.action_date.month < 12:
                    month2 = rec.action_date.month + 1
                    action_year2 = rec.action_date.year
                else:
                    month2 = 1
                    action_year2 = rec.action_date.year + 1

                # action_year2 =
                if 20 < rec.action_date.day <= self.last_day_of_month(rec.action_date).day:
                    if rec.action_type.is_overlapped:
                        rec.payroll_action_month = "{month1}/{action_year1} & {month2}/{action_year2}".format(
                            month1=month1,
                            action_year1=action_year1,
                            month2=month2,
                            action_year2=action_year2,
                        )
                    else:
                        rec.payroll_action_month = "{month1}/{action_year}".format(month1=month2,
                                                                                   action_year=action_year2, )
                else:
                    rec.payroll_action_month = "{month1}/{action_year}".format(month1=month1,
                                                                               action_year=action_year1, )

    def _recompute_job_issue_date(self, ids):
        model = self.env['ab_hr_job_occupied'].sudo()
        self.env.add_to_compute(model._fields['issue_date'], model.browse([record_id for record_id in ids if record_id]))
        model._recompute_recordset()

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_hr_employeehistory(values)
        return records

    def _create_one_ab_hr_employeehistory(self, vals):
        res = super().create(vals)
        self._recompute_job_issue_date([res.job_id.id])
        return res

    def write(self, vals):
        if 'active' in vals and not vals['active']:
            for rec in self:
                if rec.action_type.action_date_type == 'firing':
                    pass

        self._recompute_job_issue_date([self.job_id.id, vals.get('job_id', 0)])
        res = super().write(vals)
        return res

    # def action_firing_cycle(self):
    #     domain = ['&', '&',
    #               ('job_id.issue_date', '!=', False),
    #               ('job_id.termination_date', '=', False),
    #               '|', '|',
    #               ('history_diff', '>', 30),
    #               ('action_type.action_date_type', '=', 'direct_issue'),
    #               ('alt_job_id', '!=', False),
    #               ]
    #     return {
    #         "name": '.',
    #         "type": "ir.actions.act_window",
    #         "res_model": "ab_hr_emp_history",
    #         "views": [[False, "list"], [False, "pivot"]],
    #         "target": "current",
    #         "domain": domain,
    #     }
