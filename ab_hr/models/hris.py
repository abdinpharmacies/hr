from odoo import fields, models, api
from odoo.exceptions import UserError
from .extra_functions import get_modified_name


class EmployeeDocStatus(models.Model):
    _name = 'ab_hr_emp_doc_status'
    _description = 'employee document status'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('ab_hr_employee', required=True, ondelete='cascade', index=True)
    accid = fields.Char(related='employee_id.accid')
    emp_doc_id = fields.Many2one('ab_hr_emp_doc', required=True, string='Document')

    status = fields.Selection(
        selection=[
            ('missing', 'Missing'),
            ('existing', 'Existing'),
            ('excluded', 'Excluded'),
            ('temp_excluded', 'Temporary Excluded')],
        default='missing', required=True)
    attachment = fields.Binary()
    exclusion_reason_id = fields.Many2one('ab_hr_exclusion_reason')

    received_date = fields.Date()
    expiry_date = fields.Date()

    def write(self, values):
        res = super().write(values)
        return res

    def action_save(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}

    def get_formview_action(self, access_uid=None):
        # view_id = self.sudo().get_formview_id(access_uid=access_uid)
        try:
            view_id = self.env.ref('ab_hr.ab_hr_emp_doc_status_view_form').id
        except ValueError:
            view_id = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'target': 'new',
            'res_id': self.id,
            'context': dict(self._context),
        }


class EmploymentDocuments(models.Model):
    _name = 'ab_hr_emp_doc'
    _description = 'ab_hr_employment_document'
    name = fields.Char(required=True)

    @api.model
    def _search_display_name(self, operator, value):
        mod_name = get_modified_name(value)
        return ['|', ('name', operator, value), ('name', operator, mod_name)]


class ExclusionReason(models.Model):
    _name = 'ab_hr_exclusion_reason'
    _description = 'ab_hr_exclusion_reason'
    name = fields.Char(required=True)

    @api.model
    def _search_display_name(self, operator, value):
        mod_name = get_modified_name(value)
        return ['|', ('name', operator, value), ('name', operator, mod_name)]


class InsuranceInfo(models.Model):
    _name = 'ab_hr_insurance_info'
    _description = 'ab_hr_insurance_info'

    employee_id = fields.Many2one('ab_hr_employee', required=True, index=True)
    accid = fields.Char(related='employee_id.accid')
    insurance_status = fields.Boolean(store=True, )
    insurance_type = fields.Selection(selection=[('abdin', 'Abdin Pharmacies'), ('other', 'Other')])
    insurance_branch = fields.Char()
    insurance_no = fields.Char()
    insurance_start = fields.Date()
    insurance_end = fields.Date()
    is_working = fields.Boolean(related='employee_id.is_working')
    internal_job = fields.Boolean(related='employee_id.internal_working_employee')
    subscription_val = fields.Float(default=0.0, digits=(10, 2))
    is_doc_complete = fields.Boolean(related='employee_id.is_docs_complete')
    graduate = fields.Char(related='employee_id.graduate')
    job_title_id = fields.Many2one(related='employee_id.job_id')
    job_ids = fields.One2many(related='employee_id.job_occupied_ids', string='Jobs')

    def action_save(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}

    def get_formview_action(self, access_uid=None):
        view_id = self.sudo().get_formview_id(access_uid=access_uid)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'target': 'new',
            'res_id': self.id,
            'context': dict(self._context),
        }


class PaperEffect(models.Model):
    _name = 'ab_hr_paper_effect'
    _description = 'PaperEffect'

    name = fields.Char(required=True, string="Notes")
    due_month = fields.Date()
    attached_link = fields.Char()
    attached_file = fields.Binary()
    is_applied = fields.Boolean()
    active = fields.Boolean(default=True)

    #############################################################
    # WRITE #####
    def write(self, values):
        res = super().write(values)
        for rec in self:
            if values and not self.env.user.has_group('ab_hr.group_ab_hr_payroll_specialist') and rec.is_applied:
                raise UserError("COORDINATOR: YOU ARE NOT ALLOWED TO EDIT MOVEMENT AS IT IS APPLIED")

            if (values
                    and any(k in ['is_applied'] for k in values.keys())
                    and not self.env.user.has_group('ab_hr.group_ab_hr_payroll_specialist')):
                raise UserError("COORDINATOR: YOU ARE NOT ALLOWED TO EDIT MOVEMENT")

        return res
