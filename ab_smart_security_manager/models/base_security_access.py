from odoo import api, models


class AbBaseSecurityAccess(models.AbstractModel):
    _inherit = "base"

    @api.model
    def _ab_field_access_cache(self):
        if self.env.su or self.env.context.get("ab_security_skip_field_access"):
            return {}

        role_ids = self.env["ab_security_role"].with_context(ab_security_skip_field_access=True).sudo().search(
            [("group_id", "in", list(self.env.user._get_group_ids()))]
        ).ids
        if not role_ids:
            return {}

        access_lines = self.env["ab_security_field_access"].with_context(ab_security_skip_field_access=True).sudo().search(
            [
                ("role_id", "in", role_ids),
                ("field_id.model", "=", self._name),
            ]
        )
        access_map = {}
        for line in access_lines:
            field_entry = access_map.setdefault(
                line.field_id.name,
                {"read": False, "write": False, "restricted": True},
            )
            field_entry["read"] = field_entry["read"] or line.can_view
            field_entry["write"] = field_entry["write"] or line.can_edit
        return access_map

    @api.model
    def _has_field_access(self, field, operation):
        base_allowed = super()._has_field_access(field, operation)
        if not base_allowed or self.env.su or self.env.context.get("ab_security_skip_field_access"):
            return base_allowed
        access_map = self._ab_field_access_cache()
        field_access = access_map.get(field.name)
        if not field_access:
            return base_allowed
        return base_allowed and field_access["read" if operation == "read" else "write"]
