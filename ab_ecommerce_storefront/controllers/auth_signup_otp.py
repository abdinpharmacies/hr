import secrets
import time

from odoo import fields, http, _
from odoo.exceptions import UserError
from odoo.http import request

from .auth_device import StorefrontAuthDevice
from ..models.auth_signup_otp import SIGNUP_OTP_URL, SIGNUP_SESSION_AGE


class StorefrontSignupOtp(StorefrontAuthDevice):
    @http.route(SIGNUP_OTP_URL, type="http", auth="public", website=True, sitemap=False, methods=["GET", "POST"], csrf=True)
    def signup_otp(self, **post):
        self._secure()
        if request.session.uid:
            return request.redirect("/my/home", 303)
        state = dict(request.session.get("ab_signup_otp") or {})
        uid = request.session.get("pre_uid")
        if not uid or state.get("uid") != uid:
            return request.redirect("/web/login", 303)
        service = self._service()
        user = request.env["res.users"].sudo().browse(uid).exists()
        if not user or not user._ab_needs_signup_otp() or time.time() - state.get("started", 0) > SIGNUP_SESSION_AGE or not secrets.compare_digest(state.get("stamp", ""), service._credential_stamp(user)):
            request.session.logout(keep_db=True)
            return request.redirect("/web/login", 303)
        values = {"error": False, "message": False}
        token = state.get("token", "")
        browser = state.get("browser", "")
        try:
            if request.httprequest.method == "POST":
                action = post.get("action")
                if action == "cancel":
                    challenge = service._find(token, ["signup_otp"], browser)
                    if challenge and challenge.user_id == user:
                        challenge.write({"used_at": fields.Datetime.now(), "code_hash": False})
                    request.session.logout(keep_db=True)
                    return request.redirect("/web/login", 303)
                if action == "verify":
                    allowed = service._rate_allow("signup-otp-verify-ip", self._ip(), 60)
                    if allowed and service._verify_signup_otp(user, token, browser, post.get("code", "")):
                        request.session.pop("ab_signup_otp", None)
                        next_mfa = user._mfa_url()
                        if next_mfa and next_mfa != "/ab_storefront/auth/device":
                            return request.redirect(next_mfa, 303)
                        if user._ab_device_protected():
                            return self._finish(user)
                        request.session.finalize(request.env)
                        request.update_env(user=request.session.uid)
                        request.update_context(**request.session.context)
                        response = request.redirect("/my/home", 303)
                        response.headers["Cache-Control"] = "no-store"
                        return response
                    values["error"] = _("The code or link is invalid or expired.")
                elif action == "resend":
                    state["token"] = service._request_signup_otp(user, browser, self._ip())
                    request.session["ab_signup_otp"] = state
                    values["message"] = _("A new verification code has been queued for delivery.")
            elif not token:
                state["token"] = service._request_signup_otp(user, browser, self._ip())
                request.session["ab_signup_otp"] = state
        except UserError as error:
            values["error"] = error.args[0]
        return self._render("auth_signup_otp", values)
