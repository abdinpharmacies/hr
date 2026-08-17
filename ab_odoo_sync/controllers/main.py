import hmac
import json

from odoo import fields, http
from odoo.http import request
from odoo.tools.translate import _


def _json_response(payload, status=200):
    return request.make_response(
        json.dumps(payload),
        headers=[("Content-Type", "application/json")],
        status=status,
    )


class AbOdooSyncController(http.Controller):

    def _payload(self):
        try:
            payload = request.get_json_data()
        except (TypeError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _authorize(self):
        api_key = (request.env["ir.config_parameter"].sudo().get_param("ab_odoo_sync.api_key") or "").strip()
        request_key = (request.httprequest.headers.get("X-AB-Sync-Key") or "").strip()
        return bool(api_key) and hmac.compare_digest(request_key, api_key)

    def _parse_db_serial(self, payload):
        try:
            db_serial = int(payload.get("db_serial") or 0)
        except (TypeError, ValueError):
            return 0
        return db_serial if db_serial > 0 else 0

    def _get_registered_checkpoint(self, db_serial):
        return request.env["ab_odoo_sync_checkpoint"].sudo().search(
            [
                ("db_serial", "=", db_serial),
                ("active", "=", True),
            ],
            limit=1,
        )

    def _get_authorized_branch(self, payload):
        db_serial = self._parse_db_serial(payload)
        if not db_serial:
            return 0, request.env["ab_odoo_sync_checkpoint"].sudo().browse()
        return db_serial, self._get_registered_checkpoint(db_serial)

    @http.route("/ab_odoo_sync/health", type="http", auth="public", methods=["POST"], csrf=False)
    def health(self, **kwargs):
        if not self._authorize():
            return _json_response({"ok": False, "error": _("Unauthorized")}, status=401)

        service = request.env["ab_odoo_sync_service"].sudo()
        if service.get_server_role() != "main":
            return _json_response({"ok": False, "error": _("This server is not MAIN.")}, status=400)

        payload = self._payload()
        db_serial, checkpoint = self._get_authorized_branch(payload)
        if not db_serial:
            return _json_response({"ok": False, "error": _("db_serial is required")}, status=400)
        if not checkpoint:
            return _json_response({"ok": False, "error": _("Unknown or inactive db_serial.")}, status=403)

        latest_event = request.env["ab_odoo_sync_event"].sudo().search([], order="id desc", limit=1)
        return _json_response(
            {
                "ok": True,
                "api_version": 1,
                "database": request.env.cr.dbname,
                "db_serial": db_serial,
                "latest_event_id": latest_event.id if latest_event else 0,
                "server_time": fields.Datetime.to_string(fields.Datetime.now()),
                "capabilities": {
                    "pull": True,
                    "push": True,
                },
            }
        )

    @http.route("/ab_odoo_sync/events", type="http", auth="public", methods=["POST"], csrf=False)
    def get_events_after(self, **kwargs):
        if not self._authorize():
            return _json_response({"ok": False, "error": _("Unauthorized")}, status=401)

        service = request.env["ab_odoo_sync_service"].sudo()
        if service.get_server_role() != "main":
            return _json_response({"ok": False, "error": _("This server is not MAIN.")}, status=400)

        payload = self._payload()
        db_serial, checkpoint = self._get_authorized_branch(payload)
        if not db_serial:
            return _json_response({"ok": False, "error": _("db_serial is required")}, status=400)
        if not checkpoint:
            return _json_response({"ok": False, "error": _("Unknown or inactive db_serial.")}, status=403)
        try:
            last_event_id = int(payload.get("last_event_id") or 0)
            limit = int(payload.get("limit") or service.get_batch_size())
        except (TypeError, ValueError):
            return _json_response(
                {"ok": False, "error": _("last_event_id and limit must be integers.")},
                status=400,
            )
        if last_event_id < 0 or limit <= 0:
            return _json_response(
                {"ok": False, "error": _("last_event_id must be zero or greater and limit must be positive.")},
                status=400,
            )

        events = request.env["ab_odoo_sync_event"].sudo().get_events_after(last_event_id=last_event_id, limit=limit)
        return _json_response({"ok": True, "events": events})

    @http.route("/ab_odoo_sync/checkpoint/ack", type="http", auth="public", methods=["POST"], csrf=False)
    def ack_checkpoint(self, **kwargs):
        if not self._authorize():
            return _json_response({"ok": False, "error": _("Unauthorized")}, status=401)

        service = request.env["ab_odoo_sync_service"].sudo()
        if service.get_server_role() != "main":
            return _json_response({"ok": False, "error": _("This server is not MAIN.")}, status=400)

        payload = self._payload()
        db_serial, checkpoint = self._get_authorized_branch(payload)
        if not db_serial:
            return _json_response({"ok": False, "error": _("db_serial is required")}, status=400)
        if not checkpoint:
            return _json_response({"ok": False, "error": _("Unknown or inactive db_serial.")}, status=403)

        try:
            last_event_id = int(payload.get("last_event_id") or 0)
        except (TypeError, ValueError):
            return _json_response({"ok": False, "error": _("last_event_id must be an integer.")}, status=400)
        if last_event_id < 0:
            return _json_response(
                {"ok": False, "error": _("last_event_id must be zero or greater.")},
                status=400,
            )
        if last_event_id < checkpoint.last_event_id:
            return _json_response(
                {"ok": False, "error": _("Checkpoint acknowledgement cannot move backward.")},
                status=409,
            )

        latest_event = request.env["ab_odoo_sync_event"].sudo().search([], order="id desc", limit=1)
        highest_known_event_id = max(checkpoint.last_event_id, latest_event.id if latest_event else 0)
        if last_event_id > highest_known_event_id:
            return _json_response(
                {"ok": False, "error": _("Checkpoint acknowledgement exceeds the latest MAIN event.")},
                status=409,
            )

        checkpoint.write(
            {
                "last_event_id": last_event_id,
                "last_sync_at": fields.Datetime.now(),
                "active": True,
            }
        )

        return _json_response({"ok": True})

    @http.route("/ab_odoo_sync/upload", type="http", auth="public", methods=["POST"], csrf=False)
    def upload_records(self, **kwargs):
        if not self._authorize():
            return _json_response({"ok": False, "error": _("Unauthorized")}, status=401)

        service = request.env["ab_odoo_sync_service"].sudo()
        payload = self._payload()
        db_serial, checkpoint = self._get_authorized_branch(payload)
        if not db_serial:
            return _json_response({"ok": False, "error": _("db_serial is required")}, status=400)
        if not checkpoint:
            return _json_response({"ok": False, "error": _("Unknown or inactive db_serial.")}, status=403)
        try:
            result = service.receive_upload_batch(payload)
        except Exception as ex:
            return _json_response({"ok": False, "error": str(ex)}, status=400)

        result["ok"] = True
        return _json_response(result)
