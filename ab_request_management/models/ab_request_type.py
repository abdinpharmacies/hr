from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AbRequestType(models.Model):
    _name = "ab.request.type"
    _table = "ab_request_type"
    _description = "Request Type"
    _order = "name"

    name = fields.Char(required=True)
    department_id = fields.Many2one(
        "ab_hr_department",
        required=True,
        ondelete="restrict",
    )
    manager_id = fields.Many2one(
        "ab_hr_employee",
        related="department_id.manager_id",
        store=True,
        readonly=True,
    )

    _ab_request_type_name_department_uniq = models.Constraint(
        "UNIQUE(name, department_id)",
        "Request type must be unique per department.",
    )

    @api.constrains("department_id")
    def _check_department_manager(self):
        """Ensure every request type belongs to a managed department."""
        for record in self:
            if not record.department_id.manager_id:
                raise ValidationError(_("The selected department must have a manager."))

    @api.model_create_multi
    def create(self, vals_list):
        """Trim names before creating request types."""
        return super().create([self._prepare_vals(vals) for vals in vals_list])

    def write(self, vals):
        """Trim names before updating request types."""
        return super().write(self._prepare_vals(vals))

    @api.model
    def _prepare_vals(self, vals):
        """Normalize request type values."""
        prepared_vals = dict(vals or {})
        if prepared_vals.get("name"):
            prepared_vals["name"] = prepared_vals["name"].strip()
        return prepared_vals
