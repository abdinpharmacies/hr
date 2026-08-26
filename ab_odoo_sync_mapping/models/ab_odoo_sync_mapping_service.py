import logging

from odoo import api, fields, models
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)


class AbOdooSyncMappingService(models.AbstractModel):
    _inherit = "ab_odoo_sync_service"

    @api.model
    def get_registered_branch(self, db_serial):
        db_serial = self.parse_positive_int(db_serial, "db_serial")
        branch = self.env["ab_odoo_sync_branch_registry"].sudo().search(
            [("db_serial", "=", db_serial), ("active", "=", True)],
            limit=1,
        )
        if not branch:
            raise ValueError(_("Unknown or inactive db_serial."))
        return branch

    @api.model
    def receive_upload_batch(self, payload):
        if not isinstance(payload, dict):
            raise ValueError(_("Upload payload must be a JSON object."))

        db_serial = self.parse_positive_int(payload.get("db_serial"), "db_serial")
        branch = self.get_registered_branch(db_serial)
        records = payload.get("records")
        if not isinstance(records, list):
            raise ValueError(_("records must be a JSON array."))

        upload_model = self.env["ab_odoo_sync_upload_record"].sudo()
        result = {
            "accepted": 0,
            "queued": 0,
            "ignored": 0,
            "failed": 0,
            "errors": [],
        }
        for index, row in enumerate(records):
            if not isinstance(row, dict):
                result["failed"] += 1
                result["errors"].append(
                    {"index": index, "error": _("record must be a JSON object.")}
                )
                continue
            try:
                model_name = upload_model.validate_source_model_name(
                    row.get("model_name")
                )
                rec_id = self.parse_positive_int(row.get("rec_id"), "rec_id")
                payload_json = row.get("payload")
                if not isinstance(payload_json, dict):
                    raise ValueError(_("payload must be a JSON object."))
                upload_record, changed = upload_model.upsert_from_upload(
                    db_serial=db_serial,
                    model_name=model_name,
                    rec_id=rec_id,
                    payload=payload_json,
                    event_uuid=row.get("event_uuid"),
                    source_revision=row.get("source_revision") or 1,
                    source_operation=row.get("operation") or "upsert",
                    source_write_date=row.get("source_write_date") or False,
                )
                result["accepted"] += 1
                if not changed:
                    result["ignored"] += 1
                    continue
                profile = upload_record.apply_profile_id
                if (
                    profile
                    and profile.auto_apply
                    and profile.apply_mode in {"mirror_sync", "business_model"}
                ):
                    result["queued"] += upload_record._queue_apply_records()
            except Exception as ex:
                result["failed"] += 1
                result["errors"].append(
                    {
                        "index": index,
                        "model_name": row.get("model_name"),
                        "rec_id": row.get("rec_id"),
                        "error": str(ex),
                    }
                )

        branch.write({"last_upload_at": fields.Datetime.now()})
        return result

    @api.model
    def _force_next_id(self, model, target_id):
        self.env.cr.execute(
            "SELECT pg_get_serial_sequence(%s, 'id')", (model._table,)
        )
        row = self.env.cr.fetchone()
        sequence_name = row and row[0]
        if not sequence_name:
            raise ValueError(
                _("No sequence found for model %(model)s.")
                % {"model": model._name}
            )
        self.env.cr.execute(
            "SELECT setval(%s::regclass, %s, false)",
            (sequence_name, int(target_id)),
        )

    @api.model
    def _upload_apply_feeder_identity_key(self):
        return "ab_odoo_sync_mapping_upload_apply_feeder"

    @api.model
    def cron_queue_upload_apply_records(self):
        self.sudo().with_delay(
            identity_key=self._upload_apply_feeder_identity_key(),
            description=_("Queue reporting upload records for apply"),
            max_retries=0,
        ).job_queue_upload_apply_records()
        return {"status": "queued"}

    @api.model
    def job_queue_upload_apply_records(self):
        batch_size = self.get_batch_size()
        queued_count = 0
        upload_model = self.env["ab_odoo_sync_upload_record"].sudo()
        profiles = self.env["ab_odoo_sync_apply_profile"].sudo().search(
            [
                ("active", "=", True),
                ("auto_apply", "=", True),
                ("apply_mode", "in", ["mirror_sync", "business_model"]),
            ],
            order="sequence, id",
        )
        for profile in profiles:
            remaining = batch_size - queued_count
            if remaining <= 0:
                break
            records = upload_model.search(
                [
                    ("model_name", "=", profile.source_model_name),
                    (
                        "status",
                        "in",
                        ["pending_mapping", "raw_only", "pending", "failed"],
                    ),
                    ("active", "=", True),
                ],
                order="source_revision, id",
                limit=remaining,
            )
            for record in records:
                if (
                    record.apply_profile_id != profile
                    or record.target_model_name != profile.target_model_name
                    or record.status in {"pending_mapping", "raw_only"}
                ):
                    record._set_profile_handling(profile)
            queued_count += records._queue_apply_records()

        result = {
            "status": "ok",
            "queued": queued_count,
            "batch_size": batch_size,
        }
        _logger.info("AB Odoo Sync mapping feeder result: %s", result)
        return result
