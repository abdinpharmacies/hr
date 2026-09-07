from odoo import api, fields, models


class AbSalesHrPosSession(models.Model):
    _name = "ab_employee_access_sales_pos_session"
    _inherit = "ab_odoo_sync_passive_mirror_mixin"
    _description = "Sales HR POS Session"
    _order = "login_at desc, id desc"
    _log_access = False

    _uniq_sync_identity = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Source DB and record ID must be unique per POS session.",
    )

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True, index=True)
    session_token = fields.Char(copy=False, index=True)
    employee_id = fields.Many2one("ab_hr_employee", index=True)
    profile_id = fields.Many2one("ab_employee_access", index=True, ondelete="restrict")
    role_id = fields.Many2one("ab_employee_access_sales_role", index=True)
    shift_id = fields.Many2one("ab_employee_access_sales_shift", index=True, ondelete="set null")
    service_user_id = fields.Many2one("ab_users", index=True)
    store_id = fields.Many2one("ab_store", index=True)

    state = fields.Selection(
        [
            ("active", "Active"),
            ("locked", "Locked"),
            ("closed", "Closed"),
        ],

        default="active",
        index=True,
    )
    device_uid = fields.Char(index=True)
    device_name = fields.Char()
    device_ip = fields.Char(index=True)
    login_at = fields.Datetime(default=fields.Datetime.now, index=True)
    last_activity_at = fields.Datetime(default=fields.Datetime.now)
    locked_at = fields.Datetime()
    logout_at = fields.Datetime()
    unlock_count = fields.Integer(default=0)

    operation_log_ids = fields.One2many("ab_employee_access_sales_operation_log", "session_id")

    _session_token_key = models.Constraint(
        "UNIQUE(session_token)",
        "POS session token must be unique.",
    )

    @api.depends("employee_id", "store_id", "login_at")
    def _compute_name(self):
        for rec in self:
            employee_name = rec.employee_id.display_name or rec.employee_id.name or "-"
            store_name = rec.store_id.display_name or rec.store_id.name or "-"
            rec.name = f"{employee_name} / {store_name} / {rec.login_at or ''}"
