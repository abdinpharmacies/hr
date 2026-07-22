from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.translate import _


class AbRequestCategory(models.Model):
    _name = 'ab_request_category'
    _description = "Request/Complaint Category"

    name = fields.Char(string="Name", translate=True)
    type = fields.Selection(
        [
            ("complaint", "Complaint"),
            ("other", "Other"),
        ],
        default="other",
        string="Type",
        required=True,
    )
    is_public = fields.Boolean(
        string="Available on Public Form",
        default=False,
        help="The category is listed publicly only when this is enabled and it has at least one public request type.",
    )
    request_type_ids = fields.One2many(
        "ab_request_type",
        "category_id",
        string="Request/Complaint Types",
    )
    public_request_type_count = fields.Integer(
        string="Public Request Types",
        compute="_compute_public_form_status",
    )
    is_public_form_ready = fields.Boolean(
        string="Visible on Public Form",
        compute="_compute_public_form_status",
    )

    @api.depends("is_public", "request_type_ids.is_public")
    def _compute_public_form_status(self):
        for record in self:
            public_type_count = len(record.request_type_ids.filtered("is_public"))
            record.public_request_type_count = public_type_count
            record.is_public_form_ready = bool(record.is_public and public_type_count)

    @api.constrains("is_public", "name")
    def _check_public_configuration(self):
        for record in self:
            if record.is_public and not (record.name or "").strip():
                raise ValidationError(_("A public request category must have a name."))
            if not record.is_public and record.request_type_ids.filtered("is_public"):
                raise ValidationError(_("Disable public availability on the category's request types first."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_public_visibility_access(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_public_visibility_access(vals)
        return super().write(vals)

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
