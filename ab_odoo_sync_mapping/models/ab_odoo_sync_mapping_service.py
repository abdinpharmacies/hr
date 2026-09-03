import logging

from odoo import api, fields, models
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)
_APPLY_CAPABLE_MODES = {"mirror_sync", "business_model"}
_FEEDER_UPLOAD_STATUSES = ["pending_mapping", "raw_only", "pending", "failed"]


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
                profile, pending_mapping_error = self._ensure_same_name_passive_profile(
                    model_name,
                    payload=payload_json,
                )
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
                if (
                    pending_mapping_error
                    and upload_record.status == "pending_mapping"
                    and upload_record.error_message != pending_mapping_error
                ):
                    upload_record.write({"error_message": pending_mapping_error})
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
    def _ensure_same_name_passive_profile(self, model_name, payload=False):
        Profile = self.env["ab_odoo_sync_apply_profile"].sudo()
        existing = Profile.get_for_source(model_name)
        if existing:
            if existing.auto_generated:
                existing._load_matching_fields(
                    default_sync_enabled=True,
                    stored_only=True,
                    payload=payload,
                )
            return existing, False

        inactive = Profile.with_context(active_test=False).search(
            [("source_model_name", "=", model_name)],
            limit=1,
        )
        if inactive:
            return False, _(
                "Apply profile %(profile)s is inactive; activate it or configure another handling mode."
            ) % {"profile": inactive.display_name}

        pending_error = self._same_name_passive_profile_error(model_name)
        if pending_error:
            return False, pending_error

        profile_vals = {
            "name": model_name,
            "source_model_name": model_name,
            "target_model_name": model_name,
            "apply_mode": "mirror_sync",
            "auto_apply": True,
            "allow_placeholder_creation": True,
            "auto_generated": True,
            "active": True,
        }
        try:
            with self.env.cr.savepoint():
                profile = Profile.create(profile_vals)
                profile._load_matching_fields(
                    default_sync_enabled=True,
                    stored_only=True,
                    payload=payload,
                )
                self._refresh_uploads_for_profile(profile)
        except Exception as ex:
            _logger.exception(
                "Could not auto-create same-name passive sync profile for %s",
                model_name,
            )
            return False, _(
                "Could not auto-create same-name passive apply profile for %(model)s: %(error)s"
            ) % {"model": model_name, "error": str(ex)}
        return profile, False

    @api.model
    def _same_name_passive_profile_error(self, model_name):
        rules = self.env["ab_odoo_sync_rules"].sudo()
        Profile = self.env["ab_odoo_sync_apply_profile"].sudo()
        if rules.is_upload_source_forbidden(model_name):
            return _(
                "Source model %(model)s is protected by sync-rules.md and cannot be uploaded from branches."
            ) % {"model": model_name}
        if rules.is_never_mirror_model(model_name):
            return _(
                "Source model %(model)s is report-owned; create a Business Model apply profile instead of a Mirror Sync Model profile."
            ) % {"model": model_name}
        if model_name not in self.env:
            return _(
                "Report model %(model)s is not installed; install the passive report model or create an explicit apply profile."
            ) % {"model": model_name}

        target_model = self.env[model_name]
        missing = Profile._missing_mirror_sync_fields(target_model)
        if missing:
            return _(
                "Report model %(model)s cannot be auto-mapped because it is missing passive sync fields: %(fields)s"
            ) % {
                "model": model_name,
                "fields": ", ".join(sorted(missing)),
            }
        if not Profile._target_has_unique_identity_constraint(target_model):
            return _(
                "Report model %(model)s cannot be auto-mapped because it lacks a unique constraint on db_serial and rec_id."
            ) % {"model": model_name}
        return False

    @api.model
    def _refresh_uploads_for_profile(self, profile):
        records = self.env["ab_odoo_sync_upload_record"].sudo().search(
            [
                ("model_name", "=", profile.source_model_name),
                ("status", "in", _FEEDER_UPLOAD_STATUSES),
                ("active", "=", True),
            ]
        )
        for record in records:
            if (
                record.apply_profile_id != profile
                or record.target_model_name != profile.target_model_name
                or record.status in {"pending_mapping", "raw_only"}
            ):
                record._set_profile_handling(profile)
        return len(records)

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
    def _upload_apply_feeder_identity_key(self, profile, manual=False):
        profile.ensure_one()
        mode = "manual" if manual else "auto"
        return "ab_odoo_sync_mapping_upload_apply_feeder:%s:%s" % (mode, profile.id)

    @api.model
    def _can_queue_upload_apply_feeder(self, profile, manual=False):
        profile.ensure_one()
        return (
            profile.active
            and profile.apply_mode in _APPLY_CAPABLE_MODES
            and (manual or profile.auto_apply)
        )

    @api.model
    def queue_upload_apply_feeder(self, profile, manual=False):
        profile.ensure_one()
        profile = profile.sudo()
        if not self._can_queue_upload_apply_feeder(profile, manual=manual):
            return 0
        self.sudo().with_delay(
            identity_key=self._upload_apply_feeder_identity_key(profile, manual=manual),
            description=_("Queue reporting upload records for %(profile)s")
            % {"profile": profile.display_name},
            max_retries=0,
        ).job_queue_upload_apply_records(profile.id, manual=manual)
        return 1

    @api.model
    def cron_queue_upload_apply_records(self):
        pending_profiles = {}
        pending_uploads = self.env["ab_odoo_sync_upload_record"].sudo().search(
            [
                ("apply_profile_id", "=", False),
                ("status", "=", "pending_mapping"),
                ("active", "=", True),
            ],
            order="id",
            limit=self.get_batch_size(),
        )
        for upload in pending_uploads:
            if upload.model_name in pending_profiles:
                profile, pending_error = pending_profiles[upload.model_name]
            else:
                profile, pending_error = self._ensure_same_name_passive_profile(
                    upload.model_name,
                    payload=upload.payload_json,
                )
                pending_profiles[upload.model_name] = (profile, pending_error)
            if profile:
                upload._set_profile_handling(profile)
            elif pending_error and upload.error_message != pending_error:
                upload.write({"error_message": pending_error})

        profiles = self.env["ab_odoo_sync_apply_profile"].sudo().search(
            [
                ("active", "=", True),
                ("auto_apply", "=", True),
                ("apply_mode", "in", list(_APPLY_CAPABLE_MODES)),
            ],
            order="sequence, id",
        )
        queued = sum(self.queue_upload_apply_feeder(profile) for profile in profiles)
        return {"status": "queued", "feeders": queued}

    @api.model
    def job_queue_upload_apply_records(self, profile_id=False, manual=False):
        if not profile_id:
            return self.cron_queue_upload_apply_records()

        profile = (
            self.env["ab_odoo_sync_apply_profile"]
            .sudo()
            .browse(int(profile_id or 0))
            .exists()
        )
        if not profile:
            return {"status": "missing_profile", "queued": 0}
        if not self._can_queue_upload_apply_feeder(profile, manual=manual):
            return {"status": "skipped", "queued": 0, "profile_id": profile.id}

        batch_size = self.get_batch_size()
        upload_model = self.env["ab_odoo_sync_upload_record"].sudo()

        records = upload_model.search(
            [
                ("model_name", "=", profile.source_model_name),
                ("status", "in", _FEEDER_UPLOAD_STATUSES),
                ("active", "=", True),
            ],
            order="source_revision, id",
            limit=batch_size,
        )
        for record in records:
            if (
                record.apply_profile_id != profile
                or record.target_model_name != profile.target_model_name
                or record.status in {"pending_mapping", "raw_only"}
            ):
                record._set_profile_handling(profile)
        queued_count = records._queue_apply_records()

        remaining_count = upload_model.search_count(
            [
                ("model_name", "=", profile.source_model_name),
                ("status", "in", _FEEDER_UPLOAD_STATUSES),
                ("active", "=", True),
            ]
        )
        if remaining_count:
            self.queue_upload_apply_feeder(profile, manual=manual)

        result = {
            "status": "ok",
            "profile_id": profile.id,
            "manual": bool(manual),
            "queued": queued_count,
            "batch_size": batch_size,
            "remaining": remaining_count,
        }
        _logger.info("AB Odoo Sync mapping feeder result: %s", result)
        return result
