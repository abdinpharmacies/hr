import re
import secrets
import time
from datetime import timedelta

from odoo import fields, models, _
from odoo.exceptions import AccessDenied
from odoo.http import request


DEVICE_COOKIE = "ab_storefront_trusted_browser"
DEVICE_AGE = 30 * 86400
LOGIN_AGE = 300


class AuthDevice(models.Model):
    _name = "ab_storefront_auth_device"
    _description = "Storefront Trusted Browser"
    _order = "create_date desc"

    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade", groups="base.group_system")
    name = fields.Char(required=True)
    token_hash = fields.Char(required=True, index=True, groups="base.group_system")
    credential_stamp = fields.Char(required=True, groups="base.group_system")
    expires_at = fields.Datetime(required=True, index=True)
    revoked_at = fields.Datetime(index=True)
    _unique_token = models.Constraint("UNIQUE(token_hash)", "Browser tokens must be unique.")


class AuthRecoveryCode(models.Model):
    _name = "ab_storefront_auth_recovery_code"
    _description = "Storefront Recovery Code"

    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade", groups="base.group_system")
    code_hash = fields.Char(required=True, index=True, groups="base.group_system")
    used_at = fields.Datetime(index=True)
    _unique_code = models.Constraint("UNIQUE(code_hash)", "Recovery codes must be unique.")


