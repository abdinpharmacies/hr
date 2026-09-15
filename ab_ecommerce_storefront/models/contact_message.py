import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize


class AbContactMessage(models.Model):
    _name = "ab_contact_message"
    _description = "Contact Us Message"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "subject"
    _order = "create_date desc, id desc"

    active = fields.Boolean(default=True)
    name = fields.Char(string="Contact Name", required=True, tracking=True)
    phone = fields.Char()
    email_from = fields.Char(string="Email", required=True)
    company = fields.Char()
    subject = fields.Char(required=True, tracking=True)
    description = fields.Text(string="Message", required=True)
    state = fields.Selection([
        ("new", "New"),
        ("review", "In Review"),
        ("answered", "Answered"),
        ("closed", "Closed"),
    ], default="new", required=True, tracking=True, group_expand=True, index=True)
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        tracking=True,
        domain=[("share", "=", False)],
    )
    internal_notes = fields.Text(groups="website.group_website_designer")
    website_id = fields.Many2one("website", readonly=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
    )
    create_date = fields.Datetime(string="Submission Date", readonly=True)

    _SUBMISSION_FIELDS = ("name", "phone", "email_from", "company", "subject", "description")

    @api.model
    def _submission_errors(self, values):
        errors = {}
        for field_name in ("name", "email_from", "subject", "description"):
            if not (values.get(field_name) or "").strip():
                errors[field_name] = _("Please complete the required fields.")
        for field_name in self._SUBMISSION_FIELDS:
            value = values.get(field_name) or ""
            if len(value) > (5000 if field_name == "description" else 256):
                errors[field_name] = _("Please shorten your entry.")
        if values.get("email_from") and not email_normalize(values["email_from"]):
            errors["email_from"] = _("Enter a valid email address.")
        phone = values.get("phone") or ""
        if phone and (not re.fullmatch(r"\+?[\d ()-]+", phone) or not 7 <= len(re.sub(r"\D", "", phone)) <= 15):
            errors["phone"] = _("Enter a valid phone number, including the country code when needed.")
        return errors

    @api.constrains(*_SUBMISSION_FIELDS)
    def _check_message(self):
        for record in self:
            errors = record._submission_errors({field_name: record[field_name] or "" for field_name in self._SUBMISSION_FIELDS})
            if errors:
                raise ValidationError("\n".join(dict.fromkeys(errors.values())))

    @api.constrains("user_id", "company_id", "website_id")
    def _check_assignment(self):
        for record in self:
            if record.website_id and record.website_id.company_id != record.company_id:
                raise ValidationError(_("The website must belong to the message company."))
            if record.user_id and (record.user_id.share or record.company_id not in record.user_id.company_ids):
                raise ValidationError(_("Choose an internal responsible user with access to this company."))
