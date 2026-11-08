import base64
import hashlib
import hmac
import re

from cryptography.fernet import Fernet

from odoo import _
from odoo.exceptions import UserError, ValidationError


def normalize_legacy_phone(value, strict=True):
    value = str(value or '').strip()
    value = value.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
    if len(value) > 254 or not re.fullmatch(r'[+0-9 ()-]+', value):
        if not strict:
            return False
        raise ValidationError(_('Please enter a valid phone number.'))
    value = re.sub(r'[ ()-]', '', value)
    if value.startswith('00'):
        value = '+' + value[2:]
    elif value.startswith('01'):
        value = '+2' + value
    elif value.startswith('201'):
        value = '+' + value
    if not re.fullmatch(r'\+201[0125][0-9]{8}', value):
        if not strict:
            return False
        raise ValidationError(_('Please enter a valid phone number.'))
    return value


class LegacyCodeSecurity:
    def __init__(self, env):
        self.env = env

    def _digest(self, value):
        key = self.env['ir.config_parameter'].sudo().get_param('database.secret')
        if not key:
            raise UserError(_('Activation codes are temporarily unavailable.'))
        return hmac.new(key.encode(), ('legacy-activation:' + value).encode(), hashlib.sha256).hexdigest()

    def _cipher(self):
        return Fernet(base64.urlsafe_b64encode(bytes.fromhex(self._digest('export-encryption'))))

    def _lock(self, key):
        number = int(self._digest('lock:' + key)[:15], 16)
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s)', (number,))
