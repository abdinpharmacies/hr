"""Process-owned transport policy; never trust RPC context or user groups."""
import os
from odoo import _
from odoo.exceptions import AccessError


def is_callcenter():
    # Fail closed in the callcenter distribution, including unset/invalid roles.
    return os.environ.get('AB_ODOO_SERVER_ROLE', '').strip().lower() != 'branch'


def require_sql():
    if is_callcenter():
        raise AccessError(_("Direct E-Plus access is disabled on this server. Use the branch API."))
