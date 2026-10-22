import hashlib
import base64
import json
import re
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessDenied
from odoo.tools import consteq, hmac


class EcommerceApiSession(models.Model):
    _name = "ab_ecommerce_api_session"
    _description = "Storefront API Session"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    website_id = fields.Many2one("website", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="website_id.company_id", store=True)
    access_hash = fields.Char(required=True, index=True, groups="base.group_system")
    refresh_hash = fields.Char(required=True, index=True, groups="base.group_system")
    credential_stamp = fields.Char(required=True, groups="base.group_system")
    expires_at = fields.Datetime(required=True)
    refresh_expires_at = fields.Datetime(required=True)
    revoked = fields.Boolean(default=False)
    revoked_at = fields.Datetime()
    revocation_reason = fields.Selection([
        ("logout", "Logout"),
        ("logout_all", "Logout All"),
        ("device_revoked", "Device Revoked"),
        ("refresh_reuse", "Refresh Token Reuse"),
        ("credentials_changed", "Credentials Changed"),
        ("expired", "Expired"),
    ])
    device_name = fields.Char()
    generation = fields.Integer(default=0, required=True)
    last_used_at = fields.Datetime(default=fields.Datetime.now, required=True)
    last_refreshed_at = fields.Datetime(default=fields.Datetime.now, required=True)
    cart_id = fields.Many2one("sale.order", ondelete="restrict")

    _access_unique = models.Constraint("UNIQUE(access_hash)", "Access tokens must be unique.")
    _refresh_unique = models.Constraint("UNIQUE(refresh_hash)", "Refresh tokens must be unique.")

    @api.model
    def _hash(self, token):
        return hashlib.sha256(token.encode()).hexdigest()

    def _public_id(self):
        self.ensure_one()
        sudo_env = self.env["ir.config_parameter"].sudo().env
        signature = hmac(sudo_env, "ab_ecommerce_api_session", self.id)
        return f"{self.id}.{signature[:32]}"

    @api.model
    def _from_public_id(self, public_id):
        if not isinstance(public_id, str) or not re.fullmatch(r"[1-9][0-9]*\.[0-9a-f]{32}", public_id):
            return self.browse()
        record_id, supplied_signature = public_id.split(".", 1)
        session = self.sudo().browse(int(record_id)).exists()
        if not session:
            return session
        expected_signature = session._public_id().split(".", 1)[1]
        return session if consteq(supplied_signature, expected_signature) else self.browse()

    @api.model
    def _assert_customer(self, user, website):
        if (not user.active or not user._is_portal() or user._is_internal()
                or user._is_public() or website.company_id not in user.company_ids
                or (user.website_id and user.website_id != website)):
            raise AccessDenied()

    @api.model
    def _issue(self, user, website, device_name=""):
        self._assert_customer(user, website)
        service = self.env["ab_storefront_auth_service"]
        service._lock(f"api-sessions:{website.id}:{user.id}")
        excess_sessions = self.sudo().search([
            ("user_id", "=", user.id),
            ("website_id", "=", website.id),
            ("revoked", "=", False),
            ("refresh_expires_at", ">", fields.Datetime.now()),
        ], order="last_used_at desc, id desc", offset=19)
        if excess_sessions:
            excess_sessions._revoke("device_revoked")
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        now = fields.Datetime.now()
        session = self.sudo().create({
            "user_id": user.id, "website_id": website.id,
            "access_hash": self._hash(access), "refresh_hash": self._hash(refresh),
            "credential_stamp": service._credential_stamp(user),
            "expires_at": now + timedelta(minutes=15),
            "refresh_expires_at": now + timedelta(days=30),
            "device_name": device_name[:100],
        })
        return session, {"access_token": access, "refresh_token": refresh,
                         "token_type": "Bearer", "expires_in": 900,
                         "refresh_expires_in": 30 * 24 * 60 * 60}

    @api.model
    def _resolve(self, token, website, refresh=False):
        if not isinstance(token, str) or not 40 <= len(token) <= 128:
            raise AccessDenied()
        field = "refresh_hash" if refresh else "access_hash"
        token_hash = self._hash(token)
        session = self.sudo().search([
            (field, "=", token_hash), ("website_id", "=", website.id),
            ("revoked", "=", False),
        ], limit=1)
        if refresh and session:
            session = session.try_lock_for_update(allow_referencing=True)
            session.invalidate_recordset()
        now = fields.Datetime.now()
        if (not session or session.revoked or session[field] != token_hash
                or session.refresh_expires_at <= now
                or (not refresh and session.expires_at <= now)):
            raise AccessDenied()
        self._assert_customer(session.user_id, website)
        stamp = self.env["ab_storefront_auth_service"]._credential_stamp(session.user_id)
        if not secrets.compare_digest(session.credential_stamp, stamp):
            raise AccessDenied()
        if not refresh and (not session.last_used_at or session.last_used_at < now - timedelta(minutes=5)):
            session.sudo().write({"last_used_at": now})
        return session

    @api.model
    def _rotate(self, token, website):
        if not isinstance(token, str) or not 40 <= len(token) <= 128:
            raise AccessDenied()
        token_hash = self._hash(token)
        session = self.sudo().search([
            ("refresh_hash", "=", token_hash),
            ("website_id", "=", website.id),
        ], limit=1)
        if not session:
            return self._handle_refresh_reuse(token_hash, website)
        session = session.try_lock_for_update(allow_referencing=True)
        session.invalidate_recordset()
        if not session or session.refresh_hash != token_hash:
            return self._handle_refresh_reuse(token_hash, website)
        now = fields.Datetime.now()
        if session.revoked:
            return False
        if session.refresh_expires_at <= now:
            session._revoke("expired")
            return False
        self._assert_customer(session.user_id, website)
        stamp = self.env["ab_storefront_auth_service"]._credential_stamp(session.user_id)
        if not secrets.compare_digest(session.credential_stamp, stamp):
            session._revoke("credentials_changed")
            return False
        self.env["ab_ecommerce_api_refresh_token"].sudo().create({
            "session_id": session.id,
            "token_hash": token_hash,
            "expires_at": session.refresh_expires_at,
        })
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        session.write({"access_hash": self._hash(access), "refresh_hash": self._hash(refresh),
                       "expires_at": now + timedelta(minutes=15),
                       "generation": session.generation + 1,
                       "last_used_at": now, "last_refreshed_at": now})
        return {"access_token": access, "refresh_token": refresh,
                "token_type": "Bearer", "expires_in": 900,
                "refresh_expires_in": max(0, int((session.refresh_expires_at - now).total_seconds()))}

    @api.model
    def _handle_refresh_reuse(self, token_hash, website):
        history = self.env["ab_ecommerce_api_refresh_token"].sudo().search([
            ("token_hash", "=", token_hash),
            ("website_id", "=", website.id),
        ], limit=1)
        if not history:
            raise AccessDenied()
        session = history.session_id.try_lock_for_update(allow_referencing=True)
        session.invalidate_recordset()
        if session and not session.revoked:
            session._revoke("refresh_reuse")
        return False

    def _revoke(self, reason):
        now = fields.Datetime.now()
        self.sudo().write({"revoked": True, "revoked_at": now, "revocation_reason": reason})

    @api.autovacuum
    def _gc_sessions(self):
        cutoff = fields.Datetime.now() - timedelta(days=7)
        expired = fields.Domain("refresh_expires_at", "<", cutoff)
        revoked = fields.Domain("revoked", "=", True) & (
            fields.Domain("revoked_at", "<", cutoff)
            | (fields.Domain("revoked_at", "=", False) & fields.Domain("write_date", "<", cutoff))
        )
        self.sudo().search(expired | revoked, limit=10000).unlink()


