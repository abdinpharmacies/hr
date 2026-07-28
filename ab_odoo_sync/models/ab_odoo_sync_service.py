import json
import logging
import urllib.error
import urllib.request

from odoo import api, fields, models

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
    def get_branch_code(self):
        return (self._icp().get_param("ab_odoo_sync.branch_code") or "default_branch").strip()

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
        for key, val in payload.items():
            if key in {"id", "create_uid", "create_date", "write_uid", "write_date", "__last_update", "display_name"}:
                continue
            if key not in model._fields:
                continue
            clean_vals[key] = self._normalize_payload_value(model, key, val)
        return clean_vals

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
            return

        vals = self._prepare_vals_for_create_or_write(model, payload)

        if operation == "write":
            if record.exists():
                record.write(vals)
            else:
                # Optional behavior requested: create if missing.
                self._force_next_id(model, record_id)
                model.create(vals)
            return

        # operation == "create"
        if record.exists():
            record.write(vals)
            return

        self._force_next_id(model, record_id)
        model.create(vals)

    @api.model
    def _main_api_call(self, path, payload):
        main_url = (self._icp().get_param("ab_odoo_sync.main_url") or "").strip().rstrip("/")
        api_key = (self._icp().get_param("ab_odoo_sync.api_key") or "").strip()
        if not main_url:
            raise ValueError("Missing MAIN URL config: ab_odoo_sync.main_url")
        if not api_key:
            raise ValueError("Missing API key config: ab_odoo_sync.api_key")

        url = f"{main_url}{path}"
        raw = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url=url, data=raw, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-AB-Sync-Key", api_key)

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as ex:
            err_body = ex.read().decode("utf-8", errors="ignore")
            raise ValueError(f"MAIN API HTTP {ex.code}: {err_body}") from ex
        except urllib.error.URLError as ex:
            raise ValueError(f"MAIN API connection error: {ex}") from ex

        data = json.loads(body or "{}")
        if not data.get("ok"):
            raise ValueError(data.get("error") or "MAIN API returned failure")
        return data

    @api.model
    def _get_or_create_local_checkpoint(self):
        branch_code = self.get_branch_code()
        checkpoint = self.env["ab_odoo_sync_checkpoint"].sudo().search(
            [("branch_code", "=", branch_code)],
            limit=1,
        )
        if checkpoint:
            return checkpoint

        return self.env["ab_odoo_sync_checkpoint"].sudo().create(
            {
                "branch_code": branch_code,
                "last_event_id": 0,
                "active": True,
            }
        )

    @api.model
    def run_branch_sync_batch(self):
        if self.get_server_role() != "branch":
            return {"status": "skipped", "reason": "server_role is not branch"}

        checkpoint = self._get_or_create_local_checkpoint()
        batch_size = self.get_batch_size()
        branch_code = checkpoint.branch_code
        payload = {
            "branch_code": branch_code,
            "last_event_id": checkpoint.last_event_id,
            "limit": batch_size,
        }

        response = self._main_api_call("/ab_odoo_sync/events", payload)
        events = response.get("events") or []

        if not events:
            return {"status": "ok", "processed": 0, "last_event_id": checkpoint.last_event_id}

        last_processed = checkpoint.last_event_id
        for event in events:
            self._apply_event(event)
            last_processed = int(event["id"])

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
                "branch_code": branch_code,
                "last_event_id": last_processed,
                "last_sync_at": fields.Datetime.to_string(now),
                "active": True,
            },
        )

        return {"status": "ok", "processed": len(events), "last_event_id": last_processed}

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
            return {"status": "skipped", "reason": "server_role is not main"}

        checkpoints = self.env["ab_odoo_sync_checkpoint"].sudo().search([("active", "=", True)])
        if not checkpoints:
            return {"status": "ok", "deleted": 0, "reason": "no active checkpoints"}

        min_last_event_id = min(checkpoints.mapped("last_event_id") or [0])
        if min_last_event_id <= 0:
            return {"status": "ok", "deleted": 0, "reason": "watermark is zero"}

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
        result = self.cleanup_consumed_events()
        _logger.info("ab_odoo_sync cleanup result: %s", result)
        return result
