import secrets
import time

from odoo import fields, http, _
from odoo.exceptions import UserError
from odoo.http import request
from werkzeug.exceptions import Forbidden

from .auth_security import StorefrontAuthSecurity
from ..models.auth_device import DEVICE_AGE, DEVICE_COOKIE, LOGIN_AGE


class StorefrontAuthDevice(StorefrontAuthSecurity):
    def _mark_verified(self, user):
        request.session["ab_device_verified"] = {
            "uid": user.id, "stamp": self._service()._credential_stamp(user),
        }

    def _verified_session(self, user):
        proof = request.session.get("ab_device_verified") or {}
        return proof.get("uid") == user.id and secrets.compare_digest(proof.get("stamp", ""), self._service()._credential_stamp(user))

    def _remember_response(self, response, user):
        token = self._service()._remember_browser(user, request.httprequest.user_agent.string)
        response.set_cookie(DEVICE_COOKIE, token, max_age=DEVICE_AGE, secure=True, httponly=True, samesite="Lax", path="/")
        return response

    def _finish(self, user, remember=False):
        request.session.finalize(request.env)
        request.update_env(user=request.session.uid)
        request.update_context(**request.session.context)
        self._mark_verified(user)
        request.session.pop("ab_device_token", None)
        request.session.pop("ab_device_stamp", None)
        request.session.pop("ab_device_user", None)
        request.session.pop("ab_device_started", None)
        response = request.redirect("/my/authentication/browsers", 303)
        response.headers["Cache-Control"] = "no-store"
        return self._remember_response(response, user) if remember else response

    @http.route("/ab_storefront/auth/device", type="http", auth="public", website=True, sitemap=False, methods=["GET", "POST"], csrf=True)
    def device_login(self, **post):
        self._secure()
        if request.session.uid:
            return request.redirect("/my/authentication/browsers", 303)
        uid = request.session.get("pre_uid")
        if not uid or uid != request.session.get("ab_device_user"):
            return request.redirect("/web/login", 303)
        user = request.env["res.users"].sudo().browse(uid).exists()
        service = self._service()
        if not user or not user.active or not user._ab_device_protected() or time.time() - request.session.get("ab_device_started", 0) > LOGIN_AGE or not secrets.compare_digest(request.session.get("ab_device_stamp", ""), service._credential_stamp(user)):
            request.session.logout(keep_db=True)
            return request.redirect("/web/login", 303)
        trusted = service._trusted_device(user, request.cookies.get(DEVICE_COOKIE))
        if trusted:
            return self._finish(user)
        token = request.session.get("ab_device_token", "")
        browser = request.session.get("ab_device_browser", "")
        challenge = service._device_challenge(user, token, browser)
        values = {"error": False, "pending": bool(challenge and challenge.decision != "rejected"), "sent": bool(challenge and challenge.approval_sent)}
        if request.httprequest.method == "POST":
            action = post.get("action")
            if action == "cancel":
                if challenge:
                    challenge.write({"used_at": fields.Datetime.now()})
                request.session.logout(keep_db=True)
                return request.redirect("/web/login", 303)
            if action in {"continue", "recovery"}:
                code = post.get("recovery_code", "") if action == "recovery" else None
                allowed = service._rate_allow("device-check-ip", self._ip(), 60, 60)
                if allowed and service._complete_device_login(user, token, browser, code):
                    return self._finish(user, remember=post.get("remember") == "1")
                values["error"] = _("Sign-in has not been approved, or the request or recovery code is invalid. Try again or return to sign in.")
                challenge = service._device_challenge(user, token, browser)
                values["pending"] = bool(challenge and challenge.decision != "rejected")
        return self._render("auth_device_wait", values)

    @http.route("/my/authentication/browsers", type="http", auth="user", website=True, sitemap=False, methods=["GET", "POST"], csrf=True)
    def browsers(self, **post):
        self._secure()
        user = request.env.user
        if not user._ab_device_protected():
            return request.redirect("/my/authentication", 303)
        service = self._service()
        trusted = service._trusted_device(user, request.cookies.get(DEVICE_COOKIE))
        verified = self._verified_session(user) or bool(trusted) or user._mfa_url() != "/ab_storefront/auth/device"
        values = {"error": False, "message": False, "codes": [], "verified": verified}
        response = None
        if request.httprequest.method == "POST":
            try:
                self._confirm_password(user, post)
                action = post.get("action")
                if action == "verify":
                    request.session.authenticate(request.env, {"type": "password", "login": user.login, "password": post.get("current_password", "")})
                    return request.redirect(user._mfa_url() or "/my/authentication/browsers", 303)
                if not verified:
                    raise Forbidden()
                if action == "codes":
                    values["codes"] = service._generate_recovery_codes(user)
                elif action == "remember":
                    response = self._remember_response(request.redirect("/my/authentication/browsers", 303), user)
                elif action in {"revoke", "revoke_all"}:
                    try:
                        device_id = int(post.get("device_id", "")) if action == "revoke" else None
                    except ValueError:
                        raise Forbidden() from None
                    service._revoke_browser(user, device_id)
                    values["message"] = _("Browser trust revoked. A new sign-in will require verification.")
                    if action == "revoke_all" or (trusted and trusted.id == device_id):
                        response = request.redirect("/my/authentication/browsers", 303)
                        response.delete_cookie(DEVICE_COOKIE, path="/", secure=True, httponly=True, samesite="Lax")
            except UserError as error:
                values["error"] = error.args[0]
        if response:
            response.headers["Cache-Control"] = "no-store"
            return response
        devices = request.env["ab_storefront_auth_device"].sudo().search(fields.Domain("user_id", "=", user.id) & fields.Domain("revoked_at", "=", False) & fields.Domain("expires_at", ">", fields.Datetime.now()))
        values["devices"] = [{"id": device.id, "name": device.name, "expires_at": device.expires_at} for device in devices]
        values["code_count"] = request.env["ab_storefront_auth_recovery_code"].sudo().search_count(fields.Domain("user_id", "=", user.id) & fields.Domain("used_at", "=", False))
        return self._render("auth_device_management", values)
