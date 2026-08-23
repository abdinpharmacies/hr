import uuid

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbOdooSyncOutbox(models.Model):
    _name = "ab_odoo_sync_outbox"
    _description = "AB Odoo Sync Upload Outbox"
    _order = "id desc"

    event_uuid = fields.Char(
        string="Event UUID",
        required=True,
        readonly=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
    )
    db_serial = fields.Integer(string="DB Serial", required=True, readonly=True, index=True)
    model_name = fields.Char(string="Source Model", required=True, readonly=True, index=True)
    rec_id = fields.Integer(string="Source Record ID", required=True, readonly=True, index=True)
    source_revision = fields.Integer(string="Source Revision", readonly=True, index=True)
    operation = fields.Selection(
        selection=[("upsert", "Upsert"), ("archive", "Archive")],
        required=True,
        readonly=True,
        index=True,
    )
    payload_json = fields.Json(string="Full Payload", default=dict, readonly=True)
    source_write_date = fields.Datetime(string="Source Write Date", readonly=True, index=True)
    status = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("failed", "Failed"),
            ("not_sync", "Not Sync"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    attempt_count = fields.Integer(string="Attempt Count", default=0, readonly=True)
    last_error = fields.Text(string="Last Error", readonly=True)
    sent_at = fields.Datetime(string="Sent At", readonly=True)
    active = fields.Boolean(default=True, index=True)

    _uniq_event_uuid = models.Constraint(
        "UNIQUE(event_uuid)",
        "Upload outbox event UUID must be unique.",
    )

    @api.model
    def prepare_record_snapshot(self, record):
        record.ensure_one()
        service = self.env["ab_odoo_sync_service"].sudo()
        payload = service.serialize_stored_record(record.sudo())
        return {
            "db_serial": service.get_db_serial(),
            "model_name": record._name,
            "rec_id": record.id,
            "payload_json": payload,
            "source_write_date": record.write_date or fields.Datetime.now(),
        }

    @api.model
    def capture_prepared_snapshot(self, snapshot, operation="upsert"):
        if operation not in {"upsert", "archive"}:
            raise ValueError(
                _("Unsupported upload operation: %(operation)s")
                % {"operation": operation}
            )

        vals = dict(snapshot)
        vals["operation"] = operation
        outbox = self.with_context(skip_ab_odoo_sync_upload=True).sudo().create(vals)
        outbox.with_context(skip_ab_odoo_sync_upload=True).sudo().write(
            {"source_revision": outbox.id}
        )
        self.env["ab_odoo_sync_service"].sudo().queue_branch_upload_batch()
        return outbox

    @api.model
    def capture_record(self, record, operation="upsert"):
        snapshot = self.prepare_record_snapshot(record)
        return self.capture_prepared_snapshot(snapshot, operation=operation)

    def action_send_now(self):
        result = self.env["ab_odoo_sync_service"].sudo().queue_branch_upload_batch(self)
        return self._notification(
            _("Odoo Sync Upload"),
            _("Queued %(count)s outbox event(s) for sending.")
            % {
                "count": result.get("queued", 0),
            },
            "success" if result.get("queued") else "warning",
        )

    def action_retry(self):
        retry_records = self.filtered(lambda record: record.status == "failed")
        retry_records.sudo().write(
            {
                "status": "pending",
                "last_error": False,
            }
        )
        return self._notification(
            _("Odoo Sync Upload"),
            _("Reset %(count)s failed outbox event(s) to Pending.") % {"count": len(retry_records)},
            "success" if retry_records else "warning",
        )

    def action_mark_not_sync(self):
        records = self.filtered(lambda record: record.status in {"pending", "failed"})
        records.sudo().write({"status": "not_sync", "active": False})
        return self._notification(
            _("Odoo Sync Upload"),
            _("Marked %(count)s outbox event(s) as Not Sync.") % {"count": len(records)},
            "success" if records else "warning",
        )

    @api.model
    def _notification(self, title, message, notification_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            },
        }

    def unlink(self):
        raise UserError(_("Upload outbox events are audit records and cannot be deleted."))
