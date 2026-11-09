from odoo import fields, models


class AbCustodyEmployeeData(models.Model):
    _inherit = 'ab_custody_employee_data'

    is_custody = fields.Boolean(default=True)

    def btn_toggle_archive(self):
        self.active = not self.active
        return True
