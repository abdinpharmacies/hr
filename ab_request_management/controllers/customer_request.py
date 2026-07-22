import time

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools.translate import _


RATE_LIMIT_SESSION_KEY = "ab_request_management_public_submissions"
RATE_LIMIT_WINDOW_SECONDS = 10 * 60
RATE_LIMIT_MAX_SUBMISSIONS = 5
PUBLIC_FORM_LANGUAGE = "ar_001"


class AbRequestCustomerController(http.Controller):
    @http.route("/requests/external-form", type="http", auth="public", website=True, sitemap=False)
    def external_form(self, **kwargs):
        self._set_public_form_language()
        return self._render_form(post=kwargs)

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
                    "page_title": _("Request Received"),
                },
            )

        if self._is_rate_limited():
            return self._render_form(
                post=post,
                error=_("Too many submissions were received. Please wait a few minutes and try again."),
            )

        try:
            category_id = self._parse_positive_id(post.get("request_category_id"))
            request_type_id = self._parse_positive_id(post.get("request_type_id"))
            self._validate_public_selection(category_id, request_type_id)
            website_request = request.env["ab_request_website"].sudo().create(
                {
                    "customer_name": post.get("customer_name"),
                    "customer_phone": post.get("customer_phone"),
                    "customer_email": post.get("customer_email"),
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
                error=_("Please check the form fields and try again."),
            )

        self._record_successful_submission()
        return request.render(
            "ab_request_management.customer_request_thanks",
            {
                "website_request": website_request,
                "page_title": _("Request Received"),
            },
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
                "page_title": _("External Requests & Complaints"),
                "category_prompt": _("Choose a category..."),
                "select_category_prompt": _("Choose a category first..."),
                "request_type_prompt": _("Choose a request type..."),
            },
        )

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
