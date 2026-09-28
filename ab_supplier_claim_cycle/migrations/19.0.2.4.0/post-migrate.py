"""Preserve existing user notes as append-only history, with truthful import dates."""
from odoo import SUPERUSER_ID, api, fields


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    claims = env['ab_supplier_claim_cycle'].with_context(active_test=False).search(
        fields.Domain('secretarial_notes', '!=', False))
    existing = env['ab_supplier_claim_cycle.history'].search(
        fields.Domain('claim_id', 'in', claims.ids)
        & fields.Domain('event', 'in', ['secretarial_note', 'imported_secretarial_note']))
    recorded = {(row.claim_id.id, (row.reason or '').strip()) for row in existing}
    sample_labels = {
        'SCCS260927%02d' % index:
        '[SCC SAMPLE 20260927-%02d] Training only — draft; no payment or stock operation.' % index
        for index in range(1, 7)
    }
    values = []
    for claim in claims:
        note = (claim.secretarial_notes or '').strip()
        if not note or (claim.id, note) in recorded:
            continue
        if sample_labels.get(claim.supplier_id.code) == note:
            continue
        values.append(claim._history_values(
            'imported_secretarial_note', department='secretarial', reason=note))
    env['ab_supplier_claim_cycle.history']._append(values)
