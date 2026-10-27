"""Normalize existing disabled mappings without scheduling application jobs."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {"skip_sync_apply_feeders": True, "active_test": False})
    for model_name in ("ab_odoo_sync_field_mapping", "ab_odoo_sync_upload_field_override"):
        # Disabled means explicitly ignored; no previous-type state is retained.
        env[model_name].search([("sync_enabled", "=", False)]).write({"sync_enabled": False})
