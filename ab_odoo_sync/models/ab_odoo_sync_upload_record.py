import logging
import re
import uuid

from odoo import api, fields, models
from odoo.addons.integration_queue_job.exception import RetryableJobError
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

_MODEL_NAME_RE = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)*$")
_SKIPPED_SYSTEM_FIELDS = {
    "id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "__last_update",
    "display_name",
}
_RELATIONAL_FIELD_TYPES = {"many2one", "one2many", "many2many"}
_SYNC_PLACEHOLDER_META_FIELDS = {
    "db_serial",
    "rec_id",
    "payload_json",
    "source_revision",
    "event_uuid",
    "source_operation",
    "source_write_date",
    "synced_at",
    "active",
}


class AbOdooSyncUploadRecord(models.Model):
    _name = "ab_odoo_sync_upload_record"
    _description = "AB Odoo Sync Upload Record"
    _order = "received_at desc, id desc"

    db_serial = fields.Integer(string="DB Serial", required=True, index=True, readonly=True)
    event_uuid = fields.Char(string="Event UUID", required=True, index=True, readonly=True)
    model_name = fields.Char(string="Source Model", required=True, index=True, readonly=True)
    rec_id = fields.Integer(string="Source Record ID", required=True, index=True, readonly=True)
    source_revision = fields.Integer(string="Source Revision", required=True, index=True, readonly=True)
    source_operation = fields.Selection(
        string="Source Operation",
        selection=[("upsert", "Upsert"), ("archive", "Archive")],
        required=True,
        readonly=True,
        index=True,
    )
    source_write_date = fields.Datetime(string="Source Write Date", readonly=True, index=True)
    target_model_name = fields.Char(string="Target Model", required=True, index=True, readonly=True)
    apply_profile_id = fields.Many2one(
        "ab_odoo_sync_apply_profile",
        string="Apply Profile",
        readonly=True,
        index=True,
        ondelete="set null",
    )
    payload_json = fields.Json(string="Payload", default=dict, readonly=True)
    status = fields.Selection(
        string="Status",
        selection=[
            ("pending_mapping", "Pending Mapping"),
            ("pending", "Pending"),
            ("queued", "Queued"),
            ("applied", "Applied"),
            ("failed", "Failed"),
            ("raw_only", "Raw Only"),
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
    _uniq_upload_event_uuid = models.Constraint(
        "UNIQUE(event_uuid)",
        "Uploaded event UUID must be unique.",
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
            raise ValueError(
                _(
                    "model_name must contain lowercase letters, numbers, underscores, "
                    "and dots between model name segments only."
                )
            )
        return model_name

    @api.model
    def _normalize_payload_value(self, target_model, field_name, value):
        field = target_model._fields.get(field_name)
        if field and field.type == "many2one" and isinstance(value, (list, tuple)):
            return value[0] if value else False
        return value

    @api.model
    def upsert_from_upload(
        self,
        db_serial,
        model_name,
        rec_id,
        payload,
        event_uuid=None,
        source_revision=1,
        source_operation="upsert",
        source_write_date=None,
    ):
        model_name = self.validate_source_model_name(model_name)
        rec_id = int(rec_id or 0)
        if rec_id <= 0:
            raise ValueError(_("rec_id must be a positive integer."))
        if not isinstance(payload, dict):
            raise ValueError(_("payload must be a JSON object."))

        event_uuid = str(event_uuid or uuid.uuid4())
        try:
            uuid.UUID(event_uuid)
        except (TypeError, ValueError, AttributeError) as ex:
            raise ValueError(_("event_uuid must be a valid UUID.")) from ex
        source_revision = int(source_revision or 0)
        if source_revision <= 0:
            raise ValueError(_("source_revision must be a positive integer."))
        if source_operation not in {"upsert", "archive"}:
            raise ValueError(_("source_operation must be upsert or archive."))

        profile = self.env["ab_odoo_sync_apply_profile"].sudo().get_for_source(model_name)
        target_model_name = (
            profile.target_model_name
            if profile and profile.target_model_name
            else self.target_model_from_source(model_name)
        )
        status = "pending"
        if not profile:
            status = "pending_mapping"
        elif profile.apply_mode == "raw_only":
            status = "raw_only"
        elif profile.apply_mode == "ignore":
            status = "not_sync"
        vals = {
            "event_uuid": event_uuid,
            "payload_json": payload,
            "source_revision": source_revision,
            "source_operation": source_operation,
            "source_write_date": source_write_date or False,
            "target_model_name": target_model_name,
            "apply_profile_id": profile.id if profile else False,
            "status": status,
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
            if source_revision <= record.source_revision:
                return record, False
            record.write(vals)
            return record, True

        vals.update(
            {
                "db_serial": db_serial,
                "model_name": model_name,
                "rec_id": rec_id,
            }
        )
        return self.sudo().create(vals), True

    def _set_profile_handling(self, profile):
        self.ensure_one()
        vals = {
            "apply_profile_id": profile.id,
            "target_model_name": profile.target_model_name or self.target_model_from_source(self.model_name),
            "error_message": False,
        }
        if profile.apply_mode == "raw_only":
            vals.update({"status": "raw_only", "applied_at": fields.Datetime.now()})
        elif profile.apply_mode == "ignore":
            vals.update({"status": "not_sync", "applied_at": fields.Datetime.now()})
        elif self.status in {"pending_mapping", "raw_only", "not_sync"}:
            vals["status"] = "pending"
        self.sudo().write(vals)

    def _queue_identity_key(self):
        self.ensure_one()
        return f"ab_odoo_sync_upload_record_apply:{self.id}"

    def _queue_apply_records(self):
        queued_count = 0
        now = fields.Datetime.now()
        for record in self.sudo().exists():
            profile = record.apply_profile_id
            if not profile:
                record.write(
                    {
                        "status": "pending_mapping",
                        "error_message": False,
                    }
                )
                continue
            if profile.apply_mode in {"raw_only", "ignore"}:
                record._set_profile_handling(profile)
                continue
            if record.status in {"applied", "not_sync", "raw_only"}:
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
                max_retries=0,
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
        records = self.filtered(lambda rec: rec.status in {"pending_mapping", "pending", "queued", "failed", "raw_only"})
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
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
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

    def _payload_fields(self):
        self.ensure_one()
        payload = self.payload_json or {}
        if not isinstance(payload, dict):
            raise ValueError(_("payload must be a JSON object."))
        nested_fields = payload.get("fields")
        if nested_fields is not None:
            if not isinstance(nested_fields, dict):
                raise ValueError(_("payload fields must be a JSON object."))
            return nested_fields
        return payload

    def _resolve_relation_reference(self, target_field, reference, mapping):
        self.ensure_one()
        if not reference:
            if mapping.required:
                raise ValueError(
                    _("Required relation %(field)s is empty.")
                    % {"field": mapping.source_field_name}
                )
            return False
        if not isinstance(reference, dict):
            raise ValueError(
                _("Relation payload for %(field)s must be an object.")
                % {"field": mapping.source_field_name}
            )

        relation_model = self.env[target_field.comodel_name].with_context(
            active_test=False,
            skip_ab_odoo_sync_event=True,
        ).sudo()
        if mapping.mapping_type in {"sync_many2one", "sync_many2many"}:
            source_rec_id = int(reference.get("id") or 0)
            if source_rec_id <= 0:
                raise ValueError(
                    _("Relation %(field)s is missing its source record ID.")
                    % {"field": mapping.source_field_name}
                )
            if {"db_serial", "rec_id"}.issubset(relation_model._fields):
                relation = relation_model.search(
                    [
                        ("db_serial", "=", self.db_serial),
                        ("rec_id", "=", source_rec_id),
                    ],
                    limit=1,
                )
                if not relation:
                    relation = self._create_missing_sync_relation(
                        relation_model,
                        source_rec_id,
                        reference,
                        mapping,
                    )
            else:
                source_relation_model = reference.get("model") or target_field.comodel_name
                rules = self.env["ab_odoo_sync_rules"].sudo()
                if source_relation_model == rules.user_source_model():
                    target_model_name = rules.user_mirror_model()
                else:
                    target_model_name = target_field.comodel_name
                if rules.is_id_only_relation_model(source_relation_model):
                    reference = {
                        "model": source_relation_model,
                        "id": source_rec_id,
                    }
                profile = self.apply_profile_id
                relation = self.env["ab_odoo_sync_identity"].sudo().get_or_create_business_record(
                    db_serial=self.db_serial,
                    source_model_name=source_relation_model,
                    source_rec_id=source_rec_id,
                    target_model_name=target_model_name,
                    reference=reference,
                    upload_record=self,
                    create_placeholder=profile.allow_placeholder_creation if profile else True,
                )
        else:
            identity_values = reference.get("values") or {}
            source_key_value = identity_values.get(mapping.relation_source_key)
            if source_key_value in (None, False, ""):
                raise ValueError(
                    _("Relation %(field)s is missing stable key %(key)s.")
                    % {
                        "field": mapping.source_field_name,
                        "key": mapping.relation_source_key,
                    }
                )
            relation = relation_model.search(
                [(mapping.relation_target_key, "=", source_key_value)],
                limit=2,
            )
            if len(relation) > 1:
                raise ValueError(
                    _("Stable relation %(field)s matched more than one MAIN record.")
                    % {"field": mapping.source_field_name}
                )

        if not relation:
            raise ValueError(
                _("Could not resolve relation %(field)s for source record %(record)s.")
                % {
                    "field": mapping.source_field_name,
                    "record": self.rec_id,
                }
            )
        return relation.id

    def _create_missing_sync_relation(self, relation_model, source_rec_id, reference, mapping):
        self.ensure_one()
        if not {"db_serial", "rec_id"}.issubset(relation_model._fields):
            raise ValueError(
                _(
                    "Sync relation %(field)s cannot create placeholder records "
                    "because %(model)s has no sync identity fields."
                )
                % {
                    "field": mapping.source_field_name,
                    "model": relation_model._name,
                }
            )

        vals = self._prepare_sync_relation_placeholder_vals(
            relation_model,
            source_rec_id,
            reference,
        )
        try:
            with self.env.cr.savepoint():
                return relation_model.create(vals)
        except Exception:
            relation = relation_model.search(
                [
                    ("db_serial", "=", self.db_serial),
                    ("rec_id", "=", source_rec_id),
                ],
                limit=1,
            )
            if relation:
                return relation
            raise

    def _prepare_sync_relation_placeholder_vals(
        self,
        relation_model,
        source_rec_id,
        reference,
    ):
        self.ensure_one()
        vals = {
            "db_serial": self.db_serial,
            "rec_id": source_rec_id,
        }
        if "payload_json" in relation_model._fields:
            vals["payload_json"] = {
                "placeholder": True,
                "relation": reference,
            }
        if "source_revision" in relation_model._fields:
            vals["source_revision"] = 0
        source_operation_field = relation_model._fields.get("source_operation")
        if source_operation_field and self._selection_field_has_value(
            source_operation_field,
            "upsert",
        ):
            vals["source_operation"] = "upsert"
        if "synced_at" in relation_model._fields:
            vals["synced_at"] = fields.Datetime.now()
        if "active" in relation_model._fields:
            vals["active"] = True

        identity_values = reference.get("values") or {}
        for field_name, value in identity_values.items():
            field = relation_model._fields.get(field_name)
            if (
                field_name not in vals
                and field
                and self._can_write_placeholder_field(field)
            ):
                vals[field_name] = value

        display_name = reference.get("display_name")
        name_field = relation_model._fields.get("name")
        if (
            display_name
            and "name" not in vals
            and name_field
            and self._can_write_placeholder_field(name_field)
        ):
            vals["name"] = display_name

        required_fields = [
            field_name
            for field_name, field in relation_model._fields.items()
            if (
                field.required
                and field_name not in vals
                and field_name not in _SYNC_PLACEHOLDER_META_FIELDS
            )
        ]
        defaults = relation_model.default_get(required_fields) if required_fields else {}
        for field_name in required_fields:
            if (
                field_name in defaults
                and defaults[field_name] not in (None, False, "")
            ):
                vals[field_name] = defaults[field_name]
                continue

            field = relation_model._fields[field_name]
            fallback = self._placeholder_fallback_value(
                field,
                display_name,
                source_rec_id,
            )
            if fallback is not None:
                vals[field_name] = fallback

        return vals

    @api.model
    def _can_write_placeholder_field(self, field):
        return (
            field.store
            and field.type not in _RELATIONAL_FIELD_TYPES
            and not (field.compute and not field.inverse)
        )

    @api.model
    def _placeholder_fallback_value(self, field, display_name, source_rec_id):
        if not self._can_write_placeholder_field(field):
            return None
        if field.type in {"char", "text", "html"}:
            return display_name or "SYNC-%s" % source_rec_id
        if field.type == "selection":
            selection = field.selection
            if isinstance(selection, (list, tuple)) and selection:
                return selection[0][0]
            return None
        if field.type in {"integer", "float", "monetary"}:
            return 0
        if field.type == "boolean":
            return False
        if field.type == "json":
            return {}
        if field.type == "date":
            return fields.Date.context_today(self)
        if field.type == "datetime":
            return fields.Datetime.now()
        return None

    @api.model
    def _selection_field_has_value(self, field, value):
        if field.type != "selection":
            return False
        selection = getattr(field, "selection", None)
        if not isinstance(selection, (list, tuple)):
            return False
        return value in {item[0] for item in selection}

    def _prepare_target_vals(self, target_model):
        self.ensure_one()
        profile = self.apply_profile_id
        if not profile or not profile.active:
            raise ValueError(
                _("No active apply profile exists for source model %(model)s.")
                % {"model": self.model_name}
            )
        if profile.apply_mode == "raw_only":
            return {}, []
        if profile.apply_mode == "ignore":
            return {}, []
        if profile.target_model_name != self.target_model_name:
            raise ValueError(_("Upload target does not match its active apply profile."))
        if profile.apply_mode == "mirror_sync" and (
            "db_serial" not in target_model._fields or "rec_id" not in target_model._fields
        ):
            raise ValueError(
                _("Target sync model %(model)s must define db_serial and rec_id fields.")
                % {"model": self.target_model_name}
            )

        payload_fields = self._payload_fields()

        vals = {}
        if profile.apply_mode == "mirror_sync":
            vals.update(
                {
                    "db_serial": self.db_serial,
                    "rec_id": self.rec_id,
                }
            )
        meta_vals = {
            "payload_json": self.payload_json or {},
            "source_revision": self.source_revision,
            "event_uuid": self.event_uuid,
            "source_operation": self.source_operation,
            "source_write_date": self.source_write_date,
            "synced_at": fields.Datetime.now(),
        }
        for field_name, value in meta_vals.items():
            if profile.apply_mode == "mirror_sync" and field_name in target_model._fields:
                vals[field_name] = value

        active_mappings = profile.mapping_ids.filtered(
            lambda mapping: mapping.sync_enabled and mapping.mapping_type != "ignore"
        ).sorted("sequence")
        if self.source_operation == "upsert" and not active_mappings:
            raise ValueError(
                _("Apply profile %(profile)s has no active field mappings.")
                % {"profile": profile.name}
            )

        mapped_source_fields = set()
        for mapping in active_mappings:
            mapped_source_fields.add(mapping.source_field_name)
            if mapping.source_field_name not in payload_fields:
                if mapping.required:
                    raise ValueError(
                        _("Required source field %(field)s is missing from the payload.")
                        % {"field": mapping.source_field_name}
                    )
                continue

            value = payload_fields[mapping.source_field_name]
            target_field = target_model._fields[mapping.target_field_name]
            if mapping.mapping_type == "direct":
                if target_field.type in {"many2one", "one2many", "many2many"}:
                    raise ValueError(
                        _("Relational target field %(field)s requires a relation mapping type.")
                        % {"field": mapping.target_field_name}
                    )
                vals[mapping.target_field_name] = value
            elif mapping.mapping_type in {"sync_many2one", "stable_many2one"}:
                vals[mapping.target_field_name] = self._resolve_relation_reference(
                    target_field,
                    value,
                    mapping,
                )
            elif mapping.mapping_type in {"sync_many2many", "stable_many2many"}:
                if not isinstance(value, list):
                    raise ValueError(
                        _("Relation payload for %(field)s must be a list.")
                        % {"field": mapping.source_field_name}
                    )
                relation_ids = [
                    self._resolve_relation_reference(target_field, reference, mapping)
                    for reference in value
                ]
                vals[mapping.target_field_name] = [(6, 0, relation_ids)]

        if self.source_operation == "archive":
            if "active" not in target_model._fields:
                raise ValueError(
                    _("Target sync model %(model)s cannot archive records because it has no active field.")
                    % {"model": self.target_model_name}
                )
            vals["active"] = False

        skipped_fields = sorted(set(payload_fields) - mapped_source_fields)

        return vals, skipped_fields

    def _apply_to_mirror_model(self, target_model, vals):
        self.ensure_one()
        existing = target_model.search(
            [
                ("db_serial", "=", self.db_serial),
                ("rec_id", "=", self.rec_id),
            ],
            limit=1,
        )
        if existing:
            existing.write(vals)
            return existing
        return target_model.create(vals)

    def _apply_to_business_model(self, target_model, vals):
        self.ensure_one()
        identity_model = self.env["ab_odoo_sync_identity"].sudo()
        target_res_id = self.rec_id
        existing = target_model.browse(target_res_id)
        if self.source_operation == "archive":
            if existing.exists():
                existing.write(vals)
                identity_model.mark_resolved(self, target_model._name, target_res_id)
            return existing

        if existing.exists():
            existing.write(vals)
        else:
            payload_fields = self._payload_fields()
            create_vals = identity_model._prepare_placeholder_vals(
                target_model,
                target_res_id,
                {
                    "display_name": payload_fields.get("display_name") or payload_fields.get("name"),
                    "values": {},
                },
            )
            create_vals.update(vals)
            with self.env.cr.savepoint():
                self.env["ab_odoo_sync_service"].sudo()._force_next_id(target_model, target_res_id)
                existing = target_model.create(create_vals)
        identity_model.mark_resolved(self, target_model._name, target_res_id)
        return existing

    def job_apply_to_target(self):
        for record in self.sudo().exists():
            record._apply_to_target()

    def _apply_to_target(self):
        self.ensure_one()
        if self.status == "not_sync":
            return

        try:
            with self.env.cr.savepoint():
                profile = self.apply_profile_id
                if not profile:
                    self.write({"status": "pending_mapping", "error_message": False})
                    return
                if profile.apply_mode in {"raw_only", "ignore"}:
                    self._set_profile_handling(profile)
                    return
                target_model = self._get_target_model()
                vals, skipped_fields = self._prepare_target_vals(target_model)
                if profile.apply_mode == "business_model":
                    self._apply_to_business_model(target_model, vals)
                else:
                    self._apply_to_mirror_model(target_model, vals)
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
            if self.env.context.get("job_uuid"):
                raise RetryableJobError(str(ex)) from ex
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
