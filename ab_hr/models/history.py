from odoo import fields, models, api
from odoo.tools.translate import _
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
                                  
                                  tracking=True,
                                  index=True)
    job_id = fields.Many2one('ab_hr_job_occupied', index=True)
    issue_date = fields.Date(related='job_id.issue_date')

    accid = fields.Char(related='employee_id.accid')
    action_date = fields.Date(required=True,
                              tracking=True, index=True)
    is_issue_as_action = fields.Boolean(compute='_compute_is_issue_as_action', compute_sudo=True,
                                        search='_search_is_issue_as_action')

    def _compute_is_issue_as_action(self):
        for rec in self:
            rec.is_issue_as_action = rec.action_date == rec.issue_date

    def _search_is_issue_as_action(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        history = self.env['ab_hr_emp_history'].search([('job_id.issue_date', '!=', False)]).sudo()
        ids = [rec.id for rec in history if rec.action_date == rec.job_id.issue_date]

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', ids)]

    action_type = fields.Many2one('ab_hr_history_action_type', required=True,

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

                                    tracking=True)

    old_job_title = fields.Many2one('ab_hr_job',
                                    string='Job Title',
                                    required=True, store=True,
                                    default=get_default_job,

                                    tracking=True)

    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')],
                                 tracking=True,
                                 required=True, string='Territory')
    new_workplace = fields.Many2one('ab_hr_department',

                                    tracking=True,
                                    string="New Workplace")
    workplace_region = fields.Many2one(related='old_workplace.workplace_region')
    parent_department_id = fields.Many2one(related='old_workplace.parent_id', string='Superior Department')

    new_job_title = fields.Many2one('ab_hr_job',
                                    tracking=True,
                                    string='New Job Title')
    new_territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')], tracking=True,
                                     string="New Territory")

    attached_file = fields.Binary()

    attached_link = fields.Char()

    payroll_action_month = fields.Char(store=True)

    is_applied = fields.Boolean(default=False, tracking=True)
    alt_job_id = fields.Many2one('ab_hr_emp_history', string='Alternative Job')
    history_diff = fields.Integer(compute='_compute_history_diff')
    start_fir_date = fields.Date(store=True, string='Start Firing Date')
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

    @api.depends('action_type.name', 'employee_id.name', 'old_job_title.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s/%s/%s' % (
                rec.action_type.name or '',
                rec.employee_id.name or '',
                rec.old_job_title.name or '',
            )

    @api.model
    def _search_display_name(self, operator, value):
        mod_name = get_modified_name(value)
        return [
            '|', '|',
            ('employee_id.name', operator, value),
            ('action_type.name', operator, mod_name),
            ('id', '=ilike', value),
        ]

    def btn_is_applied(self):
        if self.env.user.has_group("ab_hr.group_ab_hr_payroll_specialist"):
            self.sudo().is_applied = not self.is_applied

    def _recompute_job_issue_date(self, ids):
        model = self.env['ab_hr_job_occupied'].sudo()
        self.env.all.tocompute[model._fields['issue_date']].update(ids)
        model.recompute()

    @api.model
    def create(self, vals):
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
    #         "views": [[False, "tree"], [False, "pivot"]],
    #         "target": "current",
    #         "domain": domain,
    #     }
