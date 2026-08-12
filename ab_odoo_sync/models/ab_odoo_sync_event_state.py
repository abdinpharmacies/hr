from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbOdooSyncEventState(models.Model):
    _name = "ab_odoo_sync_event_state"
    _description = "AB Odoo Sync Event State"
    _order = "source_event_id desc, id desc"

    source_event_id = fields.Integer(string="Source Event ID", required=True, index=True, readonly=True)
    db_serial = fields.Integer(string="DB Serial", required=True, index=True, readonly=True)
    model_name = fields.Char(string="Model Name", required=True, index=True, readonly=True)
    record_id = fields.Integer(string="Record ID", required=True, index=True, readonly=True)
    operation = fields.Selection(
        string="Operation",
        selection=[
            ("create", "Create"),
            ("write", "Write"),
            ("unlink", "Unlink"),
        ],
        required=True,
        index=True,
        readonly=True,
    )
    status = fields.Selection(
        string="Status",
        selection=[
            ("pending", "Pending"),
            ("full_sync", "Full Sync"),
            ("partially_sync", "Partially Sync"),
            ("failed", "Failed"),
            ("not_sync", "Not Sync"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    skipped_fields_json = fields.Json(string="Skipped Fields", default=list, readonly=True)
    error_message = fields.Text(string="Error Message", readonly=True)
    payload_json = fields.Json(string="Payload", default=dict, readonly=True)
    applied_at = fields.Datetime(string="Applied At", readonly=True)

    _uniq_source_event_db = models.Constraint(
        "UNIQUE(source_event_id, db_serial)",
        "Source event must be unique per database serial.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("ab_odoo_sync_allow_event_state_write"):
            raise UserError(_("Sync event states are created by the sync service only."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("ab_odoo_sync_allow_event_state_write"):
            if set(vals) != {"status"} or vals.get("status") != "not_sync":
                raise UserError(_("Use Mark Not Sync to manually skip a sync event."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Sync event states are audit records and cannot be deleted."))

    def action_mark_not_sync(self):
        eligible = self.filtered(lambda rec: rec.status in ("pending", "failed"))
        if not eligible:
            message = _("Only Pending or Failed sync events can be marked as Not Sync.")
            notification_type = "warning"
        else:
            eligible.with_context(ab_odoo_sync_allow_event_state_write=True).write(
                {
                    "status": "not_sync",
                    "applied_at": fields.Datetime.now(),
                }
            )
            message = _("Selected sync event(s) were marked as Not Sync.")
            notification_type = "success"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Odoo Sync"),
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }
