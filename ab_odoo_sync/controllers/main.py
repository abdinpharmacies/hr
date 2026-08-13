import json

from odoo import fields, http
from odoo.http import request


def _json_response(payload, status=200):
    return request.make_response(
        json.dumps(payload),
        headers=[("Content-Type", "application/json")],
        status=status,
    )


class AbOdooSyncController(http.Controller):

    def _payload(self):
        payload = request.jsonrequest
        if payload:
            return payload
        raw = request.httprequest.data
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _authorize(self):
        api_key = (request.env["ir.config_parameter"].sudo().get_param("ab_odoo_sync.api_key") or "").strip()
        request_key = (request.httprequest.headers.get("X-AB-Sync-Key") or "").strip()
        return bool(api_key) and request_key == api_key

    def _parse_db_serial(self, payload):
        try:
            db_serial = int(payload.get("db_serial") or 0)
        except (TypeError, ValueError):
            return 0
        return db_serial if db_serial > 0 else 0

    def _register_checkpoint_request(self, db_serial, last_event_id):
        checkpoint_model = request.env["ab_odoo_sync_checkpoint"].sudo()
        checkpoint = checkpoint_model.search([("db_serial", "=", db_serial)], limit=1)
        if not checkpoint:
            checkpoint_model.create(
                {
                    "db_serial": db_serial,
                    "last_event_id": max(0, int(last_event_id or 0)),
                    "active": True,
                }
            )
            return
        vals = {"active": True}
        if checkpoint.last_event_id > int(last_event_id or 0):
            vals["last_event_id"] = max(0, int(last_event_id or 0))
        checkpoint.write(vals)

    @http.route("/ab_odoo_sync/events", type="http", auth="public", methods=["POST"], csrf=False)
    def get_events_after(self, **kwargs):
        if not self._authorize():
            return _json_response({"ok": False, "error": "Unauthorized"}, status=401)

        service = request.env["ab_odoo_sync_service"].sudo()
        if service.get_server_role() != "main":
            return _json_response({"ok": False, "error": "This server is not MAIN"}, status=400)

        payload = self._payload()
        db_serial = self._parse_db_serial(payload)
        if not db_serial:
            return _json_response({"ok": False, "error": "db_serial is required"}, status=400)
        last_event_id = int(payload.get("last_event_id") or 0)
        limit = int(payload.get("limit") or service.get_batch_size())
        self._register_checkpoint_request(db_serial, last_event_id)

        events = request.env["ab_odoo_sync_event"].sudo().get_events_after(last_event_id=last_event_id, limit=limit)
        return _json_response({"ok": True, "events": events})

    @http.route("/ab_odoo_sync/checkpoint/ack", type="http", auth="public", methods=["POST"], csrf=False)
    def ack_checkpoint(self, **kwargs):
        if not self._authorize():
            return _json_response({"ok": False, "error": "Unauthorized"}, status=401)

        service = request.env["ab_odoo_sync_service"].sudo()
        if service.get_server_role() != "main":
            return _json_response({"ok": False, "error": "This server is not MAIN"}, status=400)

        payload = self._payload()
        db_serial = self._parse_db_serial(payload)
        if not db_serial:
            return _json_response({"ok": False, "error": "db_serial is required"}, status=400)

        last_event_id = int(payload.get("last_event_id") or 0)
        last_sync_at = payload.get("last_sync_at") or fields.Datetime.now()
        active = bool(payload.get("active", True))

        checkpoint_model = request.env["ab_odoo_sync_checkpoint"].sudo()
        checkpoint = checkpoint_model.search([("db_serial", "=", db_serial)], limit=1)

        vals = {
            "last_event_id": last_event_id,
            "last_sync_at": last_sync_at,
            "active": active,
        }
        if checkpoint:
            checkpoint.write(vals)
        else:
            vals["db_serial"] = db_serial
            checkpoint_model.create(vals)

        return _json_response({"ok": True})

    @http.route("/ab_odoo_sync/upload", type="http", auth="public", methods=["POST"], csrf=False)
    def upload_records(self, **kwargs):
        if not self._authorize():
            return _json_response({"ok": False, "error": "Unauthorized"}, status=401)

        service = request.env["ab_odoo_sync_service"].sudo()
        payload = self._payload()
        try:
            result = service.receive_upload_batch(payload)
        except Exception as ex:
            return _json_response({"ok": False, "error": str(ex)}, status=400)

        result["ok"] = True
        return _json_response(result)
