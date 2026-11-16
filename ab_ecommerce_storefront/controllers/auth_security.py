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
        lookup = service._find(request.session.get("ab_auth_lookup", ""), ["lookup"], browser)
        if request.session.uid:
            if not service._eligible_customer(request.env.user):
                raise Forbidden()
            if not lookup or lookup.user_id != request.env.user:
                token = service._lookup_recovery("", browser, self._ip(), request.env.user)
                request.session["ab_auth_lookup"] = token
                lookup = service._find(token, ["lookup"], browser)
        values = {"step": "choose" if lookup else "request", "error": False, "message": False,
                  "available_channels": service._available_channels(lookup.user_id) if lookup else [],
                  "telegram_enabled": service._channel("telegram")._enabled()}
        if request.httprequest.method == "GET":
            grant = service._find(request.session.get("ab_auth_grant", ""), ["grant"], browser)
            attempt = service._find(request.session.get("ab_auth_otp", ""), ["otp", "email_reset"], browser)
            if grant:
                values["step"] = "password"
            elif attempt:
                values["step"] = "sent" if attempt.channel == "email" else "otp"
        if request.httprequest.method == "POST":
            action = post.get("action", "identify")
            try:
                if action == "identify":
                    service._invalidate_recovery(browser)
                    request.session.pop("ab_auth_grant", None)
                    token = service._lookup_recovery(post.get("identifier", ""), browser, self._ip(),
                                                     request.env.user if request.session.uid else None)
                    request.session["ab_auth_lookup"] = token
                    lookup = service._find(token, ["lookup"], browser)
                    values.update(step="choose", available_channels=service._available_channels(lookup.user_id) if lookup else [])
                elif action in {"request", "resend", "switch"}:
                    if not lookup or (request.session.uid and lookup.user_id != request.env.user):
                        raise ValidationError(_("The code or link is invalid or expired."))
                    channels = service._available_channels(lookup.user_id)
                    values.update(step="choose", available_channels=channels)
                    if action == "switch":
                        service._invalidate_recovery(browser)
                        request.session.pop("ab_auth_otp", None)
                        request.session.pop("ab_auth_grant", None)
                    else:
                        channel = request.session.get("ab_auth_recovery_channel") if action == "resend" else post.get("channel")
                        if channel not in channels:
                            raise ValidationError(_("Invalid recovery channel."))
                        destination = service._recovery_destination(lookup.user_id, channel)
                        if action == "resend" and destination != request.session.get("ab_auth_recovery_destination"):
                            raise ValidationError(_("The code or link is invalid or expired."))
                        if action == "request":
                            request.session["ab_auth_recovery_destination"] = destination
                            service._invalidate_recovery(browser)
                            request.session.pop("ab_auth_grant", None)
                            request.session.pop("ab_auth_otp", None)
                        token = service._request_recovery(channel, lookup.user_id.login, browser, self._ip())
                        if token:
                            request.session["ab_auth_otp"] = token
                        request.session["ab_auth_recovery_channel"] = channel
                        values.update(step="sent" if channel == "email" else "otp",
                                      message=_("If an eligible account exists, you will receive recovery instructions shortly."))
                elif action in {"otp", "email"}:
                    values["step"] = "otp" if action == "otp" else "request"
                    if not service._rate_allow("verify-ip", self._ip(), 60):
                        raise ValidationError(_("Please wait before trying again."))
                    token = request.session.get("ab_auth_otp", "") if action == "otp" else post.get("proof", "")
                    grant = service._verify_recovery(token, browser, post.get("code", "") if action == "otp" else None)
                    if not grant:
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
                else:
                    raise Forbidden()
            except (UserError, ValidationError) as error:
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
            "phone": request.session.get("ab_auth_phone", "") or (user.phone if user else ""),
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
        if not challenge:
            values["link"] = False
            request.session.pop("ab_auth_deep_link", None)
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
                    from .auth_device import StorefrontAuthDevice
                    StorefrontAuthDevice()._mark_verified(user)
                    return request.redirect("/my/authentication", 303)
                elif action == "signup" and not user:
                    password = self._password(post)
                    name = post.get("name", "").strip()[:100]
                    if not name:
                        raise ValidationError(_("Please fill in this field."))
                    with request.env.cr.savepoint():
                        user = service._finish_phone_signup(token, browser, {"name": name, "password": password, "lang": request.env.lang})
                    request.env.cr.commit()
                    request.httprequest.environ["ab_storefront_verified_signup"] = user.id
                    request.session.authenticate(request.env, {"login": user.login, "password": password, "type": "password"})
                    request.session["ab_auth_link"] = False
                    request.session["ab_auth_deep_link"] = False
                    request.session.pop("ab_auth_telegram_auto_open", None)
                    request.session.pop("ab_auth_signup_name", None)
                    from .auth_device import StorefrontAuthDevice
                    device = StorefrontAuthDevice()
                    if user._ab_needs_signup_otp():
                        return request.redirect(user._mfa_url(), 303)
                    if request.session.get("pre_uid") == user.id:
                        return device._finish(user, remember=post.get("remember") == "1")
                    device._mark_verified(user)
                    return request.redirect("/my/authentication/browsers", 303)
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
        values["contact_status"] = service._profile_contact_status(user)
        values["social_contacts"] = service._social_contacts(user)
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
            if not isinstance(update, dict) or not self._service()._ingest_update(update, wake_delivery=True):
                raise ValueError
        except (ValueError, TypeError):
            return request.make_json_response({"ok": False}, status=400)
        return request.make_json_response({"ok": True})
