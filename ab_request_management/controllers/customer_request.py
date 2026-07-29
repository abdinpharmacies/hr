import io
import random
import string
import time
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import content_disposition, request
from odoo.tools.translate import _


RATE_LIMIT_SESSION_KEY = "ab_request_management_public_submissions"
VERIFIED_REQUEST_SESSION_KEY = "ab_request_management_verified_external_request_ids"
CAPTCHA_SESSION_KEY = "ab_request_management_public_captcha"
RATE_LIMIT_WINDOW_SECONDS = 10 * 60
RATE_LIMIT_MAX_SUBMISSIONS = 5
CAPTCHA_TTL_SECONDS = 180
PUBLIC_FORM_LANGUAGE = "ar_001"


class AbRequestCustomerController(http.Controller):
    @http.route("/requests/external-form", type="http", auth="public", website=True, sitemap=False)
    def external_form(self, **kwargs):
        self._set_public_form_language()
        return self._render_form(post=kwargs)

    @http.route(
        "/requests/captcha/image",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
        csrf=False,
        sitemap=False,
    )
    def captcha_image(self, **kwargs):
        code = self._generate_captcha_code()
        request.session[CAPTCHA_SESSION_KEY] = {
            "code": code,
            "created_at": int(time.time()),
        }
        return request.make_response(
            self._build_captcha_image(code),
            headers=[
                ("Content-Type", "image/png"),
                ("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"),
                ("Pragma", "no-cache"),
            ],
        )

    @http.route(
        "/requests/customer-submit",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=True,
        sitemap=False,
    )
    def customer_submit(self, **post):
        self._set_public_form_language()
        if post.get("website_url"):
            return request.render(
                "ab_request_management.customer_request_thanks",
                {
                    "website_request": False,
                    "page_title": "تم استلام الشكوى",
                },
            )

        if not self._validate_captcha(post):
            return self._render_form(
                post=post,
                error="رمز التحقق غير صحيح. يُرجى المحاولة مرة أخرى.",
            )

        if self._is_rate_limited():
            return self._render_form(
                post=post,
                error="تم استلام عدد كبير من الإرسالات. يُرجى الانتظار بضع دقائق ثم المحاولة مرة أخرى.",
            )

        try:
            category_id = self._parse_positive_id(post.get("request_category_id"))
            request_type_id = self._parse_positive_id(post.get("request_type_id"))
            requester_type = (post.get("requester_type") or "").strip()
            self._validate_public_selection(category_id, request_type_id)
            website_request = request.env["ab_request_website"].sudo().create(
                {
                    "customer_name": post.get("customer_name"),
                    "customer_phone": post.get("customer_phone"),
                    "customer_email": post.get("customer_email"),
                    "requester_type": requester_type,
                    "employee_code": post.get("employee_code") if requester_type == "employee" else False,
                    "commercial_register_number": post.get("commercial_register_number")
                    if requester_type == "supplier"
                    else False,
                    "national_id": post.get("national_id"),
                    "request_category_id": category_id,
                    "request_type_id": request_type_id,
                    "subject": post.get("subject"),
                    "description": post.get("description"),
                    "source": "embed",
                }
            )
        except (TypeError, ValueError, ValidationError):
            return self._render_form(
                post=post,
                error="يُرجى مراجعة حقول النموذج ثم المحاولة مرة أخرى.",
            )

        self._record_successful_submission()
        return request.render(
            "ab_request_management.customer_request_thanks",
            {
                "website_request": website_request,
                "followup_url": self._build_followup_url(website_request),
                "page_title": "تم استلام الشكوى",
            },
        )

    @http.route("/requests/external-followup", type="http", auth="public", website=True, sitemap=False)
    def external_followup(self, **kwargs):
        self._set_public_form_language()
        return self._render_followup_lookup(post=kwargs)

    @http.route(
        "/requests/external-followup/search",
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=True,
        sitemap=False,
    )
    def external_followup_search(self, **post):
        self._set_public_form_language()
        website_request = self._verify_followup_request(post)
        if not website_request:
            return self._render_followup_lookup(
                post=post,
                error="لم يتم العثور على شكوى مطابقة. يُرجى مراجعة المرجع وبيانات التحقق.",
            )

        self._record_verified_request(website_request)
        followups = website_request.followup_ids.filtered("visible_to_user")
        return self._render_followup_lookup(
            post=post,
            website_request=website_request,
            followups=followups,
        )

    @http.route(
        "/requests/external-followup/attachment/<int:attachment_id>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def external_followup_attachment(self, attachment_id):
        attachment = request.env["ir.attachment"].sudo().browse(attachment_id).exists()
        if not attachment or not self._is_verified_followup_attachment(attachment):
            return request.not_found()

        return request.make_response(
            attachment.raw or b"",
            headers=[
                ("Content-Type", attachment.mimetype or "application/octet-stream"),
                ("Content-Disposition", content_disposition(attachment.name or "attachment")),
            ],
        )

    def _render_form(self, post=None, error=None):
        public_request_types = request.env["ab_request_type"].sudo().search(
            [
                ("is_public", "=", True),
                ("category_id.is_public", "=", True),
            ],
            order="name, id",
        )
        public_categories = public_request_types.mapped("category_id").sorted(
            lambda category: ((category.name or "").casefold(), category.id)
        )
        return request.render(
            "ab_request_management.customer_request_form",
            {
                "categories": public_categories,
                "request_types": public_request_types,
                "has_public_options": bool(public_categories and public_request_types),
                "post": post or {},
                "error": error,
                "page_title": "الشكاوى الخارجية",
                "category_prompt": "اختر القسم...",
                "select_category_prompt": "اختر القسم أولاً...",
                "request_type_prompt": "اختر نوع الشكوى...",
            },
        )

    @staticmethod
    def _render_followup_lookup(post=None, error=None, website_request=None, followups=None):
        return request.render(
            "ab_request_management.customer_request_followup_lookup",
            {
                "post": post or {},
                "error": error,
                "website_request": website_request,
                "followups": followups or request.env["ab_request_website_followup"].sudo().browse(),
                "page_title": "متابعة الشكوى الخارجية",
            },
        )

    @staticmethod
    def _build_followup_url(website_request):
        if not website_request:
            return ""
        base_url = request.httprequest.url_root.rstrip("/")
        request_reference = quote(website_request.name or "", safe="")
        return f"{base_url}/requests/external-followup?request_id={request_reference}"

    @staticmethod
    def _generate_captcha_code(length=5):
        return "".join(random.choice(string.digits) for _i in range(length))

    @staticmethod
    def _get_captcha_font(size=36):
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _build_captcha_image(self, code):
        width, height = 220, 74
        image = Image.new("RGB", (width, height), (246, 248, 251))
        draw = ImageDraw.Draw(image)
        resampling = Image.Resampling.BICUBIC if hasattr(Image, "Resampling") else Image.BICUBIC

        for _i in range(280):
            draw.point(
                (random.randint(0, width - 1), random.randint(0, height - 1)),
                fill=(
                    random.randint(120, 205),
                    random.randint(120, 205),
                    random.randint(120, 205),
                ),
            )

        for _i in range(8):
            draw.line(
                (
                    random.randint(0, width - 1),
                    random.randint(0, height - 1),
                    random.randint(0, width - 1),
                    random.randint(0, height - 1),
                ),
                fill=(
                    random.randint(165, 230),
                    random.randint(165, 230),
                    random.randint(165, 230),
                ),
                width=1,
            )

        x = 14
        for char in code:
            char_font = self._get_captcha_font(random.randint(34, 42))
            char_canvas = Image.new("RGBA", (60, 60), (255, 255, 255, 0))
            char_draw = ImageDraw.Draw(char_canvas)
            char_draw.text(
                (10, 4),
                char,
                font=char_font,
                fill=(
                    random.randint(18, 70),
                    random.randint(18, 70),
                    random.randint(18, 70),
                ),
            )
            rotated = char_canvas.rotate(
                random.randint(-35, 35),
                resample=resampling,
                expand=True,
            )
            image.paste(rotated, (x, random.randint(6, 16)), rotated)
            x += random.randint(36, 40)

        for _i in range(3):
            points = []
            base_y = random.randint(18, height - 16)
            for x_pos in range(0, width + 1, 16):
                points.append((x_pos, base_y + random.randint(-12, 12)))
            draw.line(
                points,
                fill=(
                    random.randint(28, 95),
                    random.randint(28, 95),
                    random.randint(28, 95),
                ),
                width=random.randint(2, 3),
            )

        for _i in range(6):
            x0 = random.randint(0, width - 46)
            y0 = random.randint(0, height - 30)
            x1 = x0 + random.randint(30, 68)
            y1 = y0 + random.randint(16, 34)
            draw.arc(
                (x0, y0, x1, y1),
                start=random.randint(0, 180),
                end=random.randint(181, 360),
                fill=(
                    random.randint(95, 160),
                    random.randint(95, 160),
                    random.randint(95, 160),
                ),
                width=1,
            )

        image = image.filter(ImageFilter.GaussianBlur(0.6))
        image = image.filter(ImageFilter.SHARPEN)
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue()

    @staticmethod
    def _validate_captcha(post):
        captcha_payload = request.session.get(CAPTCHA_SESSION_KEY)
        entered_captcha = (post.get("captcha_input") or "").strip()
        request.session.pop(CAPTCHA_SESSION_KEY, None)

        expected_captcha = captcha_payload
        created_at = 0
        if isinstance(captcha_payload, dict):
            expected_captcha = captcha_payload.get("code")
            created_at = captcha_payload.get("created_at") or 0

        is_expired = bool(created_at and (time.time() - float(created_at) > CAPTCHA_TTL_SECONDS))
        return bool(expected_captcha and entered_captcha == expected_captcha and not is_expired)

    @staticmethod
    def _verify_followup_request(post):
        request_reference = (post.get("request_id") or "").strip()
        requester_type = (post.get("requester_type") or "").strip()
        employee_code = (post.get("employee_code") or "").strip()
        commercial_register_number = (post.get("commercial_register_number") or "").strip()
        if requester_type not in {"employee", "supplier"}:
            return request.env["ab_request_website"].sudo().browse()
        requester_reference = employee_code if requester_type == "employee" else commercial_register_number
        if not request_reference or not requester_reference:
            return request.env["ab_request_website"].sudo().browse()

        website_request = request.env["ab_request_website"].sudo().search(
            [("name", "=", request_reference)],
            limit=1,
        )
        if not website_request:
            return website_request

        reference_matches = AbRequestCustomerController._requester_reference_matches(
            website_request,
            requester_type,
            requester_reference,
        )
        if not reference_matches:
            return request.env["ab_request_website"].sudo().browse()
        return website_request

    @staticmethod
    def _requester_reference_matches(website_request, requester_type, requester_reference):
        stored_requester_type = website_request.requester_type
        if not stored_requester_type:
            stored_requester_type = "supplier" if website_request.commercial_register_number else "employee"
        stored_reference = (
            (website_request.employee_code or "").strip()
            if stored_requester_type == "employee"
            else (website_request.commercial_register_number or "").strip()
        )
        return requester_type == stored_requester_type and requester_reference == stored_reference

    @staticmethod
    def _record_verified_request(website_request):
        verified_request_ids = request.session.get(VERIFIED_REQUEST_SESSION_KEY, [])
        if not isinstance(verified_request_ids, list):
            verified_request_ids = []
        if website_request.id not in verified_request_ids:
            verified_request_ids.append(website_request.id)
        request.session[VERIFIED_REQUEST_SESSION_KEY] = verified_request_ids

    @staticmethod
    def _is_verified_followup_attachment(attachment):
        verified_request_ids = request.session.get(VERIFIED_REQUEST_SESSION_KEY, [])
        if not isinstance(verified_request_ids, list) or not verified_request_ids:
            return False

        followup = request.env["ab_request_website_followup"].sudo().search(
            [
                ("request_id", "in", verified_request_ids),
                ("visible_to_user", "=", True),
                ("attachment_ids", "in", [attachment.id]),
            ],
            limit=1,
        )
        return bool(followup)

    @staticmethod
    def _set_public_form_language():
        arabic_language = request.env["res.lang"].sudo().search(
            [("code", "=", PUBLIC_FORM_LANGUAGE), ("active", "=", True)],
            limit=1,
        )
        if arabic_language:
            request.update_context(lang=arabic_language.code)

    @staticmethod
    def _parse_positive_id(value):
        record_id = int(value)
        if record_id <= 0:
            raise ValueError("Record identifiers must be positive.")
        return record_id

    @staticmethod
    def _validate_public_selection(category_id, request_type_id):
        category = request.env["ab_request_category"].sudo().browse(category_id).exists()
        request_type = request.env["ab_request_type"].sudo().browse(request_type_id).exists()
        if (
            not category
            or not request_type
            or not category.is_public
            or not request_type.is_public
            or request_type.category_id != category
        ):
            raise ValidationError(_("The selected category or request type is not available."))

    @staticmethod
    def _recent_submission_times():
        now = time.time()
        raw_values = request.session.get(RATE_LIMIT_SESSION_KEY, [])
        if not isinstance(raw_values, list):
            return []
        values = []
        for raw_value in raw_values:
            try:
                timestamp = float(raw_value)
            except (TypeError, ValueError):
                continue
            if now - RATE_LIMIT_WINDOW_SECONDS < timestamp <= now:
                values.append(timestamp)
        return values

    def _is_rate_limited(self):
        recent_times = self._recent_submission_times()
        request.session[RATE_LIMIT_SESSION_KEY] = recent_times
        return len(recent_times) >= RATE_LIMIT_MAX_SUBMISSIONS

    def _record_successful_submission(self):
        recent_times = self._recent_submission_times()
        request.session[RATE_LIMIT_SESSION_KEY] = recent_times + [time.time()]
