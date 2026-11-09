# -*- coding: utf-8 -*-
import datetime

from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
from .extra_functions import get_modified_name


class SalariesDue(models.Model):
    _name = 'ab_hr_payroll'
    _description = 'Payroll'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'abdin_et.extra_tools']
    _rec_name = 'employee_id'
    _order = 'id desc'

    costcenter_id = fields.Many2one('ab_costcenter')
    employee_id = fields.Many2one("ab_hr_employee", string="Employee",
                                  compute='_compute_employee_id',
                                  store=True,
                                  index=True,
                                  readonly=lambda self: not self.user.has_group(
                                      'ab_hr.group_ab_hr_payroll_specialist'))
    accid = fields.Char(related="employee_id.accid", string="Code")
    job_id = fields.Many2one('ab_hr_job', index=True,
                             readonly=lambda self: not self.user.has_group(
                                 'ab_hr.group_ab_hr_payroll_specialist'))

    user_line_owner = fields.Many2one('res.users', string="Payment Method",
                                      domain=lambda self: [('account_auth_ids', '!=', False)], )

    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')],
                                 readonly=lambda self: not self.user.has_group(
                                     'ab_hr.group_ab_hr_payroll_specialist'))
    workplace = fields.Many2one('ab_hr_department', index=True,
                                readonly=lambda self: not self.user.has_group(
                                    'ab_hr.group_ab_hr_payroll_specialist'))

    hr_name_entry = fields.Char(string="HR Name",
                                readonly=lambda self: not self.user.has_group(
                                    'ab_hr.group_ab_hr_payroll_specialist'))

    store_id = fields.Many2one("ab_store", index=True, required=True, readonly=lambda self: not self.user.has_group(
        'ab_hr.group_ab_hr_payroll_specialist'))

    due_date = fields.Date(required=True, index=True,
                           readonly=lambda self: not self.user.has_group(
                               'ab_hr.group_ab_hr_payroll_specialist'))

    section = fields.Many2one("ab_hr_section", required=True, index=True,
                              readonly=lambda self: not self.user.has_group(
                                  'ab_hr.group_ab_hr_payroll_specialist'))

    section_type = fields.Selection(related="section.type", store=True, readonly=True, index=True)
    section_value = fields.Float(required=True, index=True,
                                 readonly=lambda self: not self.user.has_group(
                                     'ab_hr.group_ab_hr_payroll_specialist'))

    file_name = fields.Char(readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_payroll_specialist'))

    sheet_name = fields.Char(readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_payroll_specialist'))
    net_salary = fields.Float(readonly=lambda self: not self.user.has_group('ab_hr.group_ab_hr_payroll_specialist'))
    do_action = fields.Boolean(default=True)
    status = fields.Selection(string='Status',
                              selection=[
                                  ('for_entry', 'For Entry'),
                                  ('for_reviewer', 'For Reviewer'),
                                  ('for_manager', 'For Manager'),
                                  ('suspended_salaries', 'Suspended Salaries'),
                                  ('negative_salaries', 'Negative Salaries'),
                                  ('paid', 'Paid'),
                              ], default='for_entry', index=True, readonly=True)
    payment_type_id = fields.Many2one('ab_hr_payment_type')
    account_header_id = fields.Many2one('ab_accounting_je_header', readonly=True)

    user_id = fields.Many2one('res.users', readonly=True,
                              default=lambda self: self.env.user.id if self.env.user.id != 1 else False)

    @api.depends('costcenter_id')
    def _compute_employee_id(self):
        for rec in self:
            if rec.costcenter_id:
                rec.employee_id = self.env['ab_hr_employee'].search([('costcenter_id', '=', rec.costcenter_id.id)],
                                                                    limit=1).id

    @api.constrains('store_id')
    def _constraint_payroll_entry(self):
        for rec in self:
            if not rec.store_id:
                raise ValidationError(_("You Must Set Branch"))

    def write(self, values):
        res = super().write(values)
        allowed_fields = {'status', 'account_header_id'}
        for rec in self:
            if set(values) - allowed_fields and rec.status != 'for_entry':
                raise ValidationError(_("You can not edit these records."
                                        "\nPlease send them to 'For Entry' Stage first."))

        return res


######################################################################################################################
class PaymentType(models.Model):
    _name = 'ab_hr_payment_type'
    _description = 'PaymentType'

    name = fields.Char(translate=True)

    _ab_hr_payment_type_unique = models.Constraint('unique(name)', 'Payment Type CAN NOT BE DUPLICATED!')

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        mod_name = get_modified_name(name)
        args += ['|',
                 ('name', operator, name),
                 ('name', operator, mod_name),
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


######################################################################################################################

class Section(models.Model):
    _name = "ab_hr_section"
    _description = "ab_hr_section"

    name = fields.Char()
    type = fields.Selection(selection=[('hr', 'HR'), ('accounts', 'Accounting')], required=True)
    credit_account_id = fields.Many2one('ab_accounting_account_guide',
                                        default=267)  # اجور عاملين مستحقة
    debit_account_id = fields.Many2one('ab_accounting_account_guide',
                                       default=365)  # المرتبات
    active = fields.Boolean(default=True)

    _ab_hr_section_name_unique = models.Constraint('unique(name)', 'Section Name CAN NOT BE DUPLICATED!')

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        mod_name = get_modified_name(name)
        args += ['|',
                 ('name', operator, name),
                 ('name', operator, mod_name),
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
