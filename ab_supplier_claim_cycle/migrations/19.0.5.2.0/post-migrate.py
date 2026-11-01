from odoo import api, fields, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    last_id = 0
    while documents := env['ab_supplier_claim_document'].search(
        fields.Domain('id', '>', last_id), order='id', limit=500
    ):
        documents._sync_claim_chatter()
        last_id = documents[-1].id
