"""Immutable delivery receipts; processing never controls delivery acknowledgement."""
import hashlib
import json
import uuid

from psycopg2 import OperationalError
from psycopg2.errors import UniqueViolation

from odoo import api, fields, models
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _


class AbOdooSyncUploadReceipt(models.Model):
    _name = "ab_odoo_sync_upload_receipt"
    _description = "Branch Upload Receipt"
    _order = "received_at desc, id desc"
    _rec_name = "payload_hash"

    branch_id = fields.Many2one("ab_odoo_sync_branch_registry", string="Authenticated Branch",
                                required=True, readonly=True, index=True, ondelete="restrict")
    db_serial = fields.Integer(string="DB Serial", required=True, readonly=True, index=True)
    raw_row = fields.Text(string="Original Uploaded Row", required=True, readonly=True, groups="base.group_system")
    payload_hash = fields.Char(string="Payload Hash", required=True, readonly=True, index=True)
    event_uuid = fields.Char(string="Event UUID", readonly=True, index=True)
    received_at = fields.Datetime(string="Received At", required=True, readonly=True, default=fields.Datetime.now)
    processed_at = fields.Datetime(string="Processed At", readonly=True)
    status = fields.Selection([
        ("pending", "Received"), ("queued", "Processing Queued"),
        ("processed", "Processed"), ("ignored", "Older or Duplicate Revision"),
        ("quarantined", "Quarantined"), ("failed", "Processing Failed"),
    ], string="Receipt Status", required=True, readonly=True, index=True, default="pending")
    error_message = fields.Text(string="Processing Details", readonly=True)
    upload_record_id = fields.Many2one("ab_odoo_sync_upload_record", string="Upload Record",
                                       readonly=True, ondelete="restrict")
    application_status = fields.Selection(related="upload_record_id.status", string="Current Application Status", readonly=True)

    _unique_branch_hash = models.Constraint("UNIQUE(branch_id, payload_hash)", "Receipt must be unique per branch and payload.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Upload receipts are created only by the authenticated receiver."))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_("Original upload receipts cannot be edited."))

    def unlink(self):
        raise UserError(_("Original upload receipts cannot be deleted."))

    def _set_processing(self, vals):
        return super().write(vals)

    @api.model
    def _store(self, branch, row):
        raw = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        domain = fields.Domain("branch_id", "=", branch.id) & fields.Domain("payload_hash", "=", digest)
        existing = self.search(domain, limit=1)
        if existing:
            return existing, False
        event = False
        if isinstance(row, dict) and row.get("event_uuid"):
            try:
                event = str(uuid.UUID(str(row["event_uuid"])))
            except (ValueError, TypeError, AttributeError):
                pass  # Preserve invalid metadata; processing will quarantine it.
        vals = {"branch_id": branch.id, "db_serial": branch.db_serial, "raw_row": raw, "payload_hash": digest, "event_uuid": event}
        if event and self.search_count(fields.Domain("branch_id", "=", branch.id) & fields.Domain("event_uuid", "=", event)):
            vals.update(status="quarantined", error_message=_("Event ID was reused with different content."))
        try:
            with self.env.cr.savepoint():
                receipt = self.create(vals)
        except UniqueViolation:
            existing = self.search(domain, limit=1)
            if not existing:
                raise  # Concurrent transaction: sender retries without a false acknowledgement.
            return existing, False
        return receipt, True

    def _queue_processing(self, recover=False):
        self.ensure_one()
        if self.status == "queued" and recover:
            active_job = self.env["queue.job"].sudo().search_count(
                fields.Domain("identity_key", "=", f"ab_odoo_sync_receipt:{self.id}")
                & fields.Domain("state", "in", ["pending", "enqueued", "started", "wait_dependencies"])
            )
            if active_job:
                return 0
        elif self.status not in {"pending", "failed"}:
            return 0
        try:
            with self.env.cr.savepoint():
                self.with_delay(identity_key=f"ab_odoo_sync_receipt:{self.id}", max_retries=5,
                                description=_("Process stored branch upload receipt")).job_process_receipt()
                self._set_processing({"status": "queued", "error_message": False})
        except OperationalError:
            raise
        except Exception:
            self._set_processing({"status": "pending", "error_message": _("Receipt is stored. Processing could not be queued; retry processing.")})
            return 0
        return 1

    def action_retry_processing(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can retry receipt processing."))
        for receipt in self.sudo():
            receipt._queue_processing(recover=True)
        return True

    @api.private
    def job_process_receipt(self):
        self.ensure_one()
        receipt = self.sudo().try_lock_for_update()
        if not receipt:
            raise RetryableJobError("Receipt is being processed", seconds=10)
        if receipt.status not in {"pending", "queued", "failed"}:
            return
        # Never expose raw row values through diagnostics or exception logs.
        try:
            row = json.loads(receipt.raw_row)
            if not isinstance(row, dict):
                raise ValueError()
            service = self.env["ab_odoo_sync_service"].sudo()
            Upload = self.env["ab_odoo_sync_upload_record"].sudo()
            name = Upload.validate_source_model_name(row.get("model_name"))
            if service._upload_source_security_error(name):
                receipt._set_processing({"status": "quarantined", "error_message": _("Source model is protected; this receipt will not be applied.")})
                return
            serial = receipt.db_serial
            if "db_serial" in row and service.parse_positive_int(row["db_serial"], "db_serial") != serial:
                receipt._set_processing({"status": "quarantined", "error_message": _("Row branch identity does not match the authenticated branch.")})
                return
            if any(isinstance(row.get(key), (bool, float)) for key in ("rec_id", "source_revision")):
                raise ValueError()
            rec_id = service.parse_positive_int(row.get("rec_id"), "rec_id")
            revision = service.parse_positive_int(row.get("source_revision", 1), "source_revision")
            if max(rec_id, revision) > 2147483647:
                raise ValueError()
            payload = row.get("payload")
            operation = row.get("operation", "upsert")
            if not isinstance(payload, dict) or operation not in {"upsert", "archive"}:
                raise ValueError()
            event = str(uuid.UUID(str(row["event_uuid"]))) if row.get("event_uuid") else str(uuid.uuid5(uuid.NAMESPACE_URL, f"ab-sync:{receipt.branch_id.id}:{receipt.payload_hash}"))
            date = fields.Datetime.to_datetime(row.get("source_write_date")) if row.get("source_write_date") else False
            # Earlier receipt wins an event identity; never overwrite its contents.
            conflict = self.search(fields.Domain("branch_id", "=", receipt.branch_id.id) & fields.Domain("event_uuid", "=", event)
                                   & fields.Domain("id", "<", receipt.id), limit=1)
            current_event = Upload.search(fields.Domain("event_uuid", "=", event), limit=1)
            if conflict or (current_event and any((
                current_event.db_serial != serial, current_event.model_name != name,
                current_event.rec_id != rec_id, current_event.source_revision != revision,
                current_event.payload_json != payload, current_event.source_operation != operation,
                current_event.source_write_date != date,
            ))):
                receipt._set_processing({"status": "quarantined", "error_message": _("Event ID was reused with different content.")})
                return
        except (ValueError, TypeError, AttributeError, OverflowError):
            receipt._set_processing({"status": "quarantined", "error_message": _("Invalid row metadata. Original data is preserved for inspection.")})
            return
        try:
            with self.env.cr.savepoint():
                current = Upload.search(fields.Domain("db_serial", "=", serial) & fields.Domain("model_name", "=", name)
                                        & fields.Domain("rec_id", "=", rec_id), limit=1)
                if current and not current.try_lock_for_update():
                    raise RetryableJobError("Source record is being processed", seconds=10)
                if current and revision <= current.source_revision:
                    receipt._set_processing({"status": "ignored", "upload_record_id": current.id,
                                             "processed_at": fields.Datetime.now(), "error_message": False})
                    return
                profile, mapping_error = service._ensure_same_name_passive_profile(name, payload=payload)
                upload, changed = Upload.upsert_from_upload(db_serial=serial, model_name=name, rec_id=rec_id, payload=payload,
                    event_uuid=event, source_revision=revision, source_operation=operation, source_write_date=date)
                if mapping_error and upload.status == "pending_mapping":
                    upload.write({"error_message": mapping_error})
                if changed and upload.apply_profile_id.auto_apply and upload.apply_profile_id.apply_mode in {"mirror_sync", "business_model"}:
                    upload._queue_apply_records()
                receipt._set_processing({"status": "processed" if changed else "ignored", "upload_record_id": upload.id,
                                         "processed_at": fields.Datetime.now(), "error_message": False})
        except (OperationalError, RetryableJobError):
            raise
        except UniqueViolation as ex:
            # Concurrent source creation must retry with a fresh transaction snapshot.
            raise RetryableJobError("Concurrent receipt processing", seconds=10) from ex
        except Exception as ex:
            receipt._set_processing({"status": "failed", "error_message": _("Receipt is stored. Processing failed (%s); correct the mapping and retry.") % type(ex).__name__})
