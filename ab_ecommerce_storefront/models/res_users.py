import re

from odoo import api, fields, models
from .auth_identity import normalize_identity
from odoo.exceptions import ValidationError

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_EGYPT_MOBILE_RE = re.compile(r"^01[0125]\d{8}$")


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


class ResUsers(models.Model):
    _inherit = "res.users"

    ab_storefront_profile_completion_seen = fields.Boolean(
        string="Profile Completion Celebration Seen",
        default=False,
        copy=False,
        readonly=True,
        groups="base.group_system",
    )

    def _ab_storefront_profile_completion(self):
        self.ensure_one()
        partner = self.partner_id
        mobile = partner.mobile if "mobile" in partner._fields else False
        return 25 * sum((
            bool(partner.name),
            bool(partner.phone or mobile or self.login),
            bool(partner.ab_storefront_avatar_completed or (partner.ab_storefront_avatar or "avatar_none") != "avatar_none"),
            bool(partner.street or partner.city or partner.country_id),
        ))

    @api.model
    def _ab_claim_profile_completion_celebration(self):
        user = self.env.user
        result = {"celebrate": False, "seen": False}
        if user._is_public():
            return result
        user_sudo = user.sudo().try_lock_for_update(allow_referencing=True)
        if not user_sudo:
            return result
        user_sudo.invalidate_recordset(["ab_storefront_profile_completion_seen"])
        if user_sudo.ab_storefront_profile_completion_seen:
            return {"celebrate": False, "seen": True}
        if user._ab_storefront_profile_completion() != 100:
            return result
        user_sudo.write({"ab_storefront_profile_completion_seen": True})
        return {"celebrate": True, "seen": True}

    @api.model
    def _get_login_domain(self, login):
        domain = super()._get_login_domain(login)
        normalized = normalize_egyptian_phone(login)
        if normalized and normalized != login and is_valid_egyptian_mobile(normalized):
            domain = fields.Domain.OR([domain, super()._get_login_domain(normalized)])
        kind = "email" if "@" in (login or "") else "phone"
        try:
            value = normalize_identity(kind, login)
        except ValidationError:
            return domain
        identity = self.env["ab_storefront_auth_identity"].sudo().search([
            ("kind", "=", kind), ("value", "=", value), ("user_id.active", "=", True),
        ], limit=1)
        if identity:
            return fields.Domain("id", "=", identity.user_id.id)
        return domain

    @api.model
    def signup(self, values, token=None):
        values = dict(values)
        normalized = normalize_egyptian_phone(values.get("login"))
        if not token and is_valid_egyptian_mobile(normalized):
            values["login"] = normalized
            values["phone"] = normalized
        login, password = super().signup(values, token=token)
        if is_valid_egyptian_mobile(login):
            user = self.sudo().search(super()._get_login_domain(login), limit=1)
            if user and user.email == login:
                user.write({"email": False, "phone": login})
                partner_values = {"phone": login, "email": False}
                if "mobile" in user.partner_id._fields:
                    partner_values["mobile"] = login
                user.partner_id.write(partner_values)
        return login, password