class EcommerceApiRefreshToken(models.Model):
    _name = "ab_ecommerce_api_refresh_token"
    _description = "Storefront API Used Refresh Token"

    session_id = fields.Many2one("ab_ecommerce_api_session", required=True, ondelete="cascade", index=True)
    website_id = fields.Many2one(related="session_id.website_id", store=True)
    company_id = fields.Many2one(related="session_id.company_id", store=True)
    token_hash = fields.Char(required=True, index=True, groups="base.group_system")
    used_at = fields.Datetime(required=True, default=fields.Datetime.now)
    expires_at = fields.Datetime(required=True, index=True)

    _token_hash_unique = models.Constraint("UNIQUE(token_hash)", "Used refresh tokens must be unique.")

    @api.autovacuum
    def _gc_refresh_tokens(self):
        cutoff = fields.Datetime.now() - timedelta(days=1)
        self.sudo().search([("expires_at", "<", cutoff)], limit=10000).unlink()


class EcommerceApiIdempotency(models.Model):
    _name = "ab_ecommerce_api_idempotency"
    _description = "Storefront API Idempotency Record"

    session_id = fields.Many2one("ab_ecommerce_api_session", required=True, ondelete="cascade", index=True)
    website_id = fields.Many2one(related="session_id.website_id", store=True)
    company_id = fields.Many2one(related="session_id.company_id", store=True)
    operation = fields.Char(required=True, index=True)
    key_hash = fields.Char(required=True, groups="base.group_system")
    request_hash = fields.Char(required=True, groups="base.group_system")
    response_json = fields.Text(groups="base.group_system")
    expires_at = fields.Datetime(required=True, default=lambda self: fields.Datetime.now() + timedelta(days=1), index=True)

    _request_unique = models.Constraint(
        "UNIQUE(session_id, operation, key_hash)",
        "An idempotency key can be used once per operation and session.",
    )

    @api.model
    def _fingerprint(self, payload):
        return hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
        ).encode()).hexdigest()

    @api.model
    def _begin(self, key, operation, session, payload):
        key_hash = self.env["ab_ecommerce_api_session"]._hash(key)
        request_hash = self._fingerprint(payload)
        record = self.sudo().search([
            ("session_id", "=", session.id),
            ("operation", "=", operation),
            ("key_hash", "=", key_hash),
        ], limit=1)
        now = fields.Datetime.now()
        if record and record.expires_at <= now:
            record.write({"request_hash": request_hash, "response_json": False,
                          "expires_at": now + timedelta(days=1)})
            return record, None, False
        if record and not consteq(record.request_hash, request_hash):
            return record, None, True
        if record and record.response_json:
            return record, json.loads(record.response_json), False
        if not record:
            record = self.sudo().create({
                "session_id": session.id,
                "operation": operation,
                "key_hash": key_hash,
                "request_hash": request_hash,
            })
        return record, None, False

    def _complete(self, response):
        self.sudo().write({"response_json": json.dumps(
            response, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
        )})

    @api.autovacuum
    def _gc_idempotency(self):
        cutoff = fields.Datetime.now() - timedelta(days=1)
        self.sudo().search([("expires_at", "<", cutoff)], limit=10000).unlink()


