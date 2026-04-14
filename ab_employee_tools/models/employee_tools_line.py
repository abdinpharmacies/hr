from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EmployeeToolsLine(models.Model):
    _name = "ab_employee_tools_employee_tools_line"
    _description = "Employee Tools Line"
    _order = "id"

    employee_tools_id = fields.Many2one(
        "ab_employee_tools_employee_tools",
        required=True,
        ondelete="cascade",
    )
    type_id = fields.Many2one(
        "ab_employee_tools.tools_type",
        string="Tool Type",
        required=True,
    )
    no_of_units = fields.Integer(string="No. of Units", required=True, default=1)
    size = fields.Selection(
        [
            ("small", "Small"),
            ("medium", "Medium"),
            ("large", "Large"),
            ("x_large", "X-Large"),
            ("xx_large", "XX-Large"),
            ("xxx_large", "XXX-Large"),
        ],
        string="Size",
    )
    price = fields.Float(related="type_id.price", string="Price", store=True)

    @api.depends("type_id", "no_of_units")
    def _compute_display_name(self):
        for rec in self:
            type_name = rec.type_id.name or ""
            qty = rec.no_of_units if rec.no_of_units is not None else ""
            rec.display_name = f"{type_name}: {qty}".strip(": ")

    def _check_edit_allowed(self, employee_tools):
        if employee_tools.termination_date or employee_tools.status == "delivered":
            raise ValidationError(
                _("Cannot modify tools lines for a terminated or delivered record.")
            )

    @api.constrains("no_of_units")
    def _check_no_of_units(self):
        for rec in self:
            if rec.no_of_units < 0:
                raise ValidationError(_("No. of Units must be zero or positive."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            employee_tools = self.env["ab_employee_tools_employee_tools"].browse(
                vals.get("employee_tools_id")
            )
            if employee_tools:
                self._check_edit_allowed(employee_tools)
        return super().create(vals_list)

    def write(self, vals):
        for rec in self:
            rec._check_edit_allowed(rec.employee_tools_id)
            super(EmployeeToolsLine, rec).write(vals)
        return True

    def unlink(self):
        for rec in self:
            rec._check_edit_allowed(rec.employee_tools_id)
        return super().unlink()
