from odoo import fields, models


class ToolsType(models.Model):
    _name = "ab_employee_tools.tools_type"
    _description = "Tools Type"
    _order = "name"

    name = fields.Char(required=True)
    price = fields.Float()
    qty_available = fields.Integer(string="Available Units", default=0)
