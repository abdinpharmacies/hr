"""Remove the deployed receipt subsystem; intentionally do not migrate its data."""
import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)
_RECEIPT_MODEL = "ab_odoo_sync_upload_receipt"


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # The runner must be stopped during upgrade. ORM unlink also removes job
    # locks, wizard relations, and mail-thread metadata belonging to these jobs.
    jobs = env["queue.job"].search([("model_name", "=", _RECEIPT_MODEL)])
    while jobs:
        jobs[:1000].unlink()
        jobs = jobs[1000:]
    for xmlid in (
        "menu_ab_odoo_sync_upload_receipts",
        "action_ab_odoo_sync_upload_receipt",
        "view_ab_odoo_sync_upload_receipt_form",
        "view_ab_odoo_sync_upload_receipt_list",
        "access_ab_odoo_sync_upload_receipt_system",
        "job_function_ab_odoo_sync_receipt_process",
    ):
        record = env.ref(f"ab_odoo_sync_mapping.{xmlid}", raise_if_not_found=False)
        if record:
            record.unlink()
    # Include manually-created views/actions/security for the removed model.
    env["ir.ui.view"].search([("model", "=", _RECEIPT_MODEL)]).unlink()
    env["ir.actions.act_window"].search([("res_model", "=", _RECEIPT_MODEL)]).unlink()
    model = env["ir.model"].search([("model", "=", _RECEIPT_MODEL)])
    env["queue.job.function"].search([("model_id", "in", model.ids)]).unlink()
    model.with_context(_force_unlink=True).unlink()
    # Odoo cannot drop a table whose model has already left the registry.
    # RESTRICT is intentional: an unexpected external dependency must stop the
    # upgrade rather than deleting unrelated objects through CASCADE.
    cr.execute("DROP TABLE IF EXISTS ab_odoo_sync_upload_receipt RESTRICT")
    _logger.info("Removed legacy upload receipts and their jobs; no receipt data was migrated")
