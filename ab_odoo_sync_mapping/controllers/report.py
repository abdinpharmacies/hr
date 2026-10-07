import json
import logging
import time

from odoo import fields, http
from odoo.addons.ab_odoo_sync_mapping.models.ab_odoo_sync_mapping_service import (
    SyncAuthorizationError,
    SyncHardwareMismatchError,
    SyncHardwarePendingError,
)
from odoo.http import request
from odoo.tools.translate import _
from odoo.addons.ab_odoo_sync_mapping.models.ab_odoo_sync_token import SyncTokenError

_logger = logging.getLogger(__name__)


def _json_response(payload, status=200):
    return request.make_response(
        json.dumps(payload),
        headers=[("Content-Type", "application/json"), ("Cache-Control", "no-store")],
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
        authorization = request.httprequest.headers.get("Authorization")
        started = time.monotonic()
        if authorization is not None:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                raise SyncTokenError()
            branch = request.env["ab_odoo_sync_token"]._authenticate(token, payload)
            mode = "token"
        else:
            allowed = request.env["ir.config_parameter"].sudo().get_param("ab_odoo_sync.allow_legacy_key_auth", "True")
            if allowed.lower() not in {"true", "1", "yes"}:
                raise SyncAuthorizationError()
            branch = self._key_authorized_branch(payload)
            mode = "legacy"
        _logger.info("AB sync auth mode=%s branch=%s duration_ms=%.2f", mode, branch.db_serial, (time.monotonic() - started) * 1000)
        return branch

    def _key_authorized_branch(self, payload):
        service = request.env["ab_odoo_sync_service"].sudo()
        return service.authenticate_branch_request(payload, self._request_key())

    def _auth_error_response(self, ex):
        if isinstance(ex, SyncTokenError):
            return _json_response({"ok": False, "error": ex.code, "code": ex.code}, status=ex.status)
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

    @http.route("/ab_odoo_sync/token", type="http", auth="public", methods=["POST"], csrf=False, save_session=False)
    def issue_token(self, **kwargs):
        try:
            branch = self._key_authorized_branch(self._payload())
        except (SyncAuthorizationError, SyncHardwarePendingError, SyncHardwareMismatchError, ValueError) as ex:
            return self._auth_error_response(ex)
        return _json_response(request.env["ab_odoo_sync_token"]._issue(branch))

    @http.route(
        "/ab_odoo_sync/health",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
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
        save_session=False,
    )
    def upload_records(self, **kwargs):
        started = time.monotonic()
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
        try:
            result = (
                request.env["ab_odoo_sync_service"]
                .sudo()
                .receive_upload_batch(payload, branch)
            )
            # Complete durable storage before constructing a delivery acknowledgement.
            request.env.cr.commit()
        except ValueError as ex:
            request.env.cr.rollback()
            return _json_response({"ok": False, "error": str(ex)}, status=400)
        except Exception:
            request.env.cr.rollback()
            _logger.error("AB sync receipt storage failed branch=%s", branch.db_serial)
            return _json_response({"ok": False, "error": _("Upload storage is unavailable; retry delivery.")}, status=503)
        result["ok"] = True
        _logger.info("AB sync upload branch=%s records=%s accepted=%s failed=%s duration_ms=%.2f", payload.get("db_serial"), len(payload.get("records", [])), result.get("accepted"), result.get("failed"), (time.monotonic() - started) * 1000)
        return _json_response(result)
