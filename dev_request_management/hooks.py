# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID


def _ensure_admin_group_membership(env):
    admin_group = env.ref("dev_request_management.development.request.admin", raise_if_not_found=False)
    admin_user = env["res.users"].sudo().browse(SUPERUSER_ID).exists()
    if admin_group and admin_user and admin_group not in admin_user.group_ids:
        admin_user.write({"group_ids": [(4, admin_group.id)]})


def post_init_hook(env):
    _ensure_admin_group_membership(env)
