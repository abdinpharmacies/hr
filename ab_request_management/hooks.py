# -*- coding: utf-8 -*-

from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env["res.users"].sudo().search([("active", "=", True)])
    users._ab_request_management_sync_groups()
