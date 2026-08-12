from odoo import fields, models
from odoo.tools.translate import _


class AbOdooSyncCheckpoint(models.Model):
    _name = "ab_odoo_sync_checkpoint"
    _description = "AB Odoo Sync Checkpoint"

    db_serial = fields.Integer(string="DB Serial", required=True, index=True)
    last_event_id = fields.Integer(default=0, required=True, index=True)
    last_sync_at = fields.Datetime()
    active = fields.Boolean(default=True, index=True)

    _uniq_db_serial = models.Constraint(
        "UNIQUE(db_serial)",
        "DB serial must be unique.",
    )

    def action_cleanup_consumed_events(self):
        result = self.env["ab_odoo_sync_service"].sudo().cleanup_consumed_events()
        status = result.get("status")
        deleted = result.get("deleted", 0)
        watermark = result.get("watermark", 0)
        reason = result.get("reason")
        if status == "ok" and reason:
            message = reason
            notification_type = "warning"
        elif status == "ok":
            message = _("Deleted %(deleted)s consumed sync event(s). Watermark: %(watermark)s.") % {
                "deleted": deleted,
                "watermark": watermark,
            }
            notification_type = "success"
        else:
            message = reason or _("Manual sync event cleanup did not run.")
            notification_type = "warning"
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
