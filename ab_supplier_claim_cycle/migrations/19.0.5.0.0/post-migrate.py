from odoo import SUPERUSER_ID, api


STATE_MAP = {'inventory': 'operational_review', 'purchasing': 'operational_review',
             'supplier_accounts': 'financial_review', 'tax_accounts': 'financial_review'}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    claims = env['ab_supplier_claim_cycle'].with_context(active_test=False).search([])
    for claim in claims:
        old_state = claim.state
        vals = {'state': STATE_MAP.get(old_state, old_state),
                'resume_stage': STATE_MAP.get(claim.resume_stage, claim.resume_stage),
                'document_revision': 1}
        if old_state in ('bank_accounts', 'ready_to_close', 'closed'):
            vals.update(migration_gate_exception=True, secretarial_preparation_status='prepared',
                        tax_decision='not_required')
        else:
            vals.update(secretarial_preparation_status='waiting' if old_state != 'draft' else 'not_required',
                        tax_decision='pending' if claim.tax_classification != 'non_tax_payment' else 'not_required')
            if old_state in ('inventory', 'purchasing'):
                for department in ('inventory', 'purchasing'):
                    if claim[department + '_decision'] not in ('approved', 'deferred'):
                        vals[department + '_decision'] = 'pending'
        legacy_bank_return = old_state == 'returned_secretarial' and claim.resume_stage == 'bank_accounts'
        if legacy_bank_return:
            vals.update(resume_stage='financial_review', secretarial_preparation_status='suspended')
        claim._workflow_write(vals)
        if legacy_bank_return:
            claim._log('migration_exception', old_state, reason=(
                'Legacy rejected bank claim remains returned to Secretarial. Resubmission restarts financial review '
                'to satisfy the new tax and preparation gates; the in-progress bank exemption does not apply.'))
        if vals.get('migration_gate_exception'):
            claim._log('migration_exception', old_state, reason=(
                'Legacy payment-stage claim: tax and preparation gates exempted for continuity. '
                'No human approval or missing document has been created.'))
        for kind in ('supplier_cheque', 'bank_cheque'):
            if claim[kind + '_attachment']:
                claim._snapshot_document(kind, 'Legacy document preserved during upgrade')
    cr.execute('SELECT id FROM ab_supplier_claim_cycle WHERE supplier_cheque_attachment IS DISTINCT FROM cheque_attachment OR supplier_cheque_filename IS DISTINCT FROM cheque_filename')
    if cr.fetchall():
        raise ValueError('Supplier claim attachment verification failed after upgrade')
