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
    def prepare_record_snapshots(self, records):
        return [self.prepare_record_snapshot(record) for record in records]

    @api.model
    def filter_uncovered_upsert_snapshots(self, snapshots):
        snapshots = [snapshot for snapshot in snapshots or [] if snapshot]
        if not snapshots:
            return [], 0

        dated_snapshots = [
            snapshot for snapshot in snapshots if snapshot.get("source_write_date")
        ]
        if not dated_snapshots:
            return snapshots, 0

        min_write_date = min(
            snapshot["source_write_date"] for snapshot in dated_snapshots
        )
        model_names = sorted({snapshot["model_name"] for snapshot in dated_snapshots})
        rec_ids = sorted({snapshot["rec_id"] for snapshot in dated_snapshots})
        existing_events = self.sudo().search(
            [
                ("operation", "=", "upsert"),
                ("model_name", "in", model_names),
                ("rec_id", "in", rec_ids),
                ("source_write_date", ">=", min_write_date),
            ]
        )

        latest_write_by_key = {}
        for event in existing_events:
            if not event.source_write_date:
                continue
            key = (event.model_name, event.rec_id)
            latest_write_date = latest_write_by_key.get(key)
            if not latest_write_date or event.source_write_date > latest_write_date:
                latest_write_by_key[key] = event.source_write_date

        uncovered = []
        skipped = 0
        for snapshot in snapshots:
            source_write_date = snapshot.get("source_write_date")
            key = (snapshot.get("model_name"), snapshot.get("rec_id"))
            if (
                source_write_date
                and latest_write_by_key.get(key)
                and latest_write_by_key[key] >= source_write_date
            ):
                skipped += 1
                continue
            uncovered.append(snapshot)
        return uncovered, skipped

    @api.model
    def capture_prepared_snapshot(self, snapshot, operation="upsert"):
        return self.capture_prepared_snapshots([snapshot], operation=operation)[:1]

    @api.model
    def capture_prepared_snapshots(self, snapshots, operation="upsert"):
        if operation not in {"upsert", "archive"}:
            raise ValueError(
                _("Unsupported upload operation: %(operation)s")
                % {"operation": operation}
            )

        vals_list = []
        for snapshot in snapshots or []:
            vals = dict(snapshot)
            vals["operation"] = operation
            vals_list.append(vals)
        if not vals_list:
            return self.browse()

        outboxes = (
            self.with_context(skip_ab_odoo_sync_upload=True).sudo().create(vals_list)
        )
        for outbox in outboxes:
            outbox.with_context(skip_ab_odoo_sync_upload=True).sudo().write(
                {"source_revision": outbox.id}
            )
        if not self.env.context.get("defer_ab_odoo_sync_upload_sender"):
            self.env["ab_odoo_sync_service"].sudo().queue_branch_upload_batch()
        return outboxes

    @api.model
    def capture_record(self, record, operation="upsert"):
        snapshot = self.prepare_record_snapshot(record)
        return self.capture_prepared_snapshot(snapshot, operation=operation)

    @api.model
    def capture_records(self, records, operation="upsert"):
        snapshots = self.prepare_record_snapshots(records)
        return self.capture_prepared_snapshots(snapshots, operation=operation)

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
