import json
import re
import time

from odoo import http, _
from odoo.addons.website.controllers.form import WebsiteForm
from odoo.http import request
from odoo.tools import email_normalize


class AbBusinessPages(http.Controller):
    @http.route("/business-partnerships", type="http", auth="public", website=True, sitemap=True)
    def business_partnerships(self, **kwargs):
        return request.render("ab_ecommerce_storefront.business_partnerships")

    @http.route("/business-partnerships/thank-you", type="http", auth="public", website=True, sitemap=False)
    def business_partnerships_thanks(self, **kwargs):
        if not request.session.get("ab_business_submitted"):
            return request.redirect("/business-partnerships")
        response = request.render("ab_ecommerce_storefront.business_partnerships_thanks")
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Robots-Tag"] = "noindex"
        return response


class AbBusinessWebsiteForm(WebsiteForm):
    def _handle_website_form(self, model_name, **kwargs):
        contact_form_type = kwargs.pop("ab_contact_form", None)
        if model_name in ("mail.mail", "ab_contact_message") and contact_form_type == "general":
            errors = {}
            for name, field_id in (("name", "contact1"), ("email_from", "contact3"), ("subject", "contact5"), ("description", "contact6")):
                value = kwargs.get(name) or ""
                if not isinstance(value, str) or not value.strip():
                    errors[field_id] = _("Please complete the required fields.")
                elif len(value) > (5000 if name == "description" else 256):
                    errors[field_id] = _("Please shorten your entry.")
            if isinstance(kwargs.get("email_from"), str) and not email_normalize(kwargs["email_from"]):
                errors["contact3"] = _("Enter a valid email address.")
            phone = kwargs.get("phone") or ""
            if not isinstance(phone, str) or (phone and (not re.fullmatch(r"\+?[\d ()-]+", phone) or not 7 <= len(re.sub(r"\D", "", phone)) <= 15)):
                errors["contact2"] = _("Enter a valid phone number, including the country code when needed.")
            if errors:
                return json.dumps({"error": " ".join(dict.fromkeys(errors.values())), "error_fields": errors})
            if model_name == "mail.mail":
                model_name = "ab_contact_message"
        if model_name != "ab_business_partnership":
            return super()._handle_website_form(model_name, **kwargs)
        # Native form routing validates CAPTCHA; enforce CSRF for guests as well.
        if not request.validate_csrf(kwargs.get("ab_csrf_token")):
            return json.dumps({"error": _("Your session expired. Refresh the page and try again.")})
        attempts, started = request.session.get("ab_business_attempts", (0, 0))
        now = time.time()
        if now - started > 900:
            attempts, started = 0, now
        request.session["ab_business_attempts"] = (attempts + 1, started)
        if attempts >= 10 or kwargs.get("ab_company_fax"):
            return json.dumps({"error": _("We could not accept this request. Please try again later.")})
        model = request.env[model_name]
        if any(not isinstance(kwargs.get(name, ""), str) for name in model._SUBMISSION_FIELDS):
            return json.dumps({"error": _("Please enter text in the form fields. File uploads are not supported.")})
        values = {name: (kwargs.get(name) or "").strip() for name in model._SUBMISSION_FIELDS}
        if values["partnership_type"] != "product":
            values["product_category"] = ""
        errors = model._submission_errors(values)
        if errors:
            return json.dumps({"error": " ".join(dict.fromkeys(errors.values())),
                               "error_fields": {"ab_business_" + name: message for name, message in errors.items()}})
        result = super()._handle_website_form(model_name, **values)
        if json.loads(result).get("id"):
            request.session["ab_business_submitted"] = True
        return result

    def insert_record(self, request, model_sudo, values, custom, meta=None):
        if model_sudo.model in ("ab_contact_message", "ab_business_partnership"):
            values.update(website_id=request.website.id, company_id=request.website.company_id.id)
            # Do not store browser metadata or arbitrary posted fields in chatter.
            custom, meta = "", None
        return super().insert_record(request, model_sudo, values, custom, meta=meta)
