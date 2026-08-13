import logging
import re

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

_MODEL_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_SKIPPED_SYSTEM_FIELDS = {
    "id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "__last_update",
    "display_name",
}


class AbOdooSyncUploadRecord(models.Model):
    _name = "ab_odoo_sync_upload_record"
    _description = "AB Odoo Sync Upload Record"
    _order = "received_at desc, id desc"

    db_serial = fields.Integer(string="DB Serial", required=True, index=True, readonly=True)
    model_name = fields.Char(string="Source Model", required=True, index=True, readonly=True)
    rec_id = fields.Integer(string="Source Record ID", required=True, index=True, readonly=True)
    target_model_name = fields.Char(string="Target Model", required=True, index=True, readonly=True)
    payload_json = fields.Json(string="Payload", default=dict, readonly=True)
    status = fields.Selection(
        string="Status",
        selection=[
            ("pending", "Pending"),
            ("queued", "Queued"),
            ("applied", "Applied"),
            ("failed", "Failed"),
            ("not_sync", "Not Sync"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    skipped_fields_json = fields.Json(string="Skipped Fields", default=list, readonly=True)
    error_message = fields.Text(string="Error Message", readonly=True)
    received_at = fields.Datetime(string="Received At", default=fields.Datetime.now, required=True, readonly=True)
    queued_at = fields.Datetime(string="Queued At", readonly=True)
    applied_at = fields.Datetime(string="Applied At", readonly=True)
    attempt_count = fields.Integer(string="Attempt Count", default=0, readonly=True)
    active = fields.Boolean(default=True, index=True)

    _uniq_upload_record = models.Constraint(
        "UNIQUE(db_serial, model_name, rec_id)",
        "Uploaded record must be unique per database serial, source model, and source record ID.",
    )

    @api.model
    def target_model_from_source(self, model_name):
        return f"{model_name}__sync"

    @api.model
    def validate_source_model_name(self, model_name):
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError(_("model_name is required."))
        model_name = model_name.strip()
        if not _MODEL_NAME_RE.match(model_name):
            raise ValueError(_("model_name must contain lowercase letters, numbers, and underscores only."))
        return model_name

    @api.model
    def _normalize_payload_value(self, target_model, field_name, value):
        field = target_model._fields.get(field_name)
        if field and field.type == "many2one" and isinstance(value, (list, tuple)):
            return value[0] if value else False
        return value

    @api.model
    def upsert_from_upload(self, db_serial, model_name, rec_id, payload):
        model_name = self.validate_source_model_name(model_name)
        rec_id = int(rec_id or 0)
        if rec_id <= 0:
            raise ValueError(_("rec_id must be a positive integer."))
        if not isinstance(payload, dict):
            raise ValueError(_("payload must be a JSON object."))

        target_model_name = self.target_model_from_source(model_name)
        vals = {
            "payload_json": payload,
            "target_model_name": target_model_name,
            "status": "pending",
            "skipped_fields_json": [],
            "error_message": False,
            "received_at": fields.Datetime.now(),
            "queued_at": False,
            "applied_at": False,
            "active": True,
        }
        record = self.with_context(active_test=False).sudo().search(
            [
                ("db_serial", "=", db_serial),
                ("model_name", "=", model_name),
                ("rec_id", "=", rec_id),
            ],
            limit=1,
        )
        if record:
            record.write(vals)
            return record

        vals.update(
            {
                "db_serial": db_serial,
                "model_name": model_name,
                "rec_id": rec_id,
            }
        )
        return self.sudo().create(vals)

    def _queue_identity_key(self):
        self.ensure_one()
        return f"ab_odoo_sync_upload_record_apply:{self.id}"

    def _queue_apply_records(self):
        queued_count = 0
        now = fields.Datetime.now()
        for record in self.sudo().exists():
            if record.status in {"applied", "not_sync"}:
                continue
            record.write(
                {
                    "status": "queued",
                    "queued_at": now,
                    "error_message": False,
                }
            )
            record.with_delay(
                identity_key=record._queue_identity_key(),
                description=_("Apply uploaded sync record %(record_id)s") % {"record_id": record.id},
            ).job_apply_to_target()
            queued_count += 1
        return queued_count

    def action_queue_apply(self):
        queued_count = self._queue_apply_records()
        return self._notification(
            _("Odoo Sync Upload"),
            _("Queued %(count)s upload record(s) for apply.") % {"count": queued_count},
            "success" if queued_count else "warning",
        )

    def action_replay_failed(self):
        records = self.filtered(lambda rec: rec.status == "failed")
        queued_count = records._queue_apply_records()
        return self._notification(
            _("Odoo Sync Upload"),
            _("Queued %(count)s failed upload record(s) for replay.") % {"count": queued_count},
            "success" if queued_count else "warning",
        )

    def action_mark_not_sync(self):
        records = self.filtered(lambda rec: rec.status in {"pending", "queued", "failed"})
        records.sudo().write(
            {
                "status": "not_sync",
                "applied_at": fields.Datetime.now(),
                "error_message": False,
            }
        )
        return self._notification(
            _("Odoo Sync Upload"),
            _("Marked %(count)s upload record(s) as Not Sync.") % {"count": len(records)},
            "success" if records else "warning",
        )

    def _notification(self, title, message, notification_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }

    def _get_target_model(self):
        self.ensure_one()
        try:
            return self.env[self.target_model_name].with_context(
                active_test=False,
                skip_ab_odoo_sync_event=True,
            ).sudo()
        except KeyError as ex:
            raise ValueError(_("Target sync model %(model)s does not exist.") % {"model": self.target_model_name}) from ex

    def _prepare_target_vals(self, target_model):
        self.ensure_one()
        if "db_serial" not in target_model._fields or "rec_id" not in target_model._fields:
            raise ValueError(
                _("Target sync model %(model)s must define db_serial and rec_id fields.")
                % {"model": self.target_model_name}
            )

        payload = self.payload_json or {}
        if not isinstance(payload, dict):
            raise ValueError(_("payload must be a JSON object."))

        vals = {
            "db_serial": self.db_serial,
            "rec_id": self.rec_id,
        }
        skipped_fields = []
        if "payload_json" in target_model._fields:
            vals["payload_json"] = payload

        for field_name, value in payload.items():
            if field_name in _SKIPPED_SYSTEM_FIELDS or field_name in {"db_serial", "rec_id"}:
                continue

            field = target_model._fields.get(field_name)
            if not field:
                skipped_fields.append(field_name)
                continue
            if field.type in {"one2many", "many2many"}:
                skipped_fields.append(field_name)
                continue
            if getattr(field, "compute", None) and not getattr(field, "inverse", None):
                skipped_fields.append(field_name)
                continue
            if getattr(field, "related", None) and not getattr(field, "inverse", None):
                skipped_fields.append(field_name)
                continue
            vals[field_name] = self._normalize_payload_value(target_model, field_name, value)

        return vals, skipped_fields

    def job_apply_to_target(self):
        for record in self.sudo().exists():
            record._apply_to_target()

    def _apply_to_target(self):
        self.ensure_one()
        if self.status == "not_sync":
            return

        try:
            with self.env.cr.savepoint():
                target_model = self._get_target_model()
                vals, skipped_fields = self._prepare_target_vals(target_model)
                existing = target_model.search(
                    [
                        ("db_serial", "=", self.db_serial),
                        ("rec_id", "=", self.rec_id),
                    ],
                    limit=1,
                )
                if existing:
                    existing.write(vals)
                else:
                    target_model.create(vals)
        except Exception as ex:
            _logger.exception(
                "ab_odoo_sync upload apply failed for %s db_serial=%s rec_id=%s",
                self.model_name,
                self.db_serial,
                self.rec_id,
            )
            self.write(
                {
                    "status": "failed",
                    "attempt_count": self.attempt_count + 1,
                    "error_message": str(ex),
                    "applied_at": fields.Datetime.now(),
                }
            )
            return

        self.write(
            {
                "status": "applied",
                "attempt_count": self.attempt_count + 1,
                "skipped_fields_json": skipped_fields,
                "error_message": False,
                "applied_at": fields.Datetime.now(),
            }
        )

    def unlink(self):
        raise UserError(_("Sync upload records are audit records and cannot be deleted."))
