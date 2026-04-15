from odoo import api, fields, models
from odoo.exceptions import ValidationError


TECHNICAL_PREFIXES = ("ir.", "mail.", "bus.", "base.", "web.", "auth.")


class AbSecurityFieldAccess(models.Model):
    _name = "ab_security_field_access"
    _description = "Smart Security Field Access"
    _order = "role_id, field_id"

    _role_field_unique = models.Constraint(
        "unique(role_id, field_id)",
        "A role can only have one managed field access line per field.",
    )

    role_id = fields.Many2one(
        "ab_security_role",
        required=True,
        ondelete="cascade",
    )
    field_id = fields.Many2one(
        "ir.model.fields",
        required=True,
        domain="[('store', 'in', [True, False])]",
        ondelete="cascade",
    )
    can_view = fields.Boolean(default=True)
    can_edit = fields.Boolean(default=False)
    field_name = fields.Char(string="Field Name", related="field_id.name", store=True)
    field_label = fields.Char(string="Field Label", related="field_id.field_description")
    field_model_name = fields.Char(string="Model Name", related="field_id.model", store=True)
    field_type = fields.Selection(related="field_id.ttype", store=True)
    relation_model_name = fields.Char(related="field_id.relation", store=True)
    model_is_technical = fields.Boolean(compute="_compute_model_flags", store=True)
    model_is_business = fields.Boolean(compute="_compute_model_flags", store=True)
    warning_message = fields.Char(compute="_compute_warning_message")

    @api.depends("field_model_name")
    def _compute_model_flags(self):
        for line in self:
            model_name = line.field_model_name or ""
            line.model_is_technical = model_name.startswith(TECHNICAL_PREFIXES)
            line.model_is_business = not line.model_is_technical

    @api.depends("field_type", "relation_model_name")
    def _compute_warning_message(self):
        for line in self:
            if line.field_type not in ("many2one", "one2many", "many2many"):
                line.warning_message = False
            elif not line.relation_model_name:
                line.warning_message = "Relation metadata is missing; the field is treated as a plain field."
            else:
                line.warning_message = False

    @api.constrains("can_view", "can_edit")
    def _check_view_before_edit(self):
        for line in self:
            if line.can_edit and not line.can_view:
                raise ValidationError("A field cannot be editable if it is not viewable.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped("role_id")._apply_role_permissions()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.mapped("role_id")._apply_role_permissions()
        return res
