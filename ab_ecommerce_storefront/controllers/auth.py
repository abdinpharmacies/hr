import logging
import re
import base64

import werkzeug
from odoo import _, http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.controllers.home import (
    SIGN_UP_REQUEST_PARAMS,
)
from odoo.addons.web.models.res_users import SKIP_CAPTCHA_LOGIN
from odoo.exceptions import UserError
from odoo.http import request
from werkzeug.urls import url_encode

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
        raise UserError(_("برجاء رفع صورة بصيغة PNG أو JPG أو WebP."))
    data = upload.read(_CUSTOM_AVATAR_MAX_BYTES + 1)
    if len(data) > _CUSTOM_AVATAR_MAX_BYTES:
        raise UserError(_("حجم الصورة كبير. اختر صورة أقل من 3 ميجابايت."))
    encoded = base64.b64encode(data)
    request.httprequest.environ[cache_key] = encoded
    return encoded


class AbStorefrontAuth(AuthSignupHome):
    def _is_backend_login_request(self, redirect=None):
        target = redirect or request.params.get("redirect") or ""
        return target.startswith(("/odoo", "/web"))

    @staticmethod
    def _is_username_login(value):
        login = (value or "").strip()
        return bool(login and re.search(r"[A-Za-z@._-]", login))

    def _is_storefront_lang_ar(self):
        return request.env.lang in ("ar", "ar_001") or request.httprequest.path.startswith("/ar/")

    def _friendly_error(self, fallback=None):
        if self._is_storefront_lang_ar():
            return fallback or _("رقم الهاتف أو كلمة المرور غير صحيحة.")
        return fallback or _("The phone number or password is incorrect.")

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
            login = request.params.get("login") or request.params.get("phone")
            if not self._is_username_login(login):
                phone = self._prepare_phone_login_params()
                if not phone:
                    request.params["login"] = "__empty_phone__"
                elif not is_valid_egyptian_mobile(phone):
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
        phone = qcontext.get("phone") or qcontext.get("login")
        if phone:
            qcontext["phone"] = normalize_egyptian_phone(phone)
        return qcontext

    def _prepare_signup_values(self, qcontext):
        phone = normalize_egyptian_phone(qcontext.get("phone") or qcontext.get("login"))
        if not phone:
            raise UserError(_("رقم الهاتف مطلوب."))
        if not is_valid_egyptian_mobile(phone):
            raise UserError(_("برجاء إدخال رقم هاتف صحيح."))
        if not validate_storefront_password(qcontext.get("password")):
            raise UserError(_("استخدم 8 أحرف على الأقل مع حرف كبير وصغير ورقم ورمز خاص."))
        _read_custom_avatar_upload()

        qcontext["phone"] = phone
        qcontext["login"] = phone
        values = super()._prepare_signup_values(qcontext)
        values["login"] = phone
        values["phone"] = phone
        # Keep phone-first accounts compatible with mail features without
        # pretending the mobile number is an email address.
        values["email"] = False
        return values

    @http.route()
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get("token") and not qcontext.get("signup_enabled"):
            raise werkzeug.exceptions.NotFound()

        if "error" not in qcontext and request.httprequest.method == "POST":
            try:
                self.do_signup(qcontext)
                if request.session.uid is None:
                    public_user = request.env.ref("base.public_user")
                    request.update_env(user=public_user)
                request.update_context(skip_captcha_login=SKIP_CAPTCHA_LOGIN)
                return self.web_login(*args, **kw)
            except UserError as e:
                qcontext["error"] = e.args[0]
            except (SignupError, AssertionError) as e:
                User = request.env["res.users"]
                if User.sudo().with_context(active_test=False).search_count(
                    User._get_login_domain(qcontext.get("login")), limit=1
                ):
                    qcontext["error"] = _("هذا الرقم مستخدم بالفعل. جرّب تسجيل الدخول بدلًا من إنشاء حساب جديد.")
                else:
                    _logger.warning("%s", e)
                    qcontext["error"] = _("حدث خطأ غير متوقع. حاول مرة أخرى.")

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
        if request.httprequest.method == "POST":
            self._prepare_phone_login_params()
        response = super().web_auth_reset_password(*args, **kw)
        if hasattr(response, "qcontext") and response.qcontext.get("error"):
            response.qcontext["error"] = _("لم نتمكن من إرسال رابط الاستعادة لهذا الرقم. تواصل معنا على 19036 للمساعدة.")
        elif hasattr(response, "qcontext") and response.qcontext.get("message"):
            response.qcontext["message"] = _("إذا كان الرقم مسجلًا لدينا، ستصلك تعليمات استعادة الحساب.")
        return response

    @http.route("/ab_storefront/avatar/update", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def ab_storefront_avatar_update(self, **post):
        avatar = post.get("avatar")
        if avatar not in _AVATAR_KEYS:
            return request.make_json_response({"ok": False, "error": _("اختيار الأيقونة غير صحيح.")}, status=400)
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
