# -*- coding: utf-8 -*-
import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
from dateutil.relativedelta import relativedelta


class AbCustodyReconciliationLines(models.Model):
    _name = 'ab_custody_reconciliation_line'
    _description = 'ab_custody_reconciliation_line'
    _order = 'id DESC'

    header_id = fields.Many2one('ab_custody_reconciliation_header', required=True, ondelete='restrict')
    invoice_code = fields.Char()
    description = fields.Text(required=True)
    value = fields.Float(required=True, default=0)
    custody_account_id = fields.Many2one('ab_custody_request_account', required=True, domain=[('is_recon', '=', True)])
    attachment = fields.Binary(string="Attachment", attachment=True)
    concerned_employee_ids = fields.Many2many('ab_hr_employee',
                                              compute_sudo=True,
                                              compute='_compute_concerned_employee_ids',
                                              string='Concerned Employees')

    can_approve = fields.Boolean(compute_sudo=True,
                                 compute='_compute_can_approve',
                                 search='_search_can_approve')

    claimer_department_id = fields.Many2one(related='header_id.department_id', string='Claimer Department')
    status = fields.Selection([('entry', 'Entry'),
                               ('pending', 'Pending'),
                               ('approved', 'Approved'),
                               ('rejected', 'Rejected'),
                               ('neglected', 'Neglected')], default='entry', readonly=True)
    rejection_reason = fields.Html(readonly=True)
    active = fields.Boolean(default=True)
    notes = fields.Text(readonly=True)
    follow_up_ids = fields.Many2many(
        comodel_name='res.users',
        relation='ab_custody_reconciliation_line_users_rel',
        column1='recon_line_id',
        column2='user_id',
        string='Followers')

    def write(self, values):
        if self.env.context.get('skip_follow_up'):
            return super().write(values)
        current_user = self.env.user
        for rec in self:
            if current_user not in rec.follow_up_ids:
                rec.with_context(skip_follow_up=True).follow_up_ids = [(4, current_user.id)]
        return super().write(values)

    @api.constrains('value')
    def _constrains_ab_custody_reconciliation_line(self):
        for rec in self:
            if not rec.value > 0:
                raise ValidationError(_("Value must be greater than zero!"))

    def _compute_can_approve(self):
        for rec in self:
            if self.env.user.id in rec.concerned_employee_ids.mapped('user_id.id'):
                rec.can_approve = True
            else:
                rec.can_approve = False

    def _search_can_approve(self, operator, val):
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

        ids = []

        if operator != '=':  # that means it is '!='
            val = not val
        self = self.sudo()
        current_date = datetime.now()
        three_months_ago = current_date - relativedelta(months=3)

        for rec in self.search([('create_date', '>', three_months_ago)]):
            if rec.can_approve:
                ids.append(rec.id)

        return [('id', 'in' if val else 'not in', ids)]

    @api.depends('custody_account_id')
    def _compute_concerned_employee_ids(self):
        for rec in self:
            employees = self.env['ab_hr_employee']
            line = self.env['ab_reconciliation_employee_approval'].search(
                [
                    ('account_id', '=', rec.custody_account_id.id),
                    '|',
                    ('store_ids', 'in', rec.header_id.department_id.store_id.id),
                    ('store_ids', '=', False),
                ])

            all_employees = self.env['ab_hr_employee'].search([
                ('id', 'parent_of', line.employee_id.ids),
                ('user_id', '!=', False),
            ])

            for employee in all_employees:
                if employee.user_id.has_group('ab_custody_request.group_ab_custody_request_user'):
                    employees |= employee
            department_manager = rec.custody_account_id.department_id.manager_id
            if department_manager:
                employees |= department_manager
            elif not rec.custody_account_id.department_id:
                employees |= rec.header_id.manager_id

            rec.concerned_employee_ids = employees

    def btn_approve(self):
        if self.status == 'approved':
            raise ValidationError(_("Record already approved"))

        if self.status != 'pending':
            raise ValidationError(_("You can approve pending records only!"))

        if self.can_approve:
            self = self.sudo()
            self.status = 'approved'
            user_name = self.env.user.name
            approval_note = f"approved by: {user_name}"
            notes_list = []
            if self.notes:
                notes_list.append(self.notes)
            notes_list.append(approval_note)
            self.notes = '\n----------\n'.join(notes_list)
            self.header_id.sudo().message_post(body="<div class='text-success h5'>Approved</div>")
        else:
            raise ValidationError(_("You are not allowed to approve!"))

    def btn_reject(self):
        is_accounting = self.env.user.has_group('ab_custody_reconciliation.group_ab_custody_reconciliation_accounting')
        if self.header_id.je_header_id:
            raise ValidationError(_("Custody Linked to JE Header ID: %s") % self.header_id.je_header_id.id)
        if self.status == 'rejected':
            raise ValidationError(_("Record already rejected"))
        if not (
                (self.status == 'pending' and self.can_approve)
                or (self.status == 'approved' and is_accounting)
        ):
            raise ValidationError(_("Rejection is not allowed"))

        return {
            "type": "ir.actions.act_window",
            "res_model": "ab_custody_reconciliation_wizard",
            "views": [[False, "form"]],
            "target": "new",
            "context": {'default_recon_id': self.id},
        }

    def btn_add_notes(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "ab_custody_reconciliation_wizard",
            "views": [[False, "form"]],
            "target": "new",
            "context": {'default_recon_id': self.id, 'type': 'notes'},
        }

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f"{rec.custody_account_id.name} ({rec.value})"))
        return res

    @api.depends('custody_account_id', 'value')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)

    @api.model
    def get_status_selection(self):
        status_selections = self.fields_get(allfields=['status'])['status']['selection']
        return dict(status_selections)

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        for values in vals_list:
            records |= self._create_one_ab_custody_reconciliation_abcustodyreconciliationlines(values)
        return records

    def _create_one_ab_custody_reconciliation_abcustodyreconciliationlines(self, values):
        res = super().create(values)
        if res.header_id.recon_status != 'entry':
            raise ValidationError(_("Record is not in entry state"))
        return res
