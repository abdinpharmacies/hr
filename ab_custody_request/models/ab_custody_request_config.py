from odoo import api, fields, models, _


class AbCustodyRequestConfig(models.Model):
    _name = 'ab_custody_request_config'
    _description = 'ab_custody_request_config'

    date1 = fields.Datetime(required=True)
    date2 = fields.Datetime(required=True)
    employee_ids = fields.Many2many(
        comodel_name='ab_hr_employee',
        relation='ab_hr_employee_custody_request_rel',
        column1='config_id',
        column2='employee_id',
        string='Exceptional Employees')

    def name_get(self):
        res = []
        for rec in self:
            date1 = rec.date1.date() if rec.date1 else ''
            date2 = rec.date2.date() if rec.date2 else ''
            res.append((rec.id, f"[{date1}]:[{date2}]"))
        return res

    @api.depends('date1', 'date2')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)
