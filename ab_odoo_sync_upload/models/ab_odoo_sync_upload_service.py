import base64
import datetime
import hashlib
import ipaddress
import json
import logging
import random
import time
from email.utils import parsedate_to_datetime
import urllib.error
import urllib.request
from collections import defaultdict
from urllib.parse import urlsplit

from odoo import api, fields, models
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.tools import config
from odoo.tools.translate import _

from .ab_odoo_sync_hardware import (
    normalize_hdd_serial,
    read_hdd_serial,
)

_logger = logging.getLogger(__name__)
_SENSITIVE_SNAPSHOT_FIELDS = {"password"}
_DEFAULT_UPLOAD_CHANNEL = "root"


class SyncHTTPError(ValueError):
    def __init__(self, status, code, message=None):
        self.status = status
        self.code = code
        super().__init__(message or f"Report sync HTTP {status}: {code}")


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
    def _retry_delay(self, retry_after=None):
        job = self.env["queue.job"].sudo().search([
            ("uuid", "=", self.env.context.get("job_uuid") or "")], limit=1)
        base = min(300, 5 * 2 ** min(job.retry if job else 0, 6))
        seconds = min(300, base + random.uniform(0, base * 0.2))
        if retry_after:
            try:
                required = float(retry_after)
            except (ValueError, TypeError):
                try:
                    required = (parsedate_to_datetime(retry_after) - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    required = 0
            seconds = max(seconds, required)
        return seconds

    @api.model
    def _send_report_request(self, path, payload, credential_header, credential):
        report_url = (self._icp().get_param("ab_odoo_sync.report_url") or "").strip().rstrip("/")
        report_database = (self._icp().get_param("ab_odoo_sync.report_database") or "").strip()
        self._validate_report_url(report_url)
        self._ensure_ascii_transport_config("ab_odoo_sync.report_url", report_url)
        self._ensure_ascii_transport_config("ab_odoo_sync.report_database", report_database)
        request = urllib.request.Request(
            url=f"{report_url}{path}", data=json.dumps(payload).encode("utf-8"), method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header(credential_header, credential)
        request.add_header("X-Odoo-Database", report_database)
        # Do not forward a credential to a redirected destination.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as ex:
            if ex.code in {408, 429} or ex.code >= 500:
                raise RetryableJobError(_("Report sync HTTP %(status)s") % {"status": ex.code}, seconds=self._retry_delay(ex.headers.get("Retry-After"))) from ex
            try:
                error = json.loads(ex.read().decode("utf-8", errors="replace"))
                code = error.get("code", "request_rejected")
            except (ValueError, AttributeError):
                code = "request_rejected"
            # Never retain response bodies which may contain credentials or data.
            if code not in {"token_invalid", "token_expired", "token_revoked", "branch_mismatch", "hardware_pending", "hardware_mismatch"}:
                code = "request_rejected"
            message = _("Report sync HTTP %(status)s: %(code)s") % {"status": ex.code, "code": code}
            raise SyncHTTPError(ex.code, code, message) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as ex:
            raise RetryableJobError(_("Report sync connection failed"), seconds=self._retry_delay()) from ex
        try:
            result = json.loads(body or "{}")
        except ValueError as ex:
            raise RetryableJobError(_("Invalid report sync response"), seconds=self._retry_delay()) from ex
        if not isinstance(result, dict) or not result.get("ok"):
            raise ValueError(_("Report sync request failed"))
        return result

    @api.model
    def _report_api_call(self, path, payload):
        payload = dict(payload or {})
        payload.setdefault("hdd_serial", self.get_hdd_serial())
        api_key = (self._icp().get_param("ab_odoo_sync.api_key") or "").strip()
        self._ensure_ascii_transport_config("ab_odoo_sync.api_key", api_key)
        use_tokens = self._icp().get_param("ab_odoo_sync.use_branch_tokens", "True").lower() in {"true", "1", "yes"}
        if not use_tokens:
            return self._send_report_request(path, payload, "X-AB-Sync-Key", api_key)
        fingerprint = hashlib.sha256(json.dumps([
            self._icp().get_param("ab_odoo_sync.report_url"),
            self._icp().get_param("ab_odoo_sync.report_database"),
            payload.get("db_serial"), payload["hdd_serial"], api_key,
        ], sort_keys=True).encode()).hexdigest()
        cache = self.env["ab_odoo_sync_client_token"]
        def fetch():
            return self._send_report_request("/ab_odoo_sync/token", {
                "db_serial": payload.get("db_serial"), "hdd_serial": payload["hdd_serial"],
            }, "X-AB-Sync-Key", api_key)
        token = cache._get_token(fingerprint, fetch)
        try:
            return self._send_report_request(path, payload, "Authorization", f"Bearer {token}")
        except SyncHTTPError as ex:
            if ex.status != 401 or ex.code not in {"token_invalid", "token_expired"}:
                raise
        token = cache._get_token(fingerprint, fetch, rejected_token=token)
        return self._send_report_request(path, payload, "Authorization", f"Bearer {token}")

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

    @api.model
    def send_branch_upload_batch(self, outbox_records=None):
        self.env.cr.execute("SELECT pg_try_advisory_xact_lock(193733, 1)")
        if not self.env.cr.fetchone()[0]:
            raise RetryableJobError(_("Another branch upload is active"), seconds=5, ignore_retry=True)
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

        started = time.monotonic()
        try:
            response = self.push_upload_records(rows)
        except RetryableJobError:
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
            }

        # An incomplete acknowledgement must never mark unsent records as sent.
        if (not isinstance(response.get("errors"), list)
                or not isinstance(response.get("accepted"), int)
                or not isinstance(response.get("failed"), int)
                or response["accepted"] + response["failed"] != len(rows)):
            raise RetryableJobError(_("Incomplete report sync acknowledgement"), seconds=self._retry_delay())
        errors_by_index = {
            int(error.get("index")): error.get("error") or _("Unknown upload error")
            for error in response.get("errors", [])
            if isinstance(error, dict) and str(error.get("index", "")).isdigit()
        }
        if (len(errors_by_index) != response["failed"]
                or any(index < 0 or index >= len(rows) for index in errors_by_index)):
            raise RetryableJobError(_("Invalid report sync acknowledgement"), seconds=self._retry_delay())
        now = fields.Datetime.now()
        live_ages = [
            (now - record.create_date).total_seconds()
            for record in outbox_records
            if record.create_date and "sync_historical" not in (record.queue_channel or "")
        ]
        _logger.info(
            "AB sync send records=%s duration_ms=%.2f live_oldest_age_seconds=%.2f",
            len(rows), (time.monotonic() - started) * 1000, max(live_ages, default=0),
        )
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
    def _normalize_outbox_queue_channel(self, queue_channel):
        return queue_channel or _DEFAULT_UPLOAD_CHANNEL

    @api.model
    def _group_outbox_by_queue_channel(self, outbox_records):
        grouped = defaultdict(lambda: self.env["ab_odoo_sync_outbox"].sudo().browse())
        for outbox in outbox_records:
            grouped[self._normalize_outbox_queue_channel(outbox.queue_channel)] |= outbox
        return grouped

    @api.model
    def _get_batch_delay(self):
        raw = self._icp().get_param("ab_odoo_sync.upload_batch_delay_seconds", "5")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = 5
        return value if 0 <= value <= 300 else 5

    @api.model
    def _pending_upload_domain(self, channel=None):
        domain = fields.Domain("status", "=", "pending") & fields.Domain("active", "=", True)
        if channel:
            channel_domain = fields.Domain("queue_channel", "=", channel)
            if channel == "root":
                channel_domain |= fields.Domain("queue_channel", "=", False)
            domain &= channel_domain
        return domain

    @api.model
    def _queue_channel_sender(self, channel, delay=None):
        historical = channel == "root.sync_historical" or ".sync_historical." in channel
        self.sudo().with_delay(
            identity_key=f"ab_odoo_sync_branch_upload_sender:{channel}",
            description=_("Send branch upload outbox events to the report server"),
            max_retries=0, channel=channel, priority=30 if historical else 5,
            eta=self._get_batch_delay() if delay is None else delay,
        ).job_send_branch_upload_batch(queue_channel=channel)

    @api.model
    def _queue_branch_upload_sender_jobs(self, outbox_records, description):
        for channel in sorted(self._group_outbox_by_queue_channel(outbox_records)):
            self._queue_channel_sender(channel)
        return len(outbox_records)

    @api.model
    def queue_branch_upload_batch(self, outbox_records=None):
        configuration_error = self._get_upload_configuration_error()
        if configuration_error:
            return {"status": "skipped", "queued": 0, "reason": configuration_error}
        Outbox = self.env["ab_odoo_sync_outbox"].sudo()
        if outbox_records is not None:
            records = outbox_records.sudo().exists().filtered(lambda r: r.active and r.status in {"pending", "failed"})
            records.filtered(lambda r: r.status == "failed").write({"status": "pending", "last_error": False})
            queued = self._queue_branch_upload_sender_jobs(records, "")
        else:
            groups = Outbox._read_group(self._pending_upload_domain(), ["queue_channel"], ["__count"])
            queued = 0
            for channel, count in groups:
                self._queue_channel_sender(channel or "root")
                queued += count
        return {"status": "queued", "queued": queued}

    @api.model
    def queue_historical_upload_batch(self, outbox_records):
        configuration_error = self._get_upload_configuration_error()
        if configuration_error:
            return {"status": "skipped", "queued": 0, "reason": configuration_error}
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
    def job_send_branch_upload_batch(self, outbox_ids=None, queue_channel=None):
        Outbox = self.env["ab_odoo_sync_outbox"].sudo()
        if outbox_ids:
            # Compatibility with jobs queued before batching was introduced.
            records = Outbox.browse(outbox_ids).exists()
        else:
            records = Outbox.search(self._pending_upload_domain(queue_channel), order="id", limit=self.get_batch_size())
        if records and all("sync_historical" in (r.queue_channel or "") for r in records):
            live_domain = self._pending_upload_domain() & (
                fields.Domain("queue_channel", "not ilike", "sync_historical") |
                fields.Domain("queue_channel", "=", False))
            if Outbox.search_count(live_domain, limit=1):
                raise RetryableJobError(_("Live branch uploads take priority"), seconds=5, ignore_retry=True)
        result = self.send_branch_upload_batch(records)
        if queue_channel and Outbox.search_count(self._pending_upload_domain(queue_channel), limit=1):
            self._queue_channel_sender(queue_channel, delay=0)
        _logger.info("AB Odoo Sync upload sender result: %s", result)
        return result

    @api.model
    def job_send_historical_upload_batch(self, outbox_ids=None):
        if not outbox_ids:
            return {"status": "ok", "sent": 0, "failed": 0}
        return self.job_send_branch_upload_batch(outbox_ids=outbox_ids)

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