class AuthDeviceChallenge(models.Model):
    _inherit = "ab_storefront_auth_challenge"

    purpose = fields.Selection(selection_add=[("device_login", "Browser sign-in")], ondelete={"device_login": "cascade"})
    decision = fields.Selection([("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", required=True)
    browser_name = fields.Char(groups="base.group_system")
    source_ip = fields.Char(groups="base.group_system")
    approval_sent = fields.Boolean()


class AuthDeviceService(models.AbstractModel):
    _inherit = "ab_storefront_auth_service"

    def _device_lock(self, user):
        self._lock("device-user:" + str(user.id))

    def _trusted_device(self, user, token):
        Device = self.env["ab_storefront_auth_device"].sudo()
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            return Device.browse()
        device = Device.search(fields.Domain("user_id", "=", user.id) & fields.Domain("token_hash", "=", self._digest("device:" + token)) & fields.Domain("revoked_at", "=", False) & fields.Domain("expires_at", ">", fields.Datetime.now()), limit=1)
        if device and secrets.compare_digest(device.credential_stamp, self._credential_stamp(user)):
            return device
        return Device.browse()

    def _remember_browser(self, user, name):
        if not user._ab_device_protected():
            raise AccessDenied()
        self._device_lock(user)
        token = secrets.token_urlsafe(32)
        self.env["ab_storefront_auth_device"].sudo().create({
            "user_id": user.id, "name": str(name or _("Browser"))[:160],
            "token_hash": self._digest("device:" + token),
            "credential_stamp": self._credential_stamp(user),
            "expires_at": fields.Datetime.now() + timedelta(seconds=DEVICE_AGE),
        })
        return token

    def _revoke_browser(self, user, device_id=None):
        self._device_lock(user)
        domain = fields.Domain("user_id", "=", user.id) & fields.Domain("revoked_at", "=", False)
        if device_id is not None:
            domain &= fields.Domain("id", "=", device_id)
        self.env["ab_storefront_auth_device"].sudo().search(domain).write({"revoked_at": fields.Datetime.now()})

    def _invalidate_device_security(self, users, recovery_codes=True):
        for user in users.sorted("id"):
            self._device_lock(user)
        now = fields.Datetime.now()
        domain = fields.Domain("user_id", "in", users.ids)
        self.env["ab_storefront_auth_device"].sudo().search(domain & fields.Domain("revoked_at", "=", False)).write({"revoked_at": now})
        self.env["ab_storefront_auth_challenge"].sudo().search(domain & fields.Domain("purpose", "=", "device_login") & fields.Domain("used_at", "=", False)).write({"used_at": now})
        if recovery_codes:
            self.env["ab_storefront_auth_recovery_code"].sudo().search(domain & fields.Domain("used_at", "=", False)).write({"used_at": now})

    def _generate_recovery_codes(self, user):
        if not user._ab_device_protected():
            raise AccessDenied()
        self._device_lock(user)
        Code = self.env["ab_storefront_auth_recovery_code"].sudo()
        Code.search(fields.Domain("user_id", "=", user.id) & fields.Domain("used_at", "=", False)).write({"used_at": fields.Datetime.now()})
        codes = [secrets.token_hex(16).upper() for _index in range(8)]
        Code.create([{"user_id": user.id, "code_hash": self._digest("recovery-code:" + str(user.id) + ":" + code)} for code in codes])
        return ["-".join(code[index:index + 4] for index in range(0, 32, 4)) for code in codes]

    def _device_cooldown(self, user, ip, reject=False):
        key = self._digest("device-denial:" + str(user.id) + ":" + ip)
        self._lock(key)
        Rate = self.env["ab_storefront_auth_rate"].sudo()
        bucket = Rate.search(fields.Domain("key", "=", key), limit=1)
        now = fields.Datetime.now()
        if reject:
            count = bucket.count + 1 if bucket and bucket.expires_at > now else 1
            values = {"count": count, "expires_at": now + timedelta(seconds=min(900, 60 * 5 ** (min(count, 3) - 1)))}
            if bucket:
                bucket.write(values)
            else:
                Rate.create(dict(values, key=key))
            return True
        return bool(bucket and bucket.expires_at > now)

    def _new_device_login(self, user, browser, ip, name):
        if not user._ab_device_protected():
            raise AccessDenied()
        if not self._rate_allow("device-login-attempt-ip", ip, 30, 300):
            return False
        self._device_lock(user)
        challenge, token = self._new_challenge("device_login", user, browser, ttl=LOGIN_AGE)
        challenge.write({"browser_name": str(name)[:160], "source_ip": str(ip)[:64]})
        telegram = self._identities(user).filtered(lambda identity: identity.kind == "telegram")
        if self._device_cooldown(user, ip) or not telegram or not self._channel("telegram")._enabled():
            return token
        if not self._rate_allow("device-login-ip", ip, 20, 900):
            return token
        if not self._rate_allow("device-login-user", str(user.id), 3, 900):
            return token
        if not self._rate_allow("device-login-send", str(user.id), 1, 60):
            return token
        translated = self.with_context(lang=user.lang or "en_US").env
        challenge.write({"telegram_user_id": telegram.value, "telegram_chat_id": telegram.chat_id, "approval_sent": True})
        self._queue("telegram", {
            "chat_id": telegram.chat_id,
            "text": translated._("New sign-in to your Abdin Pharmacy account. Browser: %(browser)s. IP: %(ip)s. Time (UTC): %(time)s. Approve only if you just entered your password. This request expires in 5 minutes.", browser=challenge.browser_name, ip=challenge.source_ip, time=str(fields.Datetime.now())),
            "protect_content": True,
            "reply_markup": {"inline_keyboard": [[
                {"text": translated._("Approve sign-in"), "callback_data": "ab:a:" + token},
                {"text": translated._("Reject sign-in"), "callback_data": "ab:r:" + token},
            ]]},
        }, challenge)
        return token

    def _device_challenge(self, user, token, browser):
        self._device_lock(user)
        challenge = self._find(token, ["device_login"], browser)
        return challenge if challenge and challenge.user_id == user else challenge.browse()

    def _complete_device_login(self, user, token, browser, recovery_code=None):
        challenge = self._device_challenge(user, token, browser)
        if not challenge or challenge.decision == "rejected":
            return False
        if recovery_code is not None:
            if not self._rate_allow("device-recovery-source", str(user.id) + ":" + challenge.source_ip, 10, 900):
                return False
            challenge.write({"attempts": challenge.attempts + 1})
            if challenge.attempts > 5:
                challenge.write({"used_at": fields.Datetime.now()})
                return False
            code = re.sub(r"[-\s]", "", str(recovery_code)[:100]).upper()
            Code = self.env["ab_storefront_auth_recovery_code"].sudo()
            record = Code.search(fields.Domain("user_id", "=", user.id) & fields.Domain("used_at", "=", False) & fields.Domain("code_hash", "=", self._digest("recovery-code:" + str(user.id) + ":" + code)), limit=1) if re.fullmatch(r"[0-9A-F]{32}", code) else Code.browse()
            if not record:
                if challenge.attempts >= 5:
                    challenge.write({"used_at": fields.Datetime.now()})
                return False
            record.write({"used_at": fields.Datetime.now()})
            self._invalidate_device_security(user, recovery_codes=False)
        elif challenge.decision != "approved":
            return False
        challenge.write({"used_at": fields.Datetime.now()})
        return True

    def _process_device_callback(self, callback):
        sender = callback.get("from", {})
        message = callback.get("message", {})
        chat = message.get("chat", {}) if isinstance(message, dict) else {}
        data = callback.get("data", "")
        if not isinstance(sender, dict) or not isinstance(chat, dict) or sender.get("is_bot") or type(sender.get("id")) is not int or chat.get("type") != "private" or chat.get("id") != sender["id"]:
            return
        if not isinstance(data, str) or not re.fullmatch(r"ab:[ar]:[A-Za-z0-9_-]{43}", data):
            return
        token = data[5:]
        candidate = self.env["ab_storefront_auth_challenge"].sudo().search(fields.Domain("token_hash", "=", self._digest("token:" + token)) & fields.Domain("purpose", "=", "device_login"), limit=1)
        if not candidate:
            return
        user = candidate.user_id
        challenge = self._device_challenge(user, token, None)
        telegram = self._identities(user).filtered(lambda identity: identity.kind == "telegram")
        if not challenge or not self._channel("telegram")._enabled() or not challenge.approval_sent or challenge.decision != "pending" or not telegram or telegram.value != str(sender["id"]) or challenge.telegram_user_id != telegram.value or challenge.telegram_chat_id != str(chat["id"]):
            return
        approved = data[3] == "a"
        challenge.write({"decision": "approved" if approved else "rejected"})
        if not approved:
            self._device_cooldown(user, challenge.source_ip, reject=True)
        translated = self.with_context(lang=user.lang or "en_US").env
        self._queue("telegram", {"chat_id": telegram.chat_id, "text": translated._("Sign-in approved. Return to the requesting browser and continue.") if approved else translated._("Sign-in rejected. Your current sessions remain active. Change your password if this was not you.")})

    def _set_identity(self, user, kind, value, chat_id=None):
        old = self._identities(user).filtered(lambda identity: identity.kind == "telegram") if kind == "telegram" else False
        changed = bool(old and old.value != str(value))
        result = super()._set_identity(user, kind, value, chat_id)
        if changed:
            self._invalidate_device_security(user)
        return result


class ResUsers(models.Model):
    _inherit = "res.users"

    def _ab_device_protected(self):
        self.ensure_one()
        user = self.sudo()
        return bool(
            user.share
            and not user._is_public()
            and user.env["ab_storefront_auth_identity"].search_count(
                fields.Domain("user_id", "=", user.id)
                & fields.Domain("kind", "=", "telegram"),
                limit=1,
            )
        )

    def _rpc_api_keys_only(self):
        return self._ab_device_protected() or super()._rpc_api_keys_only()

    def _mfa_url(self):
        native = super()._mfa_url()
        return native or ("/ab_storefront/auth/device" if self._ab_device_protected() else None)

    def _login(self, credential, user_agent_env):
        result = super()._login(credential, user_agent_env)
        user = self.sudo().browse(result["uid"])
        if request and user._ab_device_protected() and user._mfa_url() == "/ab_storefront/auth/device":
            service = self.env["ab_storefront_auth_service"].sudo()
            browser = secrets.token_urlsafe(32)
            request.session.update(ab_device_browser=browser, ab_device_user=user.id, ab_device_stamp=service._credential_stamp(user), ab_device_token=False, ab_device_started=time.time())
            result = dict(result, mfa="default")
            if request.httprequest.environ.get("ab_storefront_verified_signup") != user.id and not service._trusted_device(user, request.cookies.get(DEVICE_COOKIE)):
                request.session["ab_device_token"] = service._new_device_login(user, browser, request.httprequest.remote_addr or "unknown", request.httprequest.user_agent.string)
        return result

    def write(self, values):
        result = super().write(values)
        if "password" in values or values.get("active") is False:
            self.env["ab_storefront_auth_service"].sudo()._invalidate_device_security(self, recovery_codes=values.get("active") is False)
        return result
