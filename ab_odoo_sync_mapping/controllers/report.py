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


class AbOdooSyncMappingController(http.Controller):
    def _payload(self):
        try:
            payload = request.get_json_data()
        except (TypeError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _authorize(self):
        service = request.env["ab_odoo_sync_service"].sudo()
        api_key = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("ab_odoo_sync.api_key")
            or ""
        ).strip()
        request_key = (
            request.httprequest.headers.get("X-AB-Sync-Key") or ""
        ).strip()
        return service.is_configured(api_key) and hmac.compare_digest(
            request_key, api_key
        )

    @http.route(
        "/ab_odoo_sync/health",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def health(self, **kwargs):
        if not self._authorize():
            return _json_response(
                {"ok": False, "error": _("Unauthorized")}, status=401
            )
        payload = self._payload()
        try:
            branch = (
                request.env["ab_odoo_sync_service"]
                .sudo()
                .get_registered_branch(payload.get("db_serial"))
            )
        except ValueError as ex:
            return _json_response({"ok": False, "error": str(ex)}, status=403)
        return _json_response(
            {
                "ok": True,
                "api_version": 1,
                "database": request.env.cr.dbname,
                "db_serial": branch.db_serial,
                "server_time": fields.Datetime.to_string(fields.Datetime.now()),
                "capabilities": {"push": True, "pull": False},
            }
        )

    @http.route(
        "/ab_odoo_sync/upload",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def upload_records(self, **kwargs):
        if not self._authorize():
            return _json_response(
                {"ok": False, "error": _("Unauthorized")}, status=401
            )
        try:
            result = (
                request.env["ab_odoo_sync_service"]
                .sudo()
                .receive_upload_batch(self._payload())
            )
        except ValueError as ex:
            return _json_response({"ok": False, "error": str(ex)}, status=400)
        result["ok"] = True
        return _json_response(result)
