from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref(
        "ab_odoo_sync_mapping.ir_cron_ab_odoo_sync_queue_upload_apply",
        raise_if_not_found=False,
    )
    if cron:
        cron.write(
            {
                "interval_number": 2,
                "interval_type": "hours",
            }
        )
