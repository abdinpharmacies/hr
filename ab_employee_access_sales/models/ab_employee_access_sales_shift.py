from odoo import api, fields, models


class AbSalesHrShift(models.Model):
    _name = "ab_employee_access_sales_shift"
    _inherit = "ab_odoo_sync_passive_mirror_mixin"
    _description = "Sales HR POS Shift"
    _order = "start_at desc, id desc"
    _log_access = False

    _uniq_sync_identity = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Source DB and record ID must be unique per POS shift.",
    )

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True, index=True)
    employee_id = fields.Many2one("ab_hr_employee", index=True)
    role_id = fields.Many2one("ab_employee_access_sales_role", index=True)
    service_user_id = fields.Many2one("ab_users", index=True)
    store_id = fields.Many2one("ab_store", index=True)
    state = fields.Selection(
        [
            ("open", "Open"),
            ("closed", "Closed"),
        ],
        default="open",

        index=True,
    )
    device_uid = fields.Char(index=True)
    device_name = fields.Char()
    start_at = fields.Datetime(default=fields.Datetime.now, index=True)
    last_activity_at = fields.Datetime(default=fields.Datetime.now)
    end_at = fields.Datetime()
    close_reason = fields.Char()

    session_ids = fields.One2many("ab_employee_access_sales_pos_session", "shift_id")
    operation_log_ids = fields.One2many("ab_employee_access_sales_operation_log", "shift_id")

    @api.depends("employee_id", "store_id", "start_at")
    def _compute_name(self):
        for rec in self:
            employee_name = rec.employee_id.display_name or rec.employee_id.name or "-"
            store_name = rec.store_id.display_name or rec.store_id.name or "-"
            rec.name = f"{employee_name} / {store_name} / {rec.start_at or ''}"
