from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.translate import _


class AbRequestType(models.Model):
    _name = "ab_request_type"
    _table = "ab_request_type"
    _description = "Request/Complaint Type"
    _order = "name"

    name = fields.Char(required=True, translate=True)
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

    category_id = fields.Many2one('ab_request_category')
    is_public = fields.Boolean(
        string="Available on Public Form",
        default=False,
        help="The type is listed publicly only when this and its owning category are both enabled.",
    )
    category_type = fields.Selection(
        related="category_id.type",
        string="Category Type",
        readonly=True,
    )
    question_ids = fields.One2many(
        "ab_request_type_question",
        "request_type_id",
        string="Questions",
    )

    _ab_request_type_name_department_uniq = models.Constraint(
        "UNIQUE(name, department_id)",
        "Request/complaint type must be unique per department.",
    )

    @api.constrains("department_id")
    def _check_department_manager(self):
        """Ensure every request type belongs to a managed department."""
        for record in self:
            if not record.department_id.manager_id:
                raise ValidationError(("The selected department must have a manager."))

    @api.constrains("is_public", "category_id")
    def _check_public_category(self):
        """Only expose types whose owning category is also explicitly public."""
        for record in self:
            if record.is_public and not record.category_id:
                raise ValidationError(_("A public request type must belong to a category."))
            if record.is_public and not record.category_id.is_public:
                raise ValidationError(_("A public request type must belong to a public category."))

    @api.model_create_multi
    def create(self, vals_list):
        """Trim names before creating request types."""
        for vals in vals_list:
            self._check_public_visibility_access(vals)
        return super().create([self._prepare_vals(vals) for vals in vals_list])

    def write(self, vals):
        """Trim names before updating request types."""
        self._check_public_visibility_access(vals)
        return super().write(self._prepare_vals(vals))

    def _check_public_visibility_access(self, vals):
        can_configure_public_form = self.env.user.has_group(
            "ab_request_management.group_ab_request_management_admin"
        ) or self.env.user.has_group(
            "ab_request_management.group_ab_request_management_viewer"
        )
        if "is_public" in vals and not can_configure_public_form:
            raise AccessError(
                _("Only request administrators or visibility users can change public form availability.")
            )

    @api.model
    def _prepare_vals(self, vals):
        """Normalize request type values."""
        prepared_vals = dict(vals or {})
        if prepared_vals.get("name"):
            prepared_vals["name"] = prepared_vals["name"].strip()
        return prepared_vals
