"""Reject an unsafe Odoo 15 accounting-only upgrade."""


def migrate(cr, installed_version):
    cr.execute(
        """SELECT 1 FROM ir_model_data
           WHERE module = 'ab_accounting'
             AND name = 'model_ab_accounting_account_guide'"""
    )
    if not cr.fetchone():
        return
    cr.execute(
        """SELECT state FROM ir_module_module
           WHERE name = 'ab_accounting_base'"""
    )
    row = cr.fetchone()
    if not row or row[0] not in ('to install', 'to upgrade', 'installed'):
        raise RuntimeError(
            "Install ab_accounting_base while upgrading ab_accounting; "
            "an accounting-only upgrade can remove shared catalog records."
        )
