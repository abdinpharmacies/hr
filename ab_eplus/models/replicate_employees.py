# -*- coding: utf-8 -*-

from odoo import api, fields, models

PARAM_STR = "%s"


class ReplicateEmployee(models.TransientModel):
    _name = 'ab_eplus.replicate_employees'
    _description = 'ab_eplus.replicate_employees'
    _inherit = 'ab_eplus_connect'

    def generate_employees(self, replicate_all=False):
        with self.connect_eplus(param_str=PARAM_STR, charset='CP1256') as cnx:
            employees = self._get_employees_data(cnx, replicate_all)
            self._update_ab_costcenter(employees)

    def _get_employees_data(self, cnx, replicate_all):
        if replicate_all:
            last_employee_bc_id = 0
        else:
            last_employee_bc_id = self.env['ab_costcenter'].sudo().search([('bc_id', '>', 0)], order='bc_id desc',
                                                                          limit=1).bc_id or 0
        cr = cnx.cursor()
        cr.execute("""
                   SELECT e_id, e_code, e_name
                   FROM employee
                   where e_id > %s
                   """, (last_employee_bc_id,))

        return cr.fetchall()

    def _update_ab_costcenter(self, employees):
        costcenter = self.env['ab_costcenter'].sudo()
        for emp in employees:
            employee_dict = dict(
                bc_id=emp[0],
                eplus_serial=emp[0],
                code=emp[1].replace('*', ''),
                name=emp[2]
            )

            employee = costcenter.with_context(active_test=False).search([('code', '=', employee_dict['code'])])
            if employee:
                values = {field: value for field, value in employee_dict.items() if getattr(employee, field) != value}
                if values:
                    employee.write(values)
            else:
                costcenter.create(employee_dict)
