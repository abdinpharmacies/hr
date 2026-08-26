import base64
import datetime
import hashlib
import json
import logging
import urllib.error
import urllib.request

from odoo import api, fields, models
from odoo.tools import config
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)
_SENSITIVE_SNAPSHOT_FIELDS = {"password"}


class AbOdooSyncUploadService(models.AbstractModel):
    _inherit = "ab_odoo_sync_service"

    @api.model
    def get_db_serial(self):
        raw = config.get("db_serial", 0) or 0
        return self.parse_positive_int(raw, "db_serial")

    @api.model
    def _ensure_ascii_transport_config(self, config_key, value):
        try:
            (value or "").encode("ascii")
        except UnicodeEncodeError as ex:
            raise ValueError(
                _(
                    "Config %(config)s contains non-ASCII character %(character)s. "
                    "Use ASCII only for sync transport settings."
                )
                % {
                    "config": config_key,
                    "character": ex.object[ex.start:ex.end],
                }
            ) from ex

    @api.model
    def _jsonable_snapshot_value(self, value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime.datetime):
            return fields.Datetime.to_string(value)
        if isinstance(value, datetime.date):
            return fields.Date.to_string(value)
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("ascii")
        if isinstance(value, dict):
            return {
                str(key): self._jsonable_snapshot_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [self._jsonable_snapshot_value(item) for item in value]
        if hasattr(value, "ids"):
            return list(value.ids)
        return str(value)

    @api.model
    def _serialize_relation_ref(self, record):
        record.ensure_one()
        if self.env["ab_odoo_sync_rules"].sudo().is_id_only_relation_model(record._name):
            return {"model": record._name, "id": record.id}

        identity = {}
        for field_name in (
            "eplus_serial",
            "code",
            "barcode",
            "reference",
            "external_id",
            "name",
        ):
            field = record._fields.get(field_name)
            if (
                not field
                or not field.store
                or field.type in {"many2one", "one2many", "many2many"}
            ):
                continue
            identity[field_name] = self._jsonable_snapshot_value(record[field_name])
        return {
            "model": record._name,
            "id": record.id,
            "display_name": record.display_name,
            "values": identity,
        }

    @api.model
    def serialize_stored_record(self, record):
        record.ensure_one()
        payload_fields = {}
        field_types = {}
        for field_name, field in sorted(record._fields.items()):
            if field_name in _SENSITIVE_SNAPSHOT_FIELDS or not field.store:
                continue
            value = record[field_name]
            field_types[field_name] = field.type
            if field.type == "many2one":
                payload_fields[field_name] = (
                    self._serialize_relation_ref(value) if value else False
                )
            elif field.type in {"one2many", "many2many"}:
                payload_fields[field_name] = [
                    self._serialize_relation_ref(related) for related in value
                ]
            else:
                payload_fields[field_name] = self._jsonable_snapshot_value(value)
        return {
            "schema_version": 1,
            "model": record._name,
            "id": record.id,
            "fields": payload_fields,
            "field_types": field_types,
        }

    @api.model
    def _get_upload_configuration_error(self):
        try:
            self.get_db_serial()
        except ValueError as ex:
            return str(ex)

        required = {
            "ab_odoo_sync.main_url": _("Missing MAIN URL config: ab_odoo_sync.main_url"),
            "ab_odoo_sync.main_database": _(
                "Missing MAIN database config: ab_odoo_sync.main_database"
            ),
            "ab_odoo_sync.api_key": _("Missing API key config: ab_odoo_sync.api_key"),
        }
        for key, message in required.items():
            if not (self._icp().get_param(key) or "").strip():
                return message
        return False

    @api.model
    def _main_api_call(self, path, payload):
        main_url = (
            self._icp().get_param("ab_odoo_sync.main_url") or ""
        ).strip().rstrip("/")
        main_database = (
            self._icp().get_param("ab_odoo_sync.main_database") or ""
        ).strip()
        api_key = (self._icp().get_param("ab_odoo_sync.api_key") or "").strip()
        for key, value in (
            ("ab_odoo_sync.main_url", main_url),
            ("ab_odoo_sync.main_database", main_database),
            ("ab_odoo_sync.api_key", api_key),
        ):
            self._ensure_ascii_transport_config(key, value)

        request = urllib.request.Request(
            url=f"{main_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        request.add_header("Content-Type", "application/json")
        request.add_header("X-AB-Sync-Key", api_key)
        request.add_header("X-Odoo-Database", main_database)

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except UnicodeEncodeError as ex:
            raise ValueError(
                _(
                    "MAIN API request contains non-ASCII characters in an HTTP URL "
                    "or header."
                )
            ) from ex
        except urllib.error.HTTPError as ex:
            error_body = ex.read().decode("utf-8", errors="ignore")
            raise ValueError(f"MAIN API HTTP {ex.code}: {error_body}") from ex
        except urllib.error.URLError as ex:
            raise ValueError(f"MAIN API connection error: {ex}") from ex

        try:
            result = json.loads(body or "{}")
        except json.JSONDecodeError as ex:
            raise ValueError(_("MAIN API returned an invalid JSON response.")) from ex
        if not result.get("ok"):
            raise ValueError(result.get("error") or _("MAIN API returned failure."))
        return result

    @api.model
    def push_upload_records(self, records):
        if not isinstance(records, list):
            raise ValueError(_("records must be a JSON array."))
        configuration_error = self._get_upload_configuration_error()
        if configuration_error:
            raise ValueError(configuration_error)
        return self._main_api_call(
            "/ab_odoo_sync/upload",
            {
                "db_serial": self.get_db_serial(),
                "records": records,
            },
        )

    @api.model
    def send_branch_upload_batch(self, outbox_records=None):
        configuration_error = self._get_upload_configuration_error()
        if configuration_error:
            return {
                "status": "skipped",
                "sent": 0,
                "failed": 0,
                "reason": configuration_error,
            }

        Outbox = self.env["ab_odoo_sync_outbox"].sudo()
        if outbox_records is None:
            outbox_records = Outbox.search(
                [
                    ("status", "in", ["pending", "failed"]),
                    ("active", "=", True),
                ],
                order="id",
                limit=self.get_batch_size(),
            )
        else:
            outbox_records = outbox_records.sudo().filtered(
                lambda record: record.status in {"pending", "failed"} and record.active
            ).sorted("id")

        if not outbox_records:
            return {"status": "ok", "sent": 0, "failed": 0}

        rows = [
            {
                "event_uuid": record.event_uuid,
                "model_name": record.model_name,
                "rec_id": record.rec_id,
                "source_revision": record.source_revision,
                "operation": record.operation,
                "source_write_date": (
                    fields.Datetime.to_string(record.source_write_date)
                    if record.source_write_date
                    else False
                ),
                "payload": record.payload_json or {},
            }
            for record in outbox_records
        ]

        try:
            response = self.push_upload_records(rows)
        except Exception as ex:
            for record in outbox_records:
                record.write(
                    {
                        "status": "failed",
                        "attempt_count": record.attempt_count + 1,
                        "last_error": str(ex),
                    }
                )
            return {
                "status": "failed",
                "sent": 0,
                "failed": len(outbox_records),
                "error": str(ex),
            }

        errors_by_index = {
            int(error.get("index")): error.get("error") or _("Unknown upload error")
            for error in response.get("errors", [])
            if isinstance(error, dict) and str(error.get("index", "")).isdigit()
        }
        now = fields.Datetime.now()
        sent = 0
        failed = 0
        for index, record in enumerate(outbox_records):
            values = {"attempt_count": record.attempt_count + 1}
            if index in errors_by_index:
                values.update(
                    {
                        "status": "failed",
                        "last_error": errors_by_index[index],
                    }
                )
                failed += 1
            else:
                values.update(
                    {
                        "status": "sent",
                        "last_error": False,
                        "sent_at": now,
                    }
                )
                sent += 1
            record.write(values)
        return {
            "status": "ok" if not failed else "partial",
            "sent": sent,
            "failed": failed,
        }

    @api.model
    def _branch_upload_sender_identity_key(self, outbox_records=None):
        if not outbox_records:
            return "ab_odoo_sync_branch_upload_sender"
        raw_ids = ",".join(str(record_id) for record_id in sorted(outbox_records.ids))
        digest = hashlib.sha1(raw_ids.encode("ascii")).hexdigest()
        return f"ab_odoo_sync_branch_upload_sender:{digest}"

    @api.model
    def queue_branch_upload_batch(self, outbox_records=None):
        configuration_error = self._get_upload_configuration_error()
        if configuration_error:
            return {"status": "skipped", "queued": 0, "reason": configuration_error}

        Outbox = self.env["ab_odoo_sync_outbox"].sudo()
        if outbox_records is None:
            outbox_records = Outbox.search(
                [
                    ("status", "in", ["pending", "failed"]),
                    ("active", "=", True),
                ],
                order="id",
                limit=self.get_batch_size(),
            )
            if not outbox_records:
                return {"status": "ok", "queued": 0}
            self.sudo().with_delay(
                identity_key=self._branch_upload_sender_identity_key(),
                description=_("Send branch upload outbox events to MAIN"),
                max_retries=0,
            ).job_send_branch_upload_batch()
            return {"status": "queued", "queued": len(outbox_records)}

        outbox_records = outbox_records.sudo().filtered(
            lambda record: record.status in {"pending", "failed"} and record.active
        ).sorted("id")
        if not outbox_records:
            return {"status": "ok", "queued": 0}

        self.sudo().with_delay(
            identity_key=self._branch_upload_sender_identity_key(outbox_records),
            description=_("Send branch upload outbox events to MAIN"),
            max_retries=0,
        ).job_send_branch_upload_batch(outbox_records.ids)
        return {"status": "queued", "queued": len(outbox_records)}

    @api.model
    def job_send_branch_upload_batch(self, outbox_ids=None):
        outbox_records = (
            self.env["ab_odoo_sync_outbox"].sudo().browse(outbox_ids)
            if outbox_ids
            else None
        )
        result = self.send_branch_upload_batch(outbox_records)
        _logger.info("AB Odoo Sync upload sender result: %s", result)
        return result

    @api.model
    def cron_send_branch_uploads(self):
        result = self.queue_branch_upload_batch()
        _logger.info("AB Odoo Sync upload queue result: %s", result)
        return result

    @api.model
    def test_upload_connection(self):
        configuration_error = self._get_upload_configuration_error()
        if configuration_error:
            return {"status": "skipped", "reason": configuration_error}

        db_serial = self.get_db_serial()
        health = self._main_api_call(
            "/ab_odoo_sync/health",
            {"db_serial": db_serial},
        )
        push = self.push_upload_records([])
        return {
            "status": "ok",
            "db_serial": db_serial,
            "main_database": health.get("database"),
            "push_accepted": push.get("accepted", 0),
            "capabilities": health.get("capabilities") or {},
        }

    @api.model
    def action_test_upload_connection(self):
        try:
            result = self.test_upload_connection()
        except Exception as ex:
            _logger.exception("AB Odoo Sync upload connection test failed")
            return self._connection_notification(str(ex), "danger", True)

        if result.get("status") != "ok":
            return self._connection_notification(
                result.get("reason") or _("Connection test was skipped."),
                "warning",
                True,
            )
        return self._connection_notification(
            _(
                "Connected to report database %(database)s. Upload check passed "
                "for DB serial %(db_serial)s."
            )
            % {
                "database": result["main_database"],
                "db_serial": result["db_serial"],
            },
            "success",
            False,
        )

    @api.model
    def _connection_notification(self, message, notification_type, sticky):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Odoo Sync Upload Connection"),
                "message": message,
                "type": notification_type,
                "sticky": sticky,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            },
        }
