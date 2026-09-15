import re
from urllib.parse import urlsplit

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize


class AbBusinessPartnership(models.Model):
    _name = "ab_business_partnership"
    _description = "Business Partnership"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "company_name"
    _order = "create_date desc, id desc"

    active = fields.Boolean(default=True)
    company_name = fields.Char(required=True, tracking=True)
    contact_name = fields.Char(string="Contact Person", required=True)
    job_title = fields.Char(string="Job Title / Role")
    phone = fields.Char(required=True)
    email = fields.Char(required=True)
    website_url = fields.Char(string="Website / Social Media")
    city = fields.Char(string="City / Governorate")
    partnership_type = fields.Selection([
        ("marketing", "Advertising & Marketing"),
        ("product", "Product Partnership"),
        ("other", "Other"),
    ], required=True, tracking=True)
    brand_name = fields.Char(string="Brand / Product Name")
    product_category = fields.Char()
    inquiry = fields.Char(string="Proposed Collaboration", required=True)
    message = fields.Text(string="Additional Details", required=True)
    state = fields.Selection([
        ("new", "New"), ("review", "In Review"), ("contacted", "Contacted"),
        ("qualified", "Qualified"), ("completed", "Completed"), ("rejected", "Rejected"),
    ], default="new", required=True, tracking=True, group_expand=True, index=True)
    user_id = fields.Many2one("res.users", string="Responsible", tracking=True,
                              domain=[("share", "=", False)])
    internal_notes = fields.Text(groups="website.group_website_designer")
    website_id = fields.Many2one("website", readonly=True)
    company_id = fields.Many2one("res.company", required=True,
                                default=lambda self: self.env.company, readonly=True)
    create_date = fields.Datetime(string="Submission Date", readonly=True)

    _SUBMISSION_FIELDS = (
        "company_name", "contact_name", "job_title", "phone", "email", "website_url",
        "city", "partnership_type", "brand_name", "product_category", "inquiry", "message",
    )

    @api.model
    def _submission_errors(self, values):
        errors = {}
        for name in ("company_name", "contact_name", "phone", "email", "partnership_type", "inquiry", "message"):
            if not (values.get(name) or "").strip():
                errors[name] = _("Please complete the required fields.")
        for name in self._SUBMISSION_FIELDS:
            value = values.get(name) or ""
            if len(value) > (5000 if name == "message" else 256):
                errors[name] = _("Please shorten your entry.")
        if values.get("email") and not email_normalize(values["email"]):
            errors["email"] = _("Enter a valid email address.")
        phone = (values.get("phone") or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
        if phone and (not re.fullmatch(r"\+?[0-9 ()-]+", phone) or not 7 <= len(re.sub(r"\D", "", phone)) <= 15):
            errors["phone"] = _("Enter a valid phone number, including the country code when needed.")
        if values.get("partnership_type") not in ("marketing", "product", "other"):
            errors["partnership_type"] = _("Choose a partnership type.")
        if values.get("message") and len(values["message"].strip()) < 10:
            errors["message"] = _("Please provide at least 10 characters describing your request.")
        if values.get("website_url"):
            try:
                url = urlsplit(values["website_url"])
                valid = url.scheme in ("http", "https") and url.hostname and not url.username
            except ValueError:
                valid = False
            if not valid:
                errors["website_url"] = _("Enter a complete website address starting with https:// or http://.")
        return errors

    @api.constrains(*_SUBMISSION_FIELDS)
    def _check_inquiry(self):
        for record in self:
            errors = record._submission_errors({name: record[name] for name in self._SUBMISSION_FIELDS})
            if errors:
                raise ValidationError("\n".join(dict.fromkeys(errors.values())))

    @api.constrains("user_id", "company_id", "website_id")
    def _check_assignment(self):
        for record in self:
            if record.website_id and record.website_id.company_id != record.company_id:
                raise ValidationError(_("The website must belong to the inquiry company."))
            if record.user_id and (record.user_id.share or record.company_id not in record.user_id.company_ids):
                raise ValidationError(_("Choose an internal responsible user with access to this company."))
