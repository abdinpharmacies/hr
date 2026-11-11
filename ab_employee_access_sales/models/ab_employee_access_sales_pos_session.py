import secrets

from odoo import api, fields, models


class AbSalesHrPosSession(models.Model):
    _name = "ab_employee_access_sales_pos_session"
    _description = "Sales HR POS Session"
    _order = "login_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    session_token = fields.Char(required=True, copy=False, index=True)
    employee_id = fields.Many2one("ab_hr_employee", required=True, index=True)
    profile_id = fields.Many2one("ab_employee_access", index=True, ondelete="restrict")
    role_id = fields.Many2one("ab_employee_access_sales_role", index=True)
    shift_id = fields.Many2one("ab_employee_access_sales_shift", index=True, ondelete="set null")
    service_user_id = fields.Many2one("res.users", required=True, index=True)
    store_id = fields.Many2one("ab_store", required=True, index=True)

    state = fields.Selection(
        [
            ("active", "Active"),
            ("locked", "Locked"),
            ("closed", "Closed"),
        ],
        required=True,
        default="active",
        index=True,
    )
    device_uid = fields.Char(required=True, index=True)
    device_name = fields.Char()
    device_ip = fields.Char(index=True)
    login_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    last_activity_at = fields.Datetime(default=fields.Datetime.now)
    locked_at = fields.Datetime()
    logout_at = fields.Datetime()
    unlock_count = fields.Integer(default=0)

    operation_log_ids = fields.One2many("ab_employee_access_sales_operation_log", "session_id")

    _session_token_key = models.Constraint(
        "UNIQUE(session_token)",
        "POS session token must be unique.",
    )

    @api.model
    def _new_session_token(self):
        return secrets.token_urlsafe(24)

    @api.depends("employee_id", "store_id", "login_at")
    def _compute_name(self):
        for rec in self:
            employee_name = rec.employee_id.display_name or rec.employee_id.name or "-"
            store_name = rec.store_id.display_name or rec.store_id.name or "-"
            rec.name = f"{employee_name} / {store_name} / {rec.login_at or ''}"

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        now = fields.Datetime.now()
        for vals in vals_list:
            values = dict(vals or {})
            values.setdefault("session_token", self._new_session_token())
            values.setdefault("login_at", now)
            values.setdefault("last_activity_at", now)
            prepared.append(values)
        return super().create(prepared)

    def mark_activity(self):
        now = fields.Datetime.now()
        self.write({
            "last_activity_at": now,
            "locked_at": False,
            "state": "active",
        })
        self.mapped("shift_id").write({"last_activity_at": now})
        return True

    def lock_session(self):
        now = fields.Datetime.now()
        active_sessions = self.filtered(lambda session: session.state == "active")
        if active_sessions:
            active_sessions.write({
                "state": "locked",
                "locked_at": now,
                "last_activity_at": now,
            })
        return True

    def unlock_session(self):
        now = fields.Datetime.now()
        locked_sessions = self.filtered(lambda session: session.state == "locked")
        for session in locked_sessions:
            session.write({
                "state": "active",
                "locked_at": False,
                "last_activity_at": now,
                "unlock_count": int(session.unlock_count or 0) + 1,
            })
        if locked_sessions:
            locked_sessions.mapped("shift_id").write({"last_activity_at": now})
        return True

    def close_session(self):
        now = fields.Datetime.now()
        open_sessions = self.filtered(lambda session: session.state in {"active", "locked"})
        if open_sessions:
            open_sessions.write({
                "state": "closed",
                "logout_at": now,
                "last_activity_at": now,
            })
        return True

    def _get_pos_profile(self):
        self.ensure_one()
        return self.profile_id or self.env["ab_employee_access"].sudo().search(
            [("employee_id", "=", self.employee_id.id)],
            limit=1,
        )

    def payload(self):
        self.ensure_one()
        employee = self.employee_id
        profile = self._get_pos_profile()
        permissions = profile._effective_pos_permissions() if profile else {}
        return {
            "token": self.session_token,
            "session_id": self.id,
            "profile_id": profile.id if profile else False,
            "shift_id": self.shift_id.id if self.shift_id else False,
            "state": self.state,
            "store": {
                "id": self.store_id.id,
                "name": self.store_id.display_name or self.store_id.name or "",
                "code": self.store_id.code or "",
            },
            "employee": {
                "id": employee.id,
                "name": employee.display_name or employee.name or "",
                "code": employee.barcode or employee.accid or "",
                "role_id": profile.pos_role_id.id if profile.pos_role_id else False,
                "role_name": profile.pos_role_id.display_name if profile.pos_role_id else "",
            },
            "permissions": permissions,
            "pin_expired": bool(profile.pos_pin_expired),
            "service_user_id": self.service_user_id.id,
            "service_user_name": self.service_user_id.display_name or "",
            "device_uid": self.device_uid or "",
            "device_name": self.device_name or "",
            "device_ip": self.device_ip or "",
        }
