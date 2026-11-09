# -*- coding: utf-8 -*-
import datetime

from odoo import models, fields, api, SUPERUSER_ID, _, tools
from odoo.exceptions import UserError
from .extra_functions import get_modified_name


class SalariesReport(models.Model):
    _name = 'ab_hr_payroll_report'
    _description = 'Payroll Report'
    _rec_name = 'employee_id'
    _auto = False

    employee_id = fields.Many2one('ab_hr_employee')
    job_id = fields.Many2one('ab_hr_job')
    user_line_owner = fields.Many2one('res.users')
    payment_type_id = fields.Many2one('ab_hr_payment_type')

    territory = fields.Selection(
        selection=lambda self: self._get_selection_form_model('ab_hr_payroll', 'territory'), )
    workplace = fields.Many2one('ab_hr_department')

    hr_name_entry = fields.Char(string="HR Name")

    store_id = fields.Many2one("ab_store")

    due_date = fields.Date()

    section = fields.Many2one("ab_hr_section")

    section_type = fields.Selection(
        selection=lambda self: self._get_selection_form_model('ab_hr_section', 'type'), )
    section_value = fields.Float()

    file_name = fields.Char()

    sheet_name = fields.Char()
    net_salary = fields.Float()
    status = fields.Selection(string='Status',
                              selection=lambda self: self._get_selection_form_model('ab_hr_payroll', 'status'), )

    e_code = fields.Char()
    costcenter_name = fields.Char()
    create_date = fields.Datetime()
    write_date = fields.Datetime()

    @api.model
    def _get_selection_form_model(self, model, fld):
        """ model: model name,
            fld: selection field
         """
        payroll_model = self.env[model]
        selection = payroll_model.fields_get(allfields=[fld])[fld]['selection']
        return selection

    def _compute_status(self):
        for rec in self:
            rec.status = self.env['ab_hr_payroll'].sudo().browse(rec.id).status

    def _search_status(self, operator, val):
        ids = self.env['ab_hr_payroll'].sudo().search([('status', operator, val)]).ids

        return [('id', 'in', ids)]

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
        delete from ir_model_fields_selection 
            where field_id in (select id from ir_model_fields
                                    where model=%s and ttype='selection') ;""", (self._name,))

        self.env.cr.execute("""
            CREATE OR REPLACE VIEW {table_name}
             AS
             SELECT
             DISTINCT ON (sd.id)
             sd.*,
             cc.code as e_code,
             CONCAT(cc.code,'::',e.name,'::',job.name) as costcenter_name
            FROM ab_hr_payroll sd
            left join ab_hr_employee e on e.id=sd.employee_id
            left join ab_hr_section s ON s.id = sd.section
            left join ab_costcenter cc on cc.id=e.costcenter_id
            left join ab_hr_job job on job.id=sd.job_id
            order by sd.id
        """.format(table_name=self._table))


##############################################################
# #################### Remove PayrollEmployee ############## #
##############################################################

class SalariesEmployee(models.Model):
    _name = 'ab_hr_payroll_employee'
    _description = 'Salaries Before Payment Report'
    _auto = False

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
        CREATE OR REPLACE VIEW {table_name}
         AS
         SELECT sd.*
         FROM ab_hr_payroll sd""".format(table_name=self._table))
