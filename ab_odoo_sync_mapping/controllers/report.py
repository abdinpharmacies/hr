import json

from odoo import fields, http
from odoo.addons.ab_odoo_sync_mapping.models.ab_odoo_sync_mapping_service import (
    SyncAuthorizationError,
    SyncHardwareMismatchError,
    SyncHardwarePendingError,
)
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

    def _request_key(self):
        return request.httprequest.headers.get("X-AB-Sync-Key")

    def _authorized_branch(self, payload):
        service = request.env["ab_odoo_sync_service"].sudo()
        return service.authenticate_branch_request(payload, self._request_key())

    def _auth_error_response(self, ex):
        if isinstance(ex, SyncAuthorizationError):
            return _json_response(
                {"ok": False, "error": _("Unauthorized")},
                status=401,
            )
        if isinstance(ex, ValueError):
            return _json_response(
                {"ok": False, "error": _("Invalid or missing hardware serial.")},
                status=400,
            )
        if isinstance(ex, SyncHardwarePendingError):
            return _json_response(
                {
                    "ok": False,
                    "error": "hardware_pending",
                    "code": "hardware_pending",
                },
                status=403,
            )
        if isinstance(ex, SyncHardwareMismatchError):
            return _json_response(
                {
                    "ok": False,
                    "error": "hardware_mismatch",
                    "code": "hardware_mismatch",
                },
                status=403,
            )
        raise ex

    @http.route(
        "/ab_odoo_sync/health",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def health(self, **kwargs):
        payload = self._payload()
        try:
            branch = self._authorized_branch(payload)
        except (
            SyncAuthorizationError,
            SyncHardwarePendingError,
            SyncHardwareMismatchError,
            ValueError,
        ) as ex:
            return self._auth_error_response(ex)
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
        payload = self._payload()
        try:
            self._authorized_branch(payload)
        except (
            SyncAuthorizationError,
            SyncHardwarePendingError,
            SyncHardwareMismatchError,
            ValueError,
        ) as ex:
            return self._auth_error_response(ex)
        try:
            result = (
                request.env["ab_odoo_sync_service"]
                .sudo()
                .receive_upload_batch(payload)
            )
        except ValueError as ex:
            return _json_response({"ok": False, "error": str(ex)}, status=400)
        result["ok"] = True
        return _json_response(result)
