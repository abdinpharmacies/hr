from odoo import api, SUPERUSER_ID
from odoo.addons.ab_supplier_claim_cycle.security_upgrade import consolidate_department_groups


def migrate(cr, version):
    if version:
        consolidate_department_groups(api.Environment(cr, SUPERUSER_ID, {}))
