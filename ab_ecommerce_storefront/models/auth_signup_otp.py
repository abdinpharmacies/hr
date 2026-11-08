import re
import secrets
import time

from odoo import fields, models, _
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request


SIGNUP_OTP_URL = "/ab_storefront/auth/signup-otp"
SIGNUP_SESSION_AGE = 900


class SignupOtpChallenge(models.Model):
    _inherit = "ab_storefront_auth_challenge"

    purpose = fields.Selection(selection_add=[("signup_otp", "First sign-in verification")], ondelete={"signup_otp": "cascade"})


class SignupOtpUsers(models.Model):
    _inherit = "res.users"

    ab_signup_otp_pending = fields.Boolean(
        string="First Sign-in Verification Required", default=False, copy=False,
        readonly=True, groups="base.group_system",
    )

    def _ab_needs_signup_otp(self):
        self.ensure_one()
        user = self.sudo()
        return bool(user.active and user._is_portal() and not user._is_internal() and "@" not in user.login and user.ab_signup_otp_pending)

    def _mfa_url(self):
        native = super()._mfa_url()
        return SIGNUP_OTP_URL if self._ab_needs_signup_otp() else native

    def _rpc_api_keys_only(self):
        return self._ab_needs_signup_otp() or super()._rpc_api_keys_only()

    def _login(self, credential, user_agent_env):
        result = super()._login(credential, user_agent_env)
        user = self.sudo().browse(result["uid"])
        if user._ab_needs_signup_otp():
            result = dict(result, mfa="default")
            if request:
                service = self.env["ab_storefront_auth_service"].sudo()
                request.session["ab_signup_otp"] = {
                    "uid": user.id, "browser": secrets.token_urlsafe(32),
                    "stamp": service._credential_stamp(user), "started": time.time(),
                }
        return result


class SignupOtpService(models.AbstractModel):
    _inherit = "ab_storefront_auth_service"

    def _signup_otp_destination(self, user):
        if not user._ab_needs_signup_otp():
            raise AccessDenied()
        telegram = self._identities(user).filtered(lambda identity: identity.kind == "telegram")
        if not telegram or not self._channel("telegram")._enabled():
            raise UserError(_("Telegram delivery is unavailable."))
        return "telegram", telegram.chat_id

    def _request_signup_otp(self, user, browser, ip):
        channel, destination = self._signup_otp_destination(user)
        if not browser:
            raise AccessDenied()
        self._lock("signup-otp-user:" + str(user.id))
        if not self._rate_allow("signup-otp-ip", ip, 20):
            raise UserError(_("Please wait before trying again."))
        if not self._rate_allow("signup-otp-send", str(user.id), 1, self._setting("resend_cooldown", 60, maximum=3600)):
            raise UserError(_("Please wait before trying again."))
        if not self._rate_allow("signup-otp-user", str(user.id)):
            raise UserError(_("Please wait before trying again."))
        domain = fields.Domain("user_id", "=", user.id) & fields.Domain("purpose", "=", "signup_otp") & fields.Domain("browser_hash", "=", self._digest("browser:" + browser)) & fields.Domain("used_at", "=", False)
        self.env["ab_storefront_auth_challenge"].sudo().search(domain).write({"used_at": fields.Datetime.now(), "code_hash": False})
        challenge, token = self._new_challenge("signup_otp", user, browser, destination, channel, ttl=self._setting("otp_expiration", 300, maximum=900))
        code = self._generate_otp(challenge, token)
        text = self.with_context(lang=user.lang or "en_US").env._("Your Abdin Pharmacy security code is: %s. Do not share it. It expires shortly.", code)
        payload = {"chat_id": destination, "text": text, "protect_content": True}
        self._queue(channel, payload, challenge)
        self._wake_delivery()
        return token

    def _verify_signup_otp(self, user, token, browser, code):
        if not browser or not user._ab_needs_signup_otp():
            return False
        self._lock("signup-otp-user:" + str(user.id))
        user.invalidate_recordset(["ab_signup_otp_pending"])
        if not user._ab_needs_signup_otp():
            return False
        challenge = self._find(token, ["signup_otp"], browser)
        if not challenge or challenge.user_id != user:
            return False
        channel, destination = self._signup_otp_destination(user)
        if challenge.channel != channel or challenge.value != destination:
            return False
        challenge.write({"attempts": challenge.attempts + 1})
        limit = self._setting("otp_max_attempts", 5, maximum=10)
        valid = isinstance(code, str) and bool(re.fullmatch(r"[0-9]{6}", code)) and secrets.compare_digest(challenge.code_hash or "", self._digest("otp:" + token + ":" + code))
        if challenge.attempts > limit or not valid:
            if challenge.attempts >= limit:
                challenge.write({"used_at": fields.Datetime.now(), "code_hash": False})
            return False
        user.sudo().write({"ab_signup_otp_pending": False})
        domain = fields.Domain("user_id", "=", user.id) & fields.Domain("purpose", "=", "signup_otp") & fields.Domain("used_at", "=", False)
        self.env["ab_storefront_auth_challenge"].sudo().search(domain).write({"used_at": fields.Datetime.now(), "code_hash": False})
        return True