class EcommerceApiBrowserGrant(models.Model):
    _name = "ab_ecommerce_api_browser_grant"
    _description = "Storefront API Browser Authorization"

    token_hash = fields.Char(required=True, index=True, groups="base.group_system")
    code_challenge = fields.Char(required=True, groups="base.group_system")
    website_id = fields.Many2one("website", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="website_id.company_id", store=True)
    user_id = fields.Many2one("res.users", ondelete="cascade")
    expires_at = fields.Datetime(required=True)
    used = fields.Boolean(default=False)

    _token_unique = models.Constraint("UNIQUE(token_hash)", "Authorization tokens must be unique.")

    @api.model
    def _start(self, challenge, website):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", challenge):
            raise AccessDenied()
        token = secrets.token_urlsafe(32)
        self.sudo().create({"token_hash": self.env["ab_ecommerce_api_session"]._hash(token),
                            "code_challenge": challenge, "website_id": website.id,
                            "expires_at": fields.Datetime.now() + timedelta(minutes=5)})
        return token

    @api.model
    def _find(self, token, website):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise AccessDenied()
        record = self.sudo().search([
            ("token_hash", "=", self.env["ab_ecommerce_api_session"]._hash(token)),
            ("website_id", "=", website.id), ("used", "=", False),
            ("expires_at", ">", fields.Datetime.now()),
        ], limit=1)
        if not record:
            raise AccessDenied()
        record = record.try_lock_for_update(allow_referencing=True)
        record.invalidate_recordset()
        if not record or record.used or record.expires_at <= fields.Datetime.now():
            raise AccessDenied()
        return record

    @api.model
    def _approve(self, token, website, user):
        self.env["ab_ecommerce_api_session"]._assert_customer(user, website)
        record = self._find(token, website)
        if record.user_id and record.user_id != user:
            raise AccessDenied()
        record.user_id = user

    @api.model
    def _exchange(self, token, verifier, website):
        if not isinstance(verifier, str) or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
            raise AccessDenied()
        record = self._find(token, website)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        if not secrets.compare_digest(challenge, record.code_challenge):
            raise AccessDenied()
        if not record.user_id:
            return {"authorization_pending": True}
        session, tokens = self.env["ab_ecommerce_api_session"]._issue(record.user_id, website)
        record.used = True
        return tokens

    @api.autovacuum
    def _gc_browser_grants(self):
        cutoff = fields.Datetime.now() - timedelta(days=1)
        stale = fields.Domain("expires_at", "<", cutoff) | (
            fields.Domain("used", "=", True) & fields.Domain("write_date", "<", cutoff)
        )
        self.sudo().search(stale, limit=10000).unlink()
