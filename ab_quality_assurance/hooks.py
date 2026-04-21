from odoo import SUPERUSER_ID, api


def post_init_hook(env_or_cr, registry=None):
    if registry is None:
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})
    env["ab_quality_assurance.access"].sudo()._sync_quality_manager_group()
