import re

import phonenumbers

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize


def normalize_identity(kind, value, region="EG"):
    value = str(value or "").strip()
    if len(value) > 254:
        raise ValidationError(_("Please enter a valid email or phone number."))
    if kind == "email":
        normalized = email_normalize(value)
        if not normalized or normalized != value.lower() or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValidationError(_("Please enter a valid email address."))
        return normalized.lower()
    if kind == "phone":
        value = value.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
        if not re.fullmatch(r"[+\d ()-]+", value, re.ASCII):
            raise ValidationError(_("Please enter a valid phone number."))
        try:
            number = phonenumbers.parse(value, region)
            if phonenumbers.is_valid_number(number):
                return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            pass
        raise ValidationError(_("Please enter a valid phone number."))
    if kind == "telegram" and re.fullmatch(r"[1-9][0-9]{0,19}", value):
        return value
    raise ValidationError(_("Invalid authentication identity."))


class AuthIdentity(models.Model):
    _name = "ab_storefront_auth_identity"
    _description = "Storefront Verified Identity"
    _rec_name = "value"

    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade", groups="base.group_system")
    kind = fields.Selection([("email", "Email"), ("phone", "Phone"), ("telegram", "Telegram")], required=True, index=True)
    value = fields.Char(required=True, index=True, groups="base.group_system")
    verified_at = fields.Datetime(required=True, default=fields.Datetime.now)
    chat_id = fields.Char(groups="base.group_system")

    _unique_value = models.Constraint("UNIQUE(kind, value)", "This identity is already linked to an account.")
    _unique_user_kind = models.Constraint("UNIQUE(user_id, kind)", "An account can have one identity of each type.")

    @api.constrains("kind", "value", "chat_id")
    def _check_identity(self):
        for identity in self:
            if normalize_identity(identity.kind, identity.value) != identity.value:
                raise ValidationError(_("Invalid authentication identity."))
            if identity.kind == "telegram" and identity.chat_id != identity.value:
                raise ValidationError(_("Telegram verification requires a private chat."))


class AuthChallenge(models.Model):
    _name = "ab_storefront_auth_challenge"
    _description = "Storefront Authentication Challenge"
    _rec_name = "purpose"

    user_id = fields.Many2one("res.users", index=True, ondelete="cascade", groups="base.group_system")
    purpose = fields.Selection([(key, key) for key in ("link", "phone_signup", "email_verify", "email_reset", "otp", "grant")], required=True, index=True)
    channel = fields.Char(index=True)
    value = fields.Char(groups="base.group_system")
    token_hash = fields.Char(required=True, index=True, groups="base.group_system")
    browser_hash = fields.Char(groups="base.group_system")
    code_hash = fields.Char(groups="base.group_system")
    credential_stamp = fields.Char(groups="base.group_system")
    expires_at = fields.Datetime(required=True, index=True)
    used_at = fields.Datetime(index=True)
    attempts = fields.Integer(default=0)
    telegram_user_id = fields.Char(index=True, groups="base.group_system")
    telegram_chat_id = fields.Char(groups="base.group_system")
    phone_verified = fields.Boolean(default=False)

    _unique_token = models.Constraint("UNIQUE(token_hash)", "Challenge tokens must be unique.")

    @api.autovacuum
    def _gc_challenges(self):
        from datetime import timedelta
        self.sudo().search([("expires_at", "<", fields.Datetime.now() - timedelta(days=1))], limit=10000).unlink()


class AuthRate(models.Model):
    _name = "ab_storefront_auth_rate"
    _description = "Storefront Authentication Rate Bucket"
    _rec_name = "key"

    key = fields.Char(required=True, index=True, groups="base.group_system")
    count = fields.Integer(default=0)
    expires_at = fields.Datetime(required=True, index=True)
    _unique_key = models.Constraint("UNIQUE(key)", "Rate buckets must be unique.")

    @api.autovacuum
    def _gc_rates(self):
        self.sudo().search([("expires_at", "<", fields.Datetime.now())], limit=10000).unlink()


class AuthEvent(models.Model):
    _name = "ab_storefront_auth_event"
    _description = "Storefront Authentication Delivery Queue"
    _rec_name = "channel"

    channel = fields.Char(required=True, index=True)
    update_key = fields.Char(index=True, groups="base.group_system")
    payload = fields.Text(groups="base.group_system")
    challenge_id = fields.Many2one("ab_storefront_auth_challenge", ondelete="cascade", index=True)
    state = fields.Selection([("pending", "Pending"), ("done", "Done"), ("failed", "Failed")], default="pending", required=True, index=True)
    attempts = fields.Integer(default=0)
    next_attempt = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    _unique_update = models.Constraint("UNIQUE(update_key)", "Telegram updates must be unique.")

    @api.autovacuum
    def _gc_events(self):
        from datetime import timedelta
        self.sudo().search([("create_date", "<", fields.Datetime.now() - timedelta(days=7))], limit=10000).unlink()

    @api.model
    def _process_queue(self):
        self.env["ab_storefront_auth_service"].sudo()._process_queue()
