import re

from odoo import api, fields, models

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

    @api.model
    def _get_login_domain(self, login):
        domain = super()._get_login_domain(login)
        normalized = normalize_egyptian_phone(login)
        if normalized and normalized != login and is_valid_egyptian_mobile(normalized):
            return fields.Domain.OR([domain, super()._get_login_domain(normalized)])
        return domain

    @api.model
    def signup(self, values, token=None):
        values = dict(values)
        normalized = normalize_egyptian_phone(values.get("phone") or values.get("login"))
        if is_valid_egyptian_mobile(normalized):
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
