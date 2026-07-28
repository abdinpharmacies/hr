from odoo import api, fields, models


class AbEmployeeAccess(models.Model):
    _inherit = "ab_employee_access"

    pos_pin = fields.Char(
        string="POS PIN",
        copy=False,
        default=lambda self: self._generate_pos_pin(),
        groups="ab_employee_access_sales.group_ab_employee_access_sales_manager"
    )

    pos_session_ids = fields.One2many("ab_employee_access_sales_pos_session", "profile_id")
    pos_operation_log_ids = fields.One2many("ab_employee_access_sales_operation_log", "profile_id")

    @api.depends("pos_pin_last_changed", "pos_pin_rotation_days", "pos_role_id.pin_rotation_days")
    def _compute_pos_pin_expired(self):
        now = fields.Datetime.now()
        for rec in self:
            rotation_days = rec._effective_pos_permissions().get("pin_rotation_days", 90)
            changed_at = rec.pos_pin_last_changed or rec.write_date or rec.create_date or now
            deadline = fields.Datetime.add(changed_at, days=rotation_days)
            rec.pos_pin_expired = bool(deadline and deadline < now)

    def _effective_pos_permissions(self):
        self.ensure_one()
        if self.pos_use_custom_permissions:
            return super()._effective_pos_permissions()
        if self.pos_role_id:
            return self.pos_role_id.permission_payload()
        return super()._effective_pos_permissions()

    def pos_permission_payload(self):
        self.ensure_one()
        payload = super().pos_permission_payload()
        payload.update({
            "role_id": self.pos_role_id.id if self.pos_role_id else False,
            "role_name": self.pos_role_id.display_name if self.pos_role_id else "",
        })
        return payload
