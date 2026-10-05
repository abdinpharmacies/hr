import json
import secrets
from urllib.parse import urlparse

from odoo import http, _
from odoo.exceptions import UserError, ValidationError
from odoo.exceptions import AccessDenied
from odoo.http import request
from werkzeug.exceptions import Forbidden, NotFound

from ..models.auth_channels import deployment_secret
from .auth import validate_storefront_password


class StorefrontAuthSecurity(http.Controller):
    def _service(self):
        return request.env["ab_storefront_auth_service"].sudo()

    def _browser(self):
        if not request.session.get("ab_auth_browser"):
            request.session["ab_auth_browser"] = secrets.token_urlsafe(32)
        return request.session["ab_auth_browser"]

    def _ip(self):
        return request.httprequest.remote_addr or "unknown"

    def _secure(self):
        service = self._service()
        hostname = urlparse(request.httprequest.host_url).hostname
        local_development = service._development_http_allowed(hostname) and service._development_http_allowed(self._ip())
        if not request.httprequest.is_secure and not local_development:
            raise Forbidden(response=request.make_response("", status=403, headers={"X-Ab-Auth-Error": "https-required", "Cache-Control": "no-store"}))

    def _render(self, template, values):
        values["ab_auth_security"] = True
        response = request.render("ab_ecommerce_storefront." + template, values)
        response.headers.update({"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY", "Content-Security-Policy": "frame-ancestors 'none'"})
        return response

    def _password(self, post):
        password = post.get("password", "")
        if len(password) > 4096 or not validate_storefront_password(password):
            raise ValidationError(_("Use at least 8 characters with uppercase, lowercase, number, and special symbol."))
        if password != post.get("confirm_password"):
            raise ValidationError(_("Passwords do not match; please retype them."))
        return password

    def _confirm_password(self, user, post):
        if not self._service()._rate_allow("link-password", str(user.id), 10):
            raise ValidationError(_("Please wait before trying again."))
        try:
            if len(post.get("current_password", "")) > 4096:
                raise AccessDenied()
            user.with_user(user)._check_credentials({"type": "password", "password": post.get("current_password", "")}, {"interactive": True})
        except AccessDenied:
            raise ValidationError(_("The current password is incorrect.")) from None

    @http.route("/ab_storefront/auth/recover", type="http", auth="public", website=True, sitemap=False, methods=["GET", "POST"], csrf=True)
    def recover(self, **post):
        self._secure()
        if request.env["ir.config_parameter"].sudo().get_param("auth_signup.reset_password", "False") != "True":
            raise NotFound()
        service = self._service()
        browser = self._browser()
        values = {"step": "request", "error": False, "message": False, "telegram_enabled": service._channel("telegram")._enabled()}
        if request.session.uid:
            values["available_channels"] = service._available_channels(request.env.user)
        else:
            values["available_channels"] = ["email"] + (["telegram"] if values["telegram_enabled"] else [])
        if request.httprequest.method == "POST":
            action = post.get("action", "request")
            try:
                if action == "request":
                    channel = post.get("channel", "email")
                    token = service._request_recovery(channel, post.get("identifier", ""), browser, self._ip())
                    if token or channel != "telegram":
                        request.session["ab_auth_otp"] = token if channel == "telegram" else False
                    request.session["ab_auth_recovery_identifier"] = post.get("identifier", "")[:254]
                    request.session["ab_auth_recovery_channel"] = channel
                    values["message"] = _("If an eligible account exists, you will receive recovery instructions shortly.")
                    values["step"] = "otp" if channel == "telegram" else "sent"
                elif action == "resend":
                    channel = request.session.get("ab_auth_recovery_channel", "email")
                    token = service._request_recovery(channel, request.session.get("ab_auth_recovery_identifier", ""), browser, self._ip())
                    if token and channel == "telegram":
                        request.session["ab_auth_otp"] = token
                    values["message"] = _("If an eligible account exists, you will receive recovery instructions shortly.")
                    values["step"] = "otp" if channel == "telegram" else "sent"
                elif action in {"otp", "email"}:
                    if not service._rate_allow("verify-ip", self._ip(), 60):
                        raise ValidationError(_("Please wait before trying again."))
                    token = request.session.get("ab_auth_otp", "") if action == "otp" else post.get("proof", "")
                    grant = service._verify_recovery(token, browser, post.get("code", "") if action == "otp" else None)
                    if not grant:
                        values["step"] = "otp" if action == "otp" else "request"
                        raise ValidationError(_("The code or link is invalid or expired."))
                    request.session["ab_auth_grant"] = grant
                    values["step"] = "password"
                elif action == "password":
                    values["step"] = "password"
                    password = self._password(post)
                    if not service._reset_password(request.session.get("ab_auth_grant", ""), browser, password):
                        values["step"] = "request"
                        raise ValidationError(_("The code or link is invalid or expired."))
                    request.session.logout(keep_db=True)
                    values.update(step="done", message=_("Your password has been reset successfully."))
            except (UserError, ValidationError) as error:
                if action in {"request", "resend"}:
                    channel = post.get("channel") if action == "request" else request.session.get("ab_auth_recovery_channel", "email")
                    values.update(step="otp" if channel == "telegram" else "sent", message=_("If an eligible account exists, you will receive recovery instructions shortly."))
                else:
                    values["error"] = error.args[0]
        return self._render("auth_recovery", values)

    @http.route("/ab_storefront/auth/confirm", type="http", auth="public", website=True, sitemap=False, methods=["GET", "POST"], csrf=True)
    def confirm_email(self, **post):
        self._secure()
        values = {"done": False, "error": False}
        if request.httprequest.method == "POST":
            try:
                values["done"] = self._service()._rate_allow("confirm-ip", self._ip(), 60) and self._service()._confirm_email(post.get("proof", ""))
                if not values["done"]:
                    values["error"] = _("The code or link is invalid or expired.")
            except (UserError, ValidationError):
                values["error"] = _("The code or link is invalid or expired.")
        return self._render("auth_email_confirm", values)

    @http.route("/ab_storefront/auth/phone", type="http", auth="public", website=True, sitemap=False, methods=["GET", "POST"], csrf=True)
    def phone(self, **post):
        self._secure()
        service = self._service()
        browser = self._browser()
        user = request.env.user if request.session.uid else None
        if user and not user.share:
            raise Forbidden()
        values = {
            "link": request.session.get("ab_auth_deep_link"),
            "verified": False,
            "error": False,
            "phone": request.session.get("ab_auth_phone", ""),
            "telegram_id": False,
            "name": request.session.get("ab_auth_signup_name", ""),
            "telegram_auto_opened": bool(request.session.get("ab_auth_telegram_auto_open")) and not user,
            "toast_message": False,
            "toast_type": "info",
            "retry_after": 0,
            "verified_message": False,
        }
        token = request.session.get("ab_auth_link", "")
        challenge = service._find(token, ["link", "phone_signup"], browser)
        values["verified"] = bool(challenge and challenge.phone_verified)
        values["telegram_id"] = challenge.telegram_user_id if challenge else False
        if values["verified"]:
            values["verified_message"] = (
                _("Phone verification completed successfully. Confirm your Telegram connection.")
                if user
                else _("Phone verification completed successfully. Complete your details to create your account.")
            )
        if request.httprequest.method == "GET" and post.get("check") == "1":
            if values["verified"]:
                values.update(toast_message=values["verified_message"], toast_type="success")
            elif challenge and challenge.telegram_user_id:
                values.update(
                    toast_message=_("Telegram is connected, but the phone number is not verified yet. In Telegram, share your own phone number and try again."),
                    toast_type="warning",
                )
            elif challenge:
                values.update(
                    toast_message=_("Telegram has not responded yet. Open Telegram, press Start, share your own phone number, and try again."),
                    toast_type="warning",
                )
            else:
                values.update(
                    toast_message=_("This verification request is invalid or expired. Start Telegram verification again."),
                    toast_type="error",
                )
        if request.httprequest.method == "POST":
            try:
                action = post.get("action", "link")
                if action == "link":
                    if user:
                        self._confirm_password(user, post)
                    token, url = service._request_link(user, post.get("phone", ""), browser, self._ip())
                    request.session.update(
                        ab_auth_link=token,
                        ab_auth_deep_link=url,
                        ab_auth_phone=post.get("phone", "")[:30],
                        ab_auth_telegram_auto_open=False,
                    )
                    values.update(
                        link=url,
                        verified=False,
                        phone=post.get("phone", ""),
                        telegram_auto_opened=False,
                        toast_message=_("Verification request created. Open Telegram and complete the steps."),
                        toast_type="info",
                    )
                elif action == "finish" and user:
                    with request.env.cr.savepoint():
                        if not service._finish_link(token, browser, user):
                            raise ValidationError(_("Complete Telegram phone verification first."))
                    request.session["ab_auth_link"] = False
                    request.session["ab_auth_deep_link"] = False
                    request.session.pop("ab_auth_telegram_auto_open", None)
                    request.session.pop("ab_auth_signup_name", None)
                    return request.redirect("/my/authentication", 303)
                elif action == "signup" and not user:
                    password = self._password(post)
                    name = post.get("name", "").strip()[:100]
                    if not name:
                        raise ValidationError(_("Please fill in this field."))
                    with request.env.cr.savepoint():
                        user = service._finish_phone_signup(token, browser, {"name": name, "password": password, "lang": request.env.lang})
                    request.env.cr.commit()
                    request.session.authenticate(request.env, {"login": user.login, "password": password, "type": "password"})
                    request.session["ab_auth_link"] = False
                    request.session["ab_auth_deep_link"] = False
                    request.session.pop("ab_auth_telegram_auto_open", None)
                    request.session.pop("ab_auth_signup_name", None)
                    return request.redirect("/my/authentication", 303)
            except (UserError, ValidationError) as error:
                values["error"] = error.args[0]
                values["retry_after"] = getattr(error, "retry_after", 0)
        values["signed_in"] = bool(request.session.uid)
        return self._render("auth_phone_link", values)

    @http.route(["/my/authentication", "/authentication"], type="http", auth="user", website=True, sitemap=False, methods=["GET", "POST"], csrf=True)
    def account_security(self, **post):
        self._secure()
        user = request.env.user
        if not user.share:
            raise Forbidden()
        service = self._service()
        values = {"error": False, "message": False}
        if request.httprequest.method == "POST":
            try:
                self._confirm_password(user, post)
                if not service._request_email_verification(user, post.get("email", ""), self._browser(), self._ip()):
                    raise ValidationError(_("Please wait before trying again."))
                values["message"] = _("Check your email to verify your address.")
            except (UserError, ValidationError) as error:
                values["error"] = error.args[0]
        identities = service._identities(user)
        values["identities"] = {identity.kind: identity.value for identity in identities}
        values["channels"] = service._available_channels(user)
        values["telegram_enabled"] = service._channel("telegram")._enabled()
        return self._render("auth_account_security", values)

    @http.route("/ab_storefront/auth/telegram/webhook", type="http", auth="public", methods=["POST"], csrf=False, save_session=False)
    def telegram_webhook(self, **kwargs):
        self._secure()
        expected = deployment_secret("AB_STOREFRONT_TELEGRAM_WEBHOOK_SECRET")
        actual = request.httprequest.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not expected or not secrets.compare_digest(actual, expected) or not self._service()._channel("telegram")._enabled():
            raise Forbidden()
        if request.httprequest.content_length is None or request.httprequest.content_length > 16384:
            return request.make_json_response({"ok": False}, status=413)
        try:
            update = json.loads(request.httprequest.get_data())
            if not isinstance(update, dict) or not self._service()._ingest_update(update):
                raise ValueError
        except (ValueError, TypeError):
            return request.make_json_response({"ok": False}, status=400)
        return request.make_json_response({"ok": True})
