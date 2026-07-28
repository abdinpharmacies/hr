# -*- coding: utf-8 -*-
import ipaddress

from odoo import models
from odoo.tools.translate import _
from odoo.exceptions import AccessDenied
from odoo.http import request


# Default trusted (internal) networks; you can also load these from ir.config_parameter


def is_internal_ip(ip):
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    # Fast checks
    if addr.is_loopback or addr.is_private or addr.is_link_local:
        return True


class ResUsers(models.Model):
    _inherit = "res.users"

    @staticmethod
    def _client_ip() -> str:
        """Return best-effort client IP (supports reverse proxies if X-Forwarded-For is set)."""
        if request and getattr(request, "httprequest", None):
            hr = request.httprequest
            xff = hr.headers.get("X-Forwarded-For")
            if xff:
                first_hop = xff.split(",")[0].strip()
                if first_hop:
                    return first_hop or ""
            return getattr(hr, "remote_addr", "")
        return ""

    def _check_credentials(self, credentials, env):
        res = super()._check_credentials(credentials, env)

        user = self.sudo()

        # never block superuser
        if user.id == 1:
            return res

        # Never block superuser
        if user.has_group('base.group_system'):
            return res

        # ✅ If user has the "login anywhere" group, bypass IP restriction
        if user.has_group("ab_store.ab_login_from_anywhere"):
            return res

        ip = self._client_ip()

        if is_internal_ip(ip):
            return res

        # Gather allowed IPs from ab_store.ip1
        allowed = self.env["ab_store_ip"].sudo().search([("include", "=", True)]).mapped("name")
        allowed = allowed or []
        # Enforce only if a list is configured
        if ip not in allowed:
            raise AccessDenied(_("Login not allowed from this IP: %s") % (ip or "unknown"))

        return res
