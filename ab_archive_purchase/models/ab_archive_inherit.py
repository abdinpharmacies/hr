from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class AbArchive(models.Model):
    _name = 'ab_archive'
    _inherit = 'ab_archive'

    notice_ids = fields.Many2many(
        comodel_name='ab_purchase_notice_header',
        relation='ab_archive_ab_purchase_notice_header_rel',
        column1='archive_id',
        column2='notice_id',
        string='Notices')

    department_id = fields.Many2one('ab_hr_department', index=True,
                                    compute='_compute_department_id',
                                    compute_sudo=True,
                                    store=True,
                                    readonly=True)
    notice_line_ids = fields.Many2many(
        comodel_name='ab_purchase_notice_line',
        compute='_compute_notice_line_ids',
        compute_sudo=True,
        string='Lines')

    @api.depends('notice_ids')
    def _compute_notice_line_ids(self):
        for rec in self:
            rec.notice_line_ids = self.notice_ids.mapped('line_ids')

    @api.constrains('user_id')
    def _constraint_ab_archive(self):
        self = self.sudo()
        for rec in self:
            if not rec.user_id.ab_employee_ids:
                raise ValidationError(_("User must linked to employee"))

    @api.depends('user_id')
    def _compute_department_id(self):
        for rec in self:
            linked_employees = rec.user_id.ab_employee_ids
            if linked_employees:
                rec.department_id = linked_employees[0].department_id.id
            else:
                rec.department_id = False

    def btn_toggle_active(self):
        if not self.env.user.has_group('ab_purchase.group_ab_purchase_data_entry'):
            raise UserError(_("You are not authorized to Archive/Restore!"))
        return super().btn_toggle_active()
