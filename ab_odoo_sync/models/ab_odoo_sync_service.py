import json
import logging
import urllib.error
import urllib.request

from odoo import api, fields, models
from odoo.tools import config
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class AbOdooSyncService(models.Model):
    _name = "ab_odoo_sync_service"
    _description = "AB Odoo Sync Service"

    @api.model
    def _icp(self):
        return self.env["ir.config_parameter"].sudo()

    @api.model
    def get_server_role(self):
        role = (self._icp().get_param("ab_odoo_sync.server_role") or "branch").strip().lower()
        return role if role in {"main", "branch"} else "branch"

    @api.model
    def get_batch_size(self):
        raw = self._icp().get_param("ab_odoo_sync.batch_size") or "1000"
        try:
            val = int(raw)
        except Exception:
            val = 1000
        return max(1, min(val, 10000))

    @api.model
    def get_db_serial(self):
        raw = config.get("db_serial", 0) or 0
        try:
            db_serial = int(raw)
        except (TypeError, ValueError) as ex:
            raise ValueError(_("Invalid db_serial config. Set db_serial to a positive integer.")) from ex
        if db_serial <= 0:
            raise ValueError(_("Missing db_serial config. Set db_serial to a positive integer."))
        return db_serial

    @api.model
    def _get_branch_sync_configuration_error(self):
        try:
            self.get_db_serial()
        except ValueError as ex:
            return str(ex)

        if not (self._icp().get_param("ab_odoo_sync.main_url") or "").strip():
            return _("Missing MAIN URL config: ab_odoo_sync.main_url")
        if not (self._icp().get_param("ab_odoo_sync.main_database") or "").strip():
            return _("Missing MAIN database config: ab_odoo_sync.main_database")
        if not (self._icp().get_param("ab_odoo_sync.api_key") or "").strip():
            return _("Missing API key config: ab_odoo_sync.api_key")
        return False

    @api.model
    def _parse_positive_int(self, value, field_name):
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError) as ex:
            raise ValueError(_("%s must be a positive integer.") % field_name) from ex
        if parsed <= 0:
            raise ValueError(_("%s must be a positive integer.") % field_name)
        return parsed

    @api.model
    def receive_upload_batch(self, payload):
        if self.get_server_role() != "main":
            raise ValueError(_("This server is not MAIN."))

        payload = payload or {}
        if not isinstance(payload, dict):
            raise ValueError(_("Upload payload must be a JSON object."))

        db_serial = self._parse_positive_int(payload.get("db_serial"), "db_serial")
        records = payload.get("records")
        if not isinstance(records, list):
            raise ValueError(_("records must be a JSON array."))

        upload_model = self.env["ab_odoo_sync_upload_record"].sudo()
        result = {
            "accepted": 0,
            "queued": 0,
            "failed": 0,
            "errors": [],
        }
        for index, row in enumerate(records):
            if not isinstance(row, dict):
                result["failed"] += 1
                result["errors"].append(
                    {
                        "index": index,
                        "error": _("record must be a JSON object."),
                    }
                )
                continue

            try:
                model_name = upload_model.validate_source_model_name(row.get("model_name"))
                rec_id = self._parse_positive_int(row.get("rec_id"), "rec_id")
                payload_json = row.get("payload")
                if not isinstance(payload_json, dict):
                    raise ValueError(_("payload must be a JSON object."))

                upload_record = upload_model.upsert_from_upload(
                    db_serial=db_serial,
                    model_name=model_name,
                    rec_id=rec_id,
                    payload=payload_json,
                )
                queued_count = upload_record._queue_apply_records()
                result["accepted"] += 1
                result["queued"] += queued_count
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

        return result

    @api.model
    def _normalize_payload_value(self, model, field_name, value):
        field = model._fields.get(field_name)
        if field and field.type == "many2one" and isinstance(value, (list, tuple)):
            return value[0] if value else False
        return value

    @api.model
    def _prepare_vals_for_create_or_write(self, model, payload):
        payload = payload or {}
        clean_vals = {}
        skipped_fields = []
        for key, val in payload.items():
            if key in {"id", "create_uid", "create_date", "write_uid", "write_date", "__last_update", "display_name"}:
                continue
            if key not in model._fields:
                skipped_fields.append(key)
                continue
            clean_vals[key] = self._normalize_payload_value(model, key, val)
        return clean_vals, skipped_fields

    @api.model
    def _force_next_id(self, model, target_id):
        self.env.cr.execute("SELECT pg_get_serial_sequence(%s, 'id')", (model._table,))
        row = self.env.cr.fetchone()
        seq_name = row and row[0]
        if not seq_name:
            raise ValueError(f"No sequence found for model {model._name}")

        # Force nextval(seq) to return target_id exactly.
        self.env.cr.execute("SELECT setval(%s::regclass, %s, false)", (seq_name, int(target_id)))

    @api.model
    def _apply_event(self, event):
        event_id = int(event.get("id") or 0)
        model_name = event.get("model_name")
        record_id = int(event.get("record_id") or 0)
        operation = event.get("operation")
        payload = event.get("payload_json") or {}

        if not model_name or not record_id or operation not in {"create", "write", "unlink"}:
            raise ValueError(f"Malformed sync event: {event}")

        model = self.env[model_name].with_context(skip_ab_odoo_sync_event=True).sudo()
        record = model.browse(record_id)

        if operation == "unlink":
            if record.exists():
                record.unlink()
            return []

        vals, skipped_fields = self._prepare_vals_for_create_or_write(model, payload)
        if skipped_fields:
            _logger.warning(
                "ab_odoo_sync event %s skipped missing field(s) on model %s: %s",
                event_id,
                model_name,
                ", ".join(skipped_fields),
            )

        if operation == "write":
            if record.exists():
                record.write(vals)
            else:
                # Optional behavior requested: create if missing.
                self._force_next_id(model, record_id)
                model.create(vals)
            return skipped_fields

        # operation == "create"
        if record.exists():
            record.write(vals)
            return skipped_fields

        self._force_next_id(model, record_id)
        model.create(vals)
        return skipped_fields

    @api.model
    def _main_api_call(self, path, payload):
        main_url = (self._icp().get_param("ab_odoo_sync.main_url") or "").strip().rstrip("/")
        main_database = (self._icp().get_param("ab_odoo_sync.main_database") or "").strip()
        api_key = (self._icp().get_param("ab_odoo_sync.api_key") or "").strip()
        if not main_url:
            raise ValueError(_("Missing MAIN URL config: ab_odoo_sync.main_url"))
        if not main_database:
            raise ValueError(_("Missing MAIN database config: ab_odoo_sync.main_database"))
        if not api_key:
            raise ValueError(_("Missing API key config: ab_odoo_sync.api_key"))

        url = f"{main_url}{path}"
        raw = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url=url, data=raw, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-AB-Sync-Key", api_key)
        req.add_header("X-Odoo-Database", main_database)

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as ex:
            err_body = ex.read().decode("utf-8", errors="ignore")
            raise ValueError(f"MAIN API HTTP {ex.code}: {err_body}") from ex
        except urllib.error.URLError as ex:
            raise ValueError(f"MAIN API connection error: {ex}") from ex

        try:
            data = json.loads(body or "{}")
        except json.JSONDecodeError as ex:
            raise ValueError(_("MAIN API returned an invalid JSON response.")) from ex
        if not data.get("ok"):
            raise ValueError(data.get("error") or "MAIN API returned failure")
        return data

    @api.model
    def push_upload_records(self, records):
        if self.get_server_role() != "branch":
            raise ValueError(_("This server is not BRANCH."))
        if not isinstance(records, list):
            raise ValueError(_("records must be a JSON array."))

        configuration_error = self._get_branch_sync_configuration_error()
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
    def test_branch_connection(self):
        if self.get_server_role() != "branch":
            return {"status": "skipped", "reason": _("server_role is not branch")}

        configuration_error = self._get_branch_sync_configuration_error()
        if configuration_error:
            return {"status": "skipped", "reason": configuration_error}

        checkpoint = self._get_or_create_local_checkpoint()
        db_serial = checkpoint.db_serial
        health = self._main_api_call(
            "/ab_odoo_sync/health",
            {"db_serial": db_serial},
        )
        pull = self._main_api_call(
            "/ab_odoo_sync/events",
            {
                "db_serial": db_serial,
                "last_event_id": checkpoint.last_event_id,
                "limit": 1,
            },
        )
        push = self.push_upload_records([])
        return {
            "status": "ok",
            "db_serial": db_serial,
            "main_database": health.get("database"),
            "latest_event_id": health.get("latest_event_id", 0),
            "pull_event_count": len(pull.get("events") or []),
            "push_accepted": push.get("accepted", 0),
            "capabilities": health.get("capabilities") or {},
        }

    @api.model
    def action_test_branch_connection(self):
        try:
            result = self.test_branch_connection()
        except Exception as ex:
            _logger.exception("ab_odoo_sync branch connection test failed")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Odoo Sync Connection"),
                    "message": str(ex),
                    "type": "danger",
                    "sticky": True,
                },
            }

        if result.get("status") != "ok":
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Odoo Sync Connection"),
                    "message": result.get("reason") or _("Connection test was skipped."),
                    "type": "warning",
                    "sticky": True,
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Odoo Sync Connection"),
                "message": _(
                    "Connected to MAIN database %(database)s. Pull and push checks passed for DB serial %(db_serial)s."
                )
                % {
                    "database": result["main_database"],
                    "db_serial": result["db_serial"],
                },
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _get_or_create_local_checkpoint(self):
        db_serial = self.get_db_serial()
        checkpoint = self.env["ab_odoo_sync_checkpoint"].sudo().search(
            [("db_serial", "=", db_serial)],
            limit=1,
        )
        if checkpoint:
            return checkpoint

        return self.env["ab_odoo_sync_checkpoint"].sudo().create(
            {
                "db_serial": db_serial,
                "last_event_id": 0,
                "active": True,
            }
        )

    @api.model
    def _get_or_create_event_state(self, event, db_serial):
        event_id = int(event.get("id") or 0)
        state_model = self.env["ab_odoo_sync_event_state"].sudo()
        state = state_model.search(
            [
                ("source_event_id", "=", event_id),
                ("db_serial", "=", db_serial),
            ],
            limit=1,
        )
        vals = {
            "source_event_id": event_id,
            "db_serial": db_serial,
            "model_name": event.get("model_name"),
            "record_id": int(event.get("record_id") or 0),
            "operation": event.get("operation"),
            "payload_json": event.get("payload_json") or {},
        }
        if state:
            state.with_context(ab_odoo_sync_allow_event_state_write=True).write(vals)
            return state
        vals.update(
            {
                "status": "pending",
                "skipped_fields_json": [],
                "error_message": False,
            }
        )
        return state_model.with_context(ab_odoo_sync_allow_event_state_write=True).create(vals)

    @api.model
    def run_branch_sync_batch(self):
        if self.get_server_role() != "branch":
            return {"status": "skipped", "reason": "server_role is not branch"}

        configuration_error = self._get_branch_sync_configuration_error()
        if configuration_error:
            return {"status": "skipped", "reason": configuration_error}

        checkpoint = self._get_or_create_local_checkpoint()
        batch_size = self.get_batch_size()
        db_serial = checkpoint.db_serial
        payload = {
            "db_serial": db_serial,
            "last_event_id": checkpoint.last_event_id,
            "limit": batch_size,
        }

        response = self._main_api_call("/ab_odoo_sync/events", payload)
        events = response.get("events") or []

        if not events:
            return {"status": "ok", "processed": 0, "last_event_id": checkpoint.last_event_id}

        last_processed = checkpoint.last_event_id
        processed_count = 0
        for event in events:
            event_id = int(event["id"])
            state = self._get_or_create_event_state(event, db_serial)
            if state.status in {"full_sync", "partially_sync", "not_sync"}:
                last_processed = event_id
                processed_count += 1
                continue

            try:
                with self.env.cr.savepoint():
                    state.with_context(ab_odoo_sync_allow_event_state_write=True).write(
                        {
                            "status": "pending",
                            "skipped_fields_json": [],
                            "error_message": False,
                        }
                    )
                    skipped_fields = self._apply_event(event)
            except Exception as ex:
                state.with_context(ab_odoo_sync_allow_event_state_write=True).write(
                    {
                        "status": "failed",
                        "error_message": str(ex),
                        "applied_at": fields.Datetime.now(),
                    }
                )
                return {
                    "status": "failed",
                    "processed": processed_count,
                    "failed_event_id": event_id,
                    "error": str(ex),
                    "last_event_id": checkpoint.last_event_id,
                }

            status = "partially_sync" if skipped_fields else "full_sync"
            state.with_context(ab_odoo_sync_allow_event_state_write=True).write(
                {
                    "status": status,
                    "skipped_fields_json": skipped_fields,
                    "error_message": False,
                    "applied_at": fields.Datetime.now(),
                }
            )
            last_processed = event_id
            processed_count += 1

        now = fields.Datetime.now()
        checkpoint.sudo().write(
            {
                "last_event_id": last_processed,
                "last_sync_at": now,
            }
        )

        # Update MAIN-side branch checkpoint for safe cleanup watermark.
        self._main_api_call(
            "/ab_odoo_sync/checkpoint/ack",
            {
                "db_serial": db_serial,
                "last_event_id": last_processed,
                "last_sync_at": fields.Datetime.to_string(now),
                "active": True,
            },
        )

        return {"status": "ok", "processed": processed_count, "last_event_id": last_processed}

    @api.model
    def cron_run_branch_sync(self):
        try:
            result = self.run_branch_sync_batch()
            _logger.info("ab_odoo_sync branch batch result: %s", result)
            return result
        except Exception:
            _logger.exception("ab_odoo_sync branch sync batch failed")
            raise

    @api.model
    def cleanup_consumed_events(self):
        if self.get_server_role() != "main":
            return {"status": "skipped", "reason": _("server_role is not main")}

        checkpoints = self.env["ab_odoo_sync_checkpoint"].sudo().search([("active", "=", True)])
        if not checkpoints:
            return {"status": "ok", "deleted": 0, "reason": _("no active checkpoints")}

        min_last_event_id = min(checkpoints.mapped("last_event_id") or [0])
        if min_last_event_id <= 0:
            return {"status": "ok", "deleted": 0, "reason": _("watermark is zero")}

        events = self.env["ab_odoo_sync_event"].sudo().search(
            [("id", "<=", min_last_event_id)],
            order="id asc",
            limit=50000,
        )
        deleted = len(events)
        if events:
            events.with_context(ab_odoo_sync_allow_event_cleanup=True).unlink()

        return {
            "status": "ok",
            "deleted": deleted,
            "watermark": min_last_event_id,
        }

    @api.model
    def cron_cleanup_consumed_events(self):
        result = {
            "status": "skipped",
            "reason": _("automatic cleanup is disabled; run manual cleanup from Odoo Sync checkpoints"),
        }
        _logger.info("ab_odoo_sync cleanup result: %s", result)
        return result
