import logging
import re
import base64

import werkzeug
from odoo import _, http
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.auth_oauth.controllers.main import OAuthLogin
from odoo.addons.web.controllers.home import (
    SIGN_UP_REQUEST_PARAMS,
)
from odoo.addons.web.models.res_users import SKIP_CAPTCHA_LOGIN
from odoo.exceptions import UserError
from odoo.http import request
from werkzeug.urls import url_encode
from ..models.auth_identity import normalize_identity

_logger = logging.getLogger(__name__)

SIGN_UP_REQUEST_PARAMS.add("phone")
SIGN_UP_REQUEST_PARAMS.add("ab_storefront_avatar")
SIGN_UP_REQUEST_PARAMS.add("ab_storefront_avatar_completed")

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_EGYPT_MOBILE_RE = re.compile(r"^01[0125]\d{8}$")
_PASSWORD_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")
_AVATAR_KEYS = {"avatar_none", "custom"} | {f"avatar_{index:02d}" for index in range(1, 13)}
_CUSTOM_AVATAR_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
_CUSTOM_AVATAR_MAX_BYTES = 3 * 1024 * 1024


def normalize_egyptian_phone(value):
    phone = (value or "").translate(_ARABIC_DIGITS)
    phone = re.sub(r"[^\d+]", "", phone)
    if phone.startswith("0020"):
        phone = "0" + phone[4:]
    elif phone.startswith("+20"):
        phone = "0" + phone[3:]
    elif phone.startswith("20") and len(phone) == 12:
        phone = "0" + phone[2:]
    elif phone.startswith("1") and len(phone) == 10:
        phone = "0" + phone
    return phone


def is_valid_egyptian_mobile(value):
    return bool(_EGYPT_MOBILE_RE.fullmatch(value or ""))


def validate_storefront_password(value):
    password = value or ""
    return (
        len(password) >= 8
        and any(char.isupper() for char in password)
        and any(char.islower() for char in password)
        and any(char.isdigit() for char in password)
        and bool(_PASSWORD_SPECIAL_RE.search(password))
    )


def _read_custom_avatar_upload(field_name="ab_storefront_avatar_upload"):
    cache_key = f"_ab_storefront_{field_name}_data"
    if cache_key in request.httprequest.environ:
        return request.httprequest.environ[cache_key]
    upload = request.httprequest.files.get(field_name)
    if not upload or not upload.filename:
        request.httprequest.environ[cache_key] = False
        return False
    if upload.mimetype not in _CUSTOM_AVATAR_MIMETYPES:
        raise UserError(_("Please upload a PNG, JPG, or WebP image."))
    data = upload.read(_CUSTOM_AVATAR_MAX_BYTES + 1)
    if len(data) > _CUSTOM_AVATAR_MAX_BYTES:
        raise UserError(_("The image is too large. Choose an image under 3 MB."))
    encoded = base64.b64encode(data)
    request.httprequest.environ[cache_key] = encoded
    return encoded


