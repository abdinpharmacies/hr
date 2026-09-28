"""Normalize editable sections; immutable history keeps its original labels."""
from odoo import SUPERUSER_ID, api, fields, models

SECTION_MAPPING = {
    'imp_med': 'medical', 'medical_preparations': 'medical',
    'imp_cosmo': 'cosmo', 'supplies': 'other',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {'active_test': False, 'tracking_disable': True})
    for model in ('ab_supplier', 'ab_supplier_claim_cycle', 'ab_supplier_claim_cycle.defaults'):
        for original, replacement in SECTION_MAPPING.items():
            records = env[model].search(fields.Domain('section', '=', original))
            # Migration only: allow normalization of frozen claims/defaults.
            # Historical decision snapshots are never rewritten.
            if records:
                models.Model.write(records, {'section': replacement})
