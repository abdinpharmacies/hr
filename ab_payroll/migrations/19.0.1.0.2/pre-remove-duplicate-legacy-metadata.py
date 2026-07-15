from odoo.addons.ab_payroll.hooks import transfer_legacy_metadata


def migrate(cr, version):
    transfer_legacy_metadata(cr)
