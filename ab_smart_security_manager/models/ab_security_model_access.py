from odoo import _, api, fields, models


TECHNICAL_PREFIXES = ("ir.", "mail.", "bus.", "base.", "web.", "auth.")


class AbSecurityModelAccess(models.Model):
    _name = "ab_security_model_access"
    _description = "Smart Security Model Access"
    _order = "role_id, model_id"

    _role_model_unique = models.Constraint(
        "unique(role_id, model_id)",
        "A role can only have one managed ACL line per model.",
    )

    role_id = fields.Many2one(
        "ab_security_role",
        required=True,
        ondelete="cascade",
    )
    model_id = fields.Many2one(
        "ir.model",
        required=True,
        domain="[('transient', '=', False)]",
        ondelete="cascade",
    )
    perm_read = fields.Boolean(default=True)
    perm_write = fields.Boolean(default=False)
    perm_create = fields.Boolean(default=False)
    perm_unlink = fields.Boolean(default=False)
    active = fields.Boolean(default=True)
    model_name = fields.Char(string="Model Name", related="model_id.model", store=True)
    model_display_name = fields.Char(string="Model Label", related="model_id.name")
    model_is_technical = fields.Boolean(compute="_compute_model_flags", store=True)
    model_is_business = fields.Boolean(compute="_compute_model_flags", store=True)
    managed_access_id = fields.One2many(
        "ir.model.access",
        "ab_security_model_access_id",
        string="Generated ACLs",
    )

    @api.depends("model_name")
    def _compute_model_flags(self):
        for line in self:
            model_name = line.model_name or ""
            line.model_is_technical = model_name.startswith(TECHNICAL_PREFIXES)
            line.model_is_business = not line.model_is_technical and not line.model_id.transient

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_ir_model_access()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sync_ir_model_access()
        return res

    def unlink(self):
        self.write({"active": False})
        return True

    def _sync_ir_model_access(self):
        for line in self:
            access = line.managed_access_id[:1]
            access_vals = {
                "name": f"ab_smart_security_manager.{line.role_id.group_id.id}.{line.model_name}",
                "model_id": line.model_id.id,
                "group_id": line.role_id.group_id.id,
                "perm_read": line.perm_read,
                "perm_write": line.perm_write,
                "perm_create": line.perm_create,
                "perm_unlink": line.perm_unlink,
                "active": line.active,
                "ab_security_managed": True,
                "ab_security_model_access_id": line.id,
            }
            if access:
                access.sudo().write(access_vals)
            else:
                self.env["ir.model.access"].sudo().create(access_vals)
        return True
