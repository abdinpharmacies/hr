from markupsafe import Markup

from odoo import api, fields, SUPERUSER_ID, _


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    last_id = 0
    while entries := env['ab_supplier_claim_cycle.history'].search(
        fields.Domain('id', '>', last_id), order='id', limit=500
    ):
        entries._sync_claim_chatter()
        last_id = entries[-1].id
    last_id = 0
    claims = env['ab_supplier_claim_cycle'].with_context(active_test=False)
    while batch := claims.search(
        fields.Domain('id', '>', last_id) & fields.Domain('secretarial_notes', '!=', False),
        order='id', limit=500
    ):
        for claim in batch:
            note = (claim.secretarial_notes or '').strip()
            if not note or any(
                entry.event == 'secretarial_note' and (entry.reason or '').strip() == note
                for entry in claim.history_ids
            ):
                continue
            marker = '<supplier-claim-legacy-note-%s@odoo.local>' % claim.id
            domain = (fields.Domain('model', '=', claim._name) & fields.Domain('res_id', '=', claim.id)
                      & fields.Domain('message_id', '=', marker))
            if not env['mail.message'].search_count(domain):
                message = claim._message_log(
                    subject=_('Legacy Secretarial Note'), body=Markup('<p>%s</p>') % note)
                message.write({'message_id': marker})
        last_id = batch[-1].id
