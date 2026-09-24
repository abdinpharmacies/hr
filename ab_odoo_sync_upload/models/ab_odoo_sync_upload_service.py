import base64
import datetime
import hashlib
import http.client
import ipaddress
import json
import logging
import ssl
import urllib.error
import urllib.request
from collections import defaultdict
from urllib.parse import urlsplit

import psycopg2

from odoo import api, fields, models
from odoo.addons.queue_job.exception import FailedJobError, RetryableJobError
from odoo.addons.queue_job.job import Job
from odoo.tools import config
from odoo.tools.translate import _

from .ab_odoo_sync_hardware import (
    normalize_hdd_serial,
    read_hdd_serial,
)
from .ab_odoo_sync_transport import ReportDeliveryError, parse_retry_after

_logger = logging.getLogger(__name__)
_SENSITIVE_SNAPSHOT_FIELDS = {"password"}
_DEFAULT_UPLOAD_CHANNEL = "root"


class AbOdooSyncUploadService(models.AbstractModel):
    _inherit = "ab_odoo_sync_service"

    @api.model
    def get_db_serial(self):
        raw = config.get("db_serial", 0) or 0
        return self.parse_positive_int(raw, "db_serial")

    @api.model
    def get_hdd_serial(self):
        configured_serial = self._icp().get_param("ab_odoo_sync.hdd_serial")
        if self.is_configured(configured_serial):
            report_url = (self._icp().get_param("ab_odoo_sync.report_url") or "").strip()
            if not self._is_loopback_report_url(report_url):
                raise ValueError(
                    _(
                        "Configured hardware serial fallback is only allowed "
                        "with loopback report URLs."
                    )
                )
            return normalize_hdd_serial(configured_serial)
        return read_hdd_serial()

    @api.model
    def _is_loopback_report_url(self, report_url):
        parsed = urlsplit(report_url)
        if parsed.scheme != "http" or not parsed.hostname:
            return False
        if parsed.hostname == "localhost":
            return True
        try:
            return ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            return False

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
            "ab_odoo_sync.report_url": _(
                "Set the report URL system parameter: ab_odoo_sync.report_url"
            ),
            "ab_odoo_sync.report_database": _(
                "Set the report database system parameter: "
                "ab_odoo_sync.report_database"
            ),
            "ab_odoo_sync.api_key": _(
                "Set the API key system parameter: ab_odoo_sync.api_key"
            ),
        }
        for key, message in required.items():
            if not self.is_configured(self._icp().get_param(key)):
                return message
        try:
            report_url = (self._icp().get_param("ab_odoo_sync.report_url") or "").strip()
            self._validate_report_url(report_url)
            self.get_hdd_serial()
        except ValueError as ex:
            return str(ex)
        return False

    @api.model
    def _validate_report_url(self, report_url):
        parsed = urlsplit(report_url)
        if not parsed.netloc:
            raise ValueError(_("Report URL must include a host."))
        if parsed.scheme == "https":
            return report_url
        if self._is_loopback_report_url(report_url):
            return report_url
        raise ValueError(
            _("Report URL must use HTTPS unless it points to a loopback development host.")
        )

    @api.model
    def _report_api_call(self, path, payload):
        report_url = (
            self._icp().get_param("ab_odoo_sync.report_url") or ""
        ).strip().rstrip("/")
        report_database = (
            self._icp().get_param("ab_odoo_sync.report_database") or ""
        ).strip()
        api_key = (self._icp().get_param("ab_odoo_sync.api_key") or "").strip()
        for key, value in (
            ("ab_odoo_sync.report_url", report_url),
            ("ab_odoo_sync.report_database", report_database),
            ("ab_odoo_sync.api_key", api_key),
        ):
            self._ensure_ascii_transport_config(key, value)
        report_url = self._validate_report_url(report_url)
        payload = dict(payload or {})
        if "hdd_serial" not in payload:
            payload["hdd_serial"] = self.get_hdd_serial()

        request = urllib.request.Request(
            url=f"{report_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
        )
        request.add_header("Content-Type", "application/json")
        request.add_header("User-Agent", "AB-Odoo-Sync/19.0")
        request.add_header("X-AB-Sync-Key", api_key)
        request.add_header("X-Odoo-Database", report_database)

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except UnicodeEncodeError as ex:
            raise ValueError(
                _(
                    "Report API request contains non-ASCII characters in an HTTP URL "
                    "or header."
                )
            ) from ex
        except urllib.error.HTTPError as ex:
            error_body = ex.read(4096).decode("utf-8", errors="replace")
            raise ReportDeliveryError(
                _("Report API HTTP %(status)s: %(error)s")
                % {"status": ex.code, "error": error_body},
                retryable=ex.code in {408, 429} or 500 <= ex.code < 600,
                retry_after=parse_retry_after(ex.headers.get("Retry-After")),
            ) from ex
        except urllib.error.URLError as ex:
            raise ReportDeliveryError(
                _("Report API connection error: %s") % ex,
                retryable=not isinstance(ex.reason, ssl.SSLCertVerificationError),
            ) from ex
        except (TimeoutError, ConnectionError, http.client.HTTPException) as ex:
            raise ReportDeliveryError(
                _("Report API connection error: %s") % ex, retryable=True,
            ) from ex

        try:
            result = json.loads(body or "{}")
        except json.JSONDecodeError as ex:
            raise ValueError(_("Report API returned an invalid JSON response.")) from ex
        if not isinstance(result, dict):
            raise ValueError(_("Report API returned an invalid JSON response."))
        if result.get("ok") is not True:
            raise ValueError(result.get("error") or _("Report API returned failure."))
        return result

    @api.model
    def push_upload_records(self, records):
        if not isinstance(records, list):
            raise ValueError(_("records must be a JSON array."))
        configuration_error = self._get_upload_configuration_error()
        if configuration_error:
            raise ValueError(configuration_error)
        return self._report_api_call(
            "/ab_odoo_sync/upload",
            {
                "db_serial": self.get_db_serial(),
                "hdd_serial": self.get_hdd_serial(),
                "records": records,
            },
        )

    @api.private
    @api.model
    def send_branch_upload_batch(self, outbox_records=None):
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
            errors_by_index = self._validate_upload_response(response, len(rows))
        except psycopg2.Error:
            # Let the queue runner handle database rollback/concurrency retries.
            raise
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
                "retryable": isinstance(ex, ReportDeliveryError) and ex.retryable,
                "retry_after": getattr(ex, "retry_after", None),
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
        result = {
            "status": "ok" if not failed else "partial",
            "sent": sent,
            "failed": failed,
        }
        if failed:
            result["error"] = _(
                "Report API rejected %(failed)s record(s): %(error)s"
            ) % {
                "failed": failed,
                "error": "; ".join(dict.fromkeys(errors_by_index.values()))[:4096],
            }
        return result

    @api.model
    def _validate_upload_response(self, response, count):
        error_message = _("Report API returned an invalid upload response.")
        if not isinstance(response, dict) or response.get("ok") is not True:
            raise ValueError(error_message)
        errors = response.get("errors")
        accepted = response.get("accepted")
        failed = response.get("failed")
        if (
            not isinstance(errors, list)
            or type(accepted) is not int
            or type(failed) is not int
            or min(accepted, failed) < 0
            or accepted + failed != count
            or failed != len(errors)
        ):
            raise ValueError(error_message)
        errors_by_index = {}
        for error in errors:
            if not isinstance(error, dict):
                raise ValueError(error_message)
            index = error.get("index")
            if type(index) is not int or not 0 <= index < count or index in errors_by_index:
                raise ValueError(error_message)
            errors_by_index[index] = str(error.get("error") or _("Unknown upload error"))
        return errors_by_index

    @api.model
    def _normalize_outbox_queue_channel(self, queue_channel):
        return queue_channel or _DEFAULT_UPLOAD_CHANNEL

    @api.model
    def _group_outbox_by_queue_channel(self, outbox_records):
        grouped = defaultdict(lambda: self.env["ab_odoo_sync_outbox"].sudo().browse())
        for outbox in outbox_records:
            grouped[self._normalize_outbox_queue_channel(outbox.queue_channel)] |= outbox
        return grouped

    @api.model
    def _branch_upload_sender_identity_key(
        self,
        outbox_records=None,
        queue_channel=None,
    ):
        if not outbox_records:
            return "ab_odoo_sync_branch_upload_sender:%s" % (
                self._normalize_outbox_queue_channel(queue_channel),
            )
        channel = self._normalize_outbox_queue_channel(queue_channel)
        raw_ids = ",".join(str(record_id) for record_id in sorted(outbox_records.ids))
        digest = hashlib.sha1(f"{channel}:{raw_ids}".encode("ascii")).hexdigest()
        return f"ab_odoo_sync_branch_upload_sender:{channel}:{digest}"

    @api.model
    def _queue_branch_upload_sender_jobs(self, outbox_records, description, retry_owned=False):
        outbox_records = outbox_records.sudo().exists().sorted("id")
        outbox_records._lock_delivery()
        outbox_records = outbox_records.filtered(
            lambda record: record.active and record.status in {"pending", "failed"}
        )
        queued = 0
        if retry_owned:
            for owner in sorted(set(outbox_records.mapped("delivery_job_uuid")) - {False}):
                owned = outbox_records.filtered(lambda record: record.delivery_job_uuid == owner)
                job = self.env["queue.job"].sudo().search([("uuid", "=", owner)], limit=1)
                if not job:
                    owned.write({"delivery_job_uuid": False})
                elif job.state in {"failed", "done", "cancelled"}:
                    job.requeue()
                    queued += len(owned)
        outbox_records = outbox_records.filtered(lambda record: not record.delivery_job_uuid)
        for queue_channel, channel_records in sorted(
            self._group_outbox_by_queue_channel(outbox_records).items()
        ):
            channel_records = channel_records.sorted("id")
            job = self.sudo().with_delay(
                identity_key=self._branch_upload_sender_identity_key(
                    channel_records,
                    queue_channel,
                ),
                description=description,
                max_retries=0,
                channel=queue_channel,
            ).job_send_branch_upload_batch(channel_records.ids)
            channel_records.write({"delivery_job_uuid": job.uuid})
            queued += len(channel_records)
        return queued

    @api.model
    def queue_branch_upload_batch(self, outbox_records=None, retry_owned=False):
        Outbox = self.env["ab_odoo_sync_outbox"].sudo()
        if outbox_records is None:
            outbox_records = Outbox.search(
                [
                    ("status", "in", ["pending", "failed"]),
                    ("active", "=", True),
                    ("delivery_job_uuid", "=", False),
                ],
                order="id",
                limit=self.get_batch_size(),
            )
            if not outbox_records:
                return {"status": "ok", "queued": 0}
            queued = self._queue_branch_upload_sender_jobs(
                outbox_records,
                _("Send branch upload outbox events to the report server"),
            )
            return {"status": "queued", "queued": queued}

        outbox_records = outbox_records.sudo().filtered(
            lambda record: record.status in {"pending", "failed"} and record.active
        ).sorted("id")
        if not outbox_records:
            return {"status": "ok", "queued": 0}

        queued = self._queue_branch_upload_sender_jobs(
            outbox_records,
            _("Send branch upload outbox events to the report server"),
            retry_owned=retry_owned,
        )
        return {"status": "queued", "queued": queued}

    @api.model
    def queue_historical_upload_batch(self, outbox_records):
        if not outbox_records:
            return {"status": "ok", "queued": 0}

        outbox_records = outbox_records.sudo().filtered(
            lambda record: record.status in {"pending", "failed"} and record.active
        ).sorted("id")
        if not outbox_records:
            return {"status": "ok", "queued": 0}

        queued = self._queue_branch_upload_sender_jobs(
            outbox_records,
            _("Send historical branch upload outbox events to the report server"),
        )
        return {"status": "queued", "queued": queued}

    @api.model
    def job_send_branch_upload_batch(self, outbox_ids=None):
        result = self._run_upload_delivery(outbox_ids)
        _logger.info("AB Odoo Sync upload sender result: %s", result)
        return result

    @api.model
    def job_send_historical_upload_batch(self, outbox_ids=None):
        if not outbox_ids:
            result = {"status": "ok", "sent": 0, "failed": 0}
            _logger.info("AB Odoo Sync historical upload sender result: %s", result)
            return result
        result = self._run_upload_delivery(outbox_ids)
        _logger.info("AB Odoo Sync historical upload sender result: %s", result)
        return result

    @api.model
    def _run_upload_delivery(self, outbox_ids):
        job_uuid = self.env.context.get("job_uuid")
        if not job_uuid:
            raise FailedJobError(_("Upload delivery must run through the queue."))
        # This cursor owns only delivery metadata. Committing here cannot commit
        # a caller's business transaction, and queue exception rollback cannot
        # erase an accepted receipt or an unsuccessful delivery attempt.
        with self.env.registry.cursor() as delivery_cr:
            delivery_env = api.Environment(delivery_cr, self.env.uid, dict(self.env.context))
            service = delivery_env[self._name]
            job = Job.load(delivery_env, job_uuid)
            if job.state != "started" or job.model_name != self._name or job.method_name not in {
                "job_send_branch_upload_batch", "job_send_historical_upload_batch",
            }:
                raise FailedJobError(_("Upload delivery must run through the queue."))
            expected_ids = job.args[0] if job.args else job.kwargs.get("outbox_ids")
            if outbox_ids != expected_ids:
                raise FailedJobError(_("Upload job records do not match its queued arguments."))
            Outbox = delivery_env["ab_odoo_sync_outbox"].sudo()
            if outbox_ids:
                records = Outbox.browse(outbox_ids).exists().sorted("id")
            else:
                # Support old sender jobs that did not carry an explicit batch.
                records = Outbox.with_context(active_test=False).search([
                    ("delivery_job_uuid", "=", job_uuid),
                ], order="id")
                if not records:
                    records = Outbox.search([
                        ("active", "=", True), ("status", "in", ["pending", "failed"]),
                        ("delivery_job_uuid", "=", False),
                    ], order="id", limit=service.get_batch_size())
            records._lock_delivery()
            records = records.filtered(
                lambda record: record.active and record.status in {"pending", "failed"}
                and record.delivery_job_uuid in {False, job_uuid}
            )
            records.filtered(lambda record: not record.delivery_job_uuid).write(
                {"delivery_job_uuid": job_uuid}
            )
            result = service.send_branch_upload_batch(records)
            job.retry += 1
            retry_seconds = job._get_retry_seconds()
            delivery_cr.commit()
        if result["status"] != "ok":
            message = result.get("error") or _("Report API returned failure.")
            if result.get("retryable"):
                raise RetryableJobError(
                    message, seconds=max(retry_seconds, result.get("retry_after") or 0),
                )
            raise FailedJobError(message)
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
        health = self._report_api_call(
            "/ab_odoo_sync/health",
            {
                "db_serial": db_serial,
                "hdd_serial": self.get_hdd_serial(),
            },
        )
        push = self.push_upload_records([])
        return {
            "status": "ok",
            "db_serial": db_serial,
            "report_database": health.get("database"),
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
                "database": result["report_database"],
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
