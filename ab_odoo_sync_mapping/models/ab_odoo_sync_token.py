import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models

from .ab_odoo_sync_mapping_service import SyncAuthorizationError, SyncHardwareMismatchError
from .ab_odoo_sync_security import normalize_hdd_serial


class SyncTokenError(SyncAuthorizationError):
    def __init__(self, code="token_invalid", status=401):
        self.code = code
        self.status = status
        super().__init__(code)


class AbOdooSyncToken(models.Model):
    _name = "ab_odoo_sync_token"
    _description = "Branch Sync Token"
    _log_access = False

    digest = fields.Char(required=True, index=True, groups="base.group_system")
    branch_id = fields.Many2one("ab_odoo_sync_branch_registry", required=True, ondelete="cascade", index=True)
    expires_at = fields.Datetime(required=True, index=True)
    token_version = fields.Integer(required=True)
    scope = fields.Selection([("upload_health", "Upload and health")], required=True, default="upload_health")

    _unique_digest = models.Constraint("UNIQUE(digest)", "Token digest must be unique.")

    @api.model
    def _issue(self, branch):
        raw = self.env["ir.config_parameter"].sudo().get_param("ab_odoo_sync.token_ttl_seconds", "900")
        try:
            ttl = int(raw)
        except (TypeError, ValueError):
            ttl = 900
        if not 60 <= ttl <= 3600:
            ttl = 900
        token = secrets.token_urlsafe(32)
        expires = fields.Datetime.now() + timedelta(seconds=ttl)
        self.sudo().create({
            "digest": hashlib.sha256(token.encode("ascii")).hexdigest(),
            "branch_id": branch.id,
            "expires_at": expires,
            "token_version": branch.sync_token_version,
        })
        return {"ok": True, "access_token": token, "token_type": "Bearer", "expires_in": ttl,
                "expires_at": fields.Datetime.to_string(expires)}

    @api.model
    def _authenticate(self, token, payload):
        if not isinstance(token, str) or len(token) != 43 or not token.isascii():
            raise SyncTokenError()
        record = self.sudo().search([("digest", "=", hashlib.sha256(token.encode("ascii")).hexdigest())], limit=1)
        if not record or record.scope != "upload_health":
            raise SyncTokenError()
        branch = record.branch_id
        # Read current transaction state, never a process-local authorization cache.
        if not branch.active or record.token_version != branch.sync_token_version:
            raise SyncTokenError("token_revoked", 403)
        if record.expires_at <= fields.Datetime.now():
            raise SyncTokenError("token_expired")
        service = self.env["ab_odoo_sync_service"]
        if not isinstance(payload, dict) or service.parse_positive_int(payload.get("db_serial"), "db_serial") != branch.db_serial:
            raise SyncTokenError("branch_mismatch", 403)
        if branch.hardware_binding_state != "approved" or normalize_hdd_serial(payload.get("hdd_serial")) != branch.hdd_serial:
            raise SyncHardwareMismatchError()
        return branch

    @api.autovacuum
    def _gc_expired_tokens(self):
        self.sudo().search([("expires_at", "<", fields.Datetime.now())], limit=10000).unlink()