class AbStorefrontAuth(OAuthLogin):
    def get_auth_signup_config(self):
        config = super().get_auth_signup_config()
        config["ab_telegram_enabled"] = request.env["ab_storefront_auth_telegram"].sudo()._enabled()
        config["ab_auth_retry_after"] = 0
        config.update(ab_phone_signup_label=_("Start Telegram verification"), ab_email_signup_label=_("Create account"), ab_signup_loading_label=_("Creating account..."), ab_signup_continuing_label=_("Continuing..."))
        return config

    def _is_backend_login_request(self, redirect=None):
        target = redirect or request.params.get("redirect") or ""
        return target.startswith(("/odoo", "/web"))

    @staticmethod
    def _is_username_login(value):
        login = (value or "").strip()
        return bool(login and re.search(r"[A-Za-z@._-]", login))

    def _friendly_error(self, fallback=None):
        return fallback or _("The phone number or password is incorrect.")

    def list_providers(self):
        providers = super().list_providers()
        if self._is_backend_login_request():
            return providers
        google_provider = request.env.ref("auth_oauth.provider_google", raise_if_not_found=False)
        if not google_provider:
            return providers
        return [provider for provider in providers if provider.get("id") == google_provider.id]

    def _prepare_phone_login_params(self):
        login = request.params.get("login") or request.params.get("phone")
        normalized = normalize_egyptian_phone(login)
        if normalized:
            request.params["login"] = normalized
            request.params["phone"] = normalized
        return normalized

    def _login_redirect(self, uid, redirect=None):
        if request.params.get("login_success") and not self._is_backend_login_request(redirect):
            user = request.env["res.users"].browse(uid)
            if user._is_internal():
                return "/odoo"
            partner = user.partner_id.sudo()
            if not partner.ab_storefront_seen_profile_onboarding:
                partner.write({"ab_storefront_seen_profile_onboarding": True})
                return "/my/home"
            return "/"
        return super()._login_redirect(uid, redirect=redirect)

    @http.route()
    def web_login(self, redirect=None, **kw):
        if request.httprequest.method == "POST" and not self._is_backend_login_request(redirect):
            from .auth_security import StorefrontAuthSecurity
            StorefrontAuthSecurity()._secure()
            login = request.params.get("login") or request.params.get("phone")
            if not self._is_username_login(login):
                try:
                    request.params["login"] = normalize_identity("phone", login)
                except UserError:
                    request.params["login"] = "__invalid_phone__"

        response = super().web_login(redirect=redirect, **kw)
        if hasattr(response, "qcontext"):
            response.qcontext.update(self.get_auth_signup_config())
            response.qcontext["backend_login"] = self._is_backend_login_request(redirect)
            if (
                request.httprequest.method == "POST"
                and not self._is_backend_login_request(redirect)
                and not self._is_username_login(request.params.get("login"))
                and response.qcontext.get("error")
            ):
                response.qcontext["error"] = self._friendly_error()
        return response

    def get_auth_signup_qcontext(self):
        qcontext = super().get_auth_signup_qcontext()
        if not qcontext.get("token") and request.params.get("from_phone") == "1":
            qcontext["login"] = request.session.get("ab_auth_phone", "")
            request.session["ab_auth_telegram_auto_open"] = False
        phone = qcontext.get("phone") or qcontext.get("login")
        if phone and not self._is_username_login(phone):
            qcontext["phone"] = normalize_egyptian_phone(phone)
        return qcontext

    def _prepare_signup_values(self, qcontext):
        from .auth_security import StorefrontAuthSecurity
        if not qcontext.get("token"):
            StorefrontAuthSecurity()._secure()
        if not validate_storefront_password(qcontext.get("password")):
            raise UserError(_("Use at least 8 characters with uppercase, lowercase, number, and special symbol."))
        if len(qcontext.get("password") or "") > 4096:
            raise UserError(_("Use at least 8 characters with uppercase, lowercase, number, and special symbol."))
        _read_custom_avatar_upload()
        if qcontext.get("token"):
            return super()._prepare_signup_values(qcontext)
        qcontext["login"] = normalize_identity("email", qcontext.get("login"))
        service = request.env["ab_storefront_auth_service"].sudo()
        service._base_url()
        if not service._rate_allow("signup-ip", request.httprequest.remote_addr or "unknown", 10):
            raise UserError(_("Please wait before trying again."))
        service._assert_available_identity(None, "email", qcontext["login"])
        values = super()._prepare_signup_values(qcontext)
        values["email"] = qcontext["login"]
        return values

    @http.route()
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get("token") and not qcontext.get("signup_enabled"):
            raise werkzeug.exceptions.NotFound()

        if "error" not in qcontext and request.httprequest.method == "POST":
            try:
                if not qcontext.get("token") and "@" not in (qcontext.get("login") or ""):
                    from .auth_security import StorefrontAuthSecurity
                    security = StorefrontAuthSecurity()
                    security._secure()
                    phone = normalize_identity("phone", qcontext.get("login"))
                    name = (qcontext.get("name") or "").strip()[:100]
                    if not name:
                        raise UserError(_("Please fill in this field."))
                    token, url = security._service()._request_link(None, phone, security._browser(), security._ip())
                    request.session.update(
                        ab_auth_link=token,
                        ab_auth_deep_link=url,
                        ab_auth_phone=phone,
                        ab_auth_signup_name=name,
                        ab_auth_telegram_auto_open=False,
                    )
                    return request.redirect("/ab_storefront/auth/phone", 303)
                self.do_signup(qcontext)
                if request.session.uid is None:
                    public_user = request.env.ref("base.public_user")
                    request.update_env(user=public_user)
                request.update_context(skip_captcha_login=SKIP_CAPTCHA_LOGIN)
                return self.web_login(*args, **kw)
            except UserError as e:
                qcontext["error"] = e.args[0]
                qcontext["ab_auth_retry_after"] = getattr(e, "retry_after", 0)
            except werkzeug.exceptions.Forbidden as error:
                if error.response is None or error.response.headers.get("X-Ab-Auth-Error") != "https-required":
                    raise
                qcontext["error"] = _("Open the HTTPS website to continue. Local HTTP testing requires development mode.")
                response = request.render("auth_signup.signup", qcontext, status=403)
                response.headers.update({"X-Ab-Auth-Error": "https-required", "Cache-Control": "no-store", "X-Frame-Options": "SAMEORIGIN", "Content-Security-Policy": "frame-ancestors 'self'"})
                return response
            except (SignupError, AssertionError) as e:
                User = request.env["res.users"]
                if User.sudo().with_context(active_test=False).search_count(
                    User._get_login_domain(qcontext.get("login")), limit=1
                ):
                    qcontext["error"] = _("This email is already used. Try signing in instead of creating a new account.")
                else:
                    _logger.warning("%s", e)
                    qcontext["error"] = _("An unexpected error occurred. Please try again.")

        elif "signup_email" in qcontext:
            user = request.env["res.users"].sudo().search([("email", "=", qcontext.get("signup_email")), ("state", "!=", "new")], limit=1)
            if user:
                return request.redirect("/web/login?%s" % url_encode({"login": user.login, "redirect": "/web"}))

        response = request.render("auth_signup.signup", qcontext)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
        return response

    def _signup_with_values(self, token, values, do_login):
        login, password = request.env["res.users"].sudo().signup(values, token)
        user = request.env["res.users"].sudo().search(
            request.env["res.users"]._get_login_domain(login),
            order=request.env["res.users"]._get_login_order(),
            limit=1,
        )
        if user and user.email == login and is_valid_egyptian_mobile(login):
            user.write({"email": False, "phone": login})
            partner_values = {"phone": login, "email": False}
            if "mobile" in user.partner_id._fields:
                partner_values["mobile"] = login
            user.partner_id.write(partner_values)
        if user:
            if not token and "@" in user.login:
                request.env["ab_storefront_auth_service"].sudo()._request_email_verification(
                    user, user.email, "", request.httprequest.remote_addr or "unknown",
                )
            avatar = request.params.get("ab_storefront_avatar")
            avatar_completed = request.params.get("ab_storefront_avatar_completed") == "1"
            avatar_upload = _read_custom_avatar_upload()
            partner_values = {}
            if avatar_upload:
                partner_values.update({
                    "ab_storefront_avatar": "custom",
                    "ab_storefront_avatar_completed": True,
                    "image_1920": avatar_upload,
                })
            elif avatar in _AVATAR_KEYS and avatar != "custom":
                partner_values["ab_storefront_avatar"] = avatar
                partner_values["image_1920"] = False
                partner_values["ab_storefront_avatar_completed"] = avatar_completed or avatar != "avatar_none"
            if partner_values:
                user.partner_id.write(partner_values)
        credential = {"login": login, "password": password, "type": "password"}
        if do_login:
            request.session.authenticate(request.env, credential)

    @http.route()
    def web_auth_reset_password(self, *args, **kw):
        if request.params.get("token"):
            return super().web_auth_reset_password(*args, **kw)
        from .auth_security import StorefrontAuthSecurity
        post = dict(kw)
        post.setdefault("identifier", request.params.get("login", ""))
        return StorefrontAuthSecurity().recover(**post)

    @http.route("/ab_storefront/avatar/update", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def ab_storefront_avatar_update(self, **post):
        avatar = post.get("avatar")
        if avatar not in _AVATAR_KEYS:
            return request.make_json_response({"ok": False, "error": _("The selected avatar is invalid.")}, status=400)
        try:
            avatar_upload = _read_custom_avatar_upload("avatar_upload")
        except UserError as error:
            return request.make_json_response({"ok": False, "error": error.args[0]}, status=400)
        partner_values = {"ab_storefront_avatar": avatar, "ab_storefront_avatar_completed": True}
        if avatar_upload:
            partner_values.update({"ab_storefront_avatar": "custom", "image_1920": avatar_upload})
            avatar = "custom"
        elif avatar != "custom":
            partner_values["image_1920"] = False
        request.env.user.partner_id.sudo().write(partner_values)
        return request.make_json_response({"ok": True, "avatar": avatar})
