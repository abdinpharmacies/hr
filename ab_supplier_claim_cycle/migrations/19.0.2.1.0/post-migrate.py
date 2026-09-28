"""Recover legacy supplier references and migrate parallel reviews safely."""
from odoo import SUPERUSER_ID, api, fields
from odoo.exceptions import ValidationError


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {'tracking_disable': True})
    _migrate_legacy_inventory_claims(env)
    claims = env['ab_supplier_claim_cycle'].with_context(active_test=False).search(
        fields.Domain('state', '=', 'inventory_purchase')
        | fields.Domain('resume_stage', '=', 'inventory_purchase')
    )
    changes = []
    for claim in claims:
        vals = {}
        if claim.payment_nature != 'non_cash':
            raise ValidationError('Legacy claim %s has inconsistent payment routing.' % claim.id)
        if claim.state == 'inventory_purchase':
            if claim.resume_stage or any(claim[d + '_decision'] not in ('pending', 'deferred', 'approved')
                                         for d in ('inventory', 'purchasing')):
                raise ValidationError('Legacy claim %s has inconsistent review decisions.' % claim.id)
            if claim.supplier_accounts_decision != 'pending' or claim.bank_accounts_decision != 'pending':
                raise ValidationError('Legacy claim %s has inconsistent downstream decisions.' % claim.id)
            vals['state'] = ('inventory' if claim.inventory_decision != 'approved'
                             else 'purchasing' if claim.purchasing_decision != 'approved'
                             else 'supplier_accounts')
        if claim.resume_stage == 'inventory_purchase':
            department = claim.rejection_department
            if (claim.state != 'returned_secretarial' or department not in ('inventory', 'purchasing')
                    or claim[department + '_decision'] != 'rejected'):
                raise ValidationError('Legacy claim %s has an inconsistent rejection route.' % claim.id)
            if department == 'purchasing' and claim.inventory_decision != 'approved':
                raise ValidationError('Legacy claim %s needs an explicit Inventory review resolution before migration.' % claim.id)
            if department == 'inventory' and claim.purchasing_decision not in ('approved', 'cancelled'):
                raise ValidationError('Legacy claim %s has an inconsistent Purchasing decision.' % claim.id)
            vals['resume_stage'] = department
        changes.append((claim, vals))
    for claim, vals in changes:
        old_state = claim.state
        claim._workflow_write(vals)
        claim._log('migrated', old_state, reason='Converted outstanding parallel review to sequential routing.')


def _migrate_legacy_inventory_claims(env):
    """Recover mixed legacy/schema-rollback claims without fabricating approvals."""
    env.cr.execute("""
        SELECT 1 FROM pg_attribute
         WHERE attrelid = 'ab_supplier_claim_cycle'::regclass
           AND attname = 'legacy_supplier_reference_id' AND NOT attisdropped
    """)
    if not env.cr.fetchone():
        return
    # Later upgrades may remove the obsolete status column after recovery.
    # Retained reference metadata alone does not imply unfinished recovery.
    env.cr.execute("""
        SELECT 1 FROM ab_supplier_claim_cycle
         WHERE legacy_supplier_reference_id IS NOT NULL
           AND NOT COALESCE(legacy_claim_recovered, false) LIMIT 1
    """)
    if not env.cr.fetchone():
        return
    env.cr.execute("""
        SELECT id, legacy_supplier_reference_id, status
          FROM ab_supplier_claim_cycle
         WHERE legacy_supplier_reference_id IS NOT NULL
           AND NOT COALESCE(legacy_claim_recovered, false) ORDER BY id
    """)
    legacy_rows = env.cr.fetchall()
    Claim = env['ab_supplier_claim_cycle'].with_context(active_test=False, tracking_disable=True)
    Supplier = env['ab_supplier'].with_context(active_test=False)
    histories = env['ab_supplier_claim_cycle.history'].search(
        fields.Domain('claim_id', 'in', [row[0] for row in legacy_rows]),
        order='occurred_at, id',
    )
    by_claim = {}
    for history in histories:
        by_claim.setdefault(history.claim_id.id, env['ab_supplier_claim_cycle.history'])
        by_claim[history.claim_id.id] |= history
    for claim_id, reference_id, status in legacy_rows:
        claim = Claim.browse(claim_id)
        history = by_claim.get(claim_id, env['ab_supplier_claim_cycle.history'])
        created = history.filtered(lambda h: h.event == 'created')
        native = bool(created and claim.create_date and any(
            h.from_state == 'draft' and h.to_state == 'draft'
            and abs((h.occurred_at - claim.create_date).total_seconds()) <= 1
            for h in created
        ))
        if history and not native:
            raise ValidationError('Claim %s has history without matching creation evidence; recovery stopped.' % claim_id)
        if native:
            supplier = Supplier.browse(reference_id).exists()
            if not supplier:
                raise ValidationError('Claim %s has a missing original supplier %s.' % (claim_id, reference_id))
            source_model = 'ab_supplier'
        else:
            supplier, source_model = Supplier._resolve_legacy_supplier_reference(reference_id)
        vals = dict(
            supplier_id=supplier.id, legacy_status=status,
            payment_nature=supplier.payment_nature,
            business_category=supplier.business_category, tax_classification=supplier.tax_type,
        )
        explanation = 'Original reference: %s(%s); legacy status: %s. ' % (source_model, reference_id, status)
        if native:
            latest = history[-1]
            vals.update(state=latest.to_state, review_round=latest.review_round)
            for department in ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts'):
                decision = latest[f'{department}_decision']
                if not decision:
                    raise ValidationError('Claim %s has incomplete decision snapshots.' % claim_id)
                vals[f'{department}_decision'] = decision
                decisions = history.filtered(lambda h: h.department == department and h.event == 'decision')
                if decisions:
                    vals[f'{department}_notes'] = decisions[-1].reason
                    vals[f'{department}_followup_date'] = decisions[-1].followup_date if decision == 'deferred' else False
            submitted = history.filtered(lambda h: h.event == 'submitted')
            if submitted:
                vals['payment_nature'] = 'cash' if submitted[-1].to_state == 'supplier_accounts' else 'non_cash'
            if latest.to_state == 'returned_secretarial':
                rejected = history.filtered(lambda h: h.event == 'decision' and h.decision == 'rejected')
                if not rejected:
                    raise ValidationError('Claim %s has no rejection evidence.' % claim_id)
                vals.update(resume_stage=rejected[-1].from_state,
                            rejection_department=rejected[-1].department, rejection_reason=rejected[-1].reason)
            if latest.event == 'archived':
                vals['active'] = False
            explanation += 'Supplier identity and workflow snapshot restored from matching creation/audit history. '
        else:
            vals.update(state='legacy_review', review_round=0)
            explanation += 'Legacy progress retained for review; no department approvals inferred. '
        claim._workflow_write(vals)
        claim._log('migrated', reason='Legacy schema recovery: ' + explanation)
        env.cr.execute("""
            UPDATE ab_supplier_claim_cycle
               SET legacy_supplier_reference_model = %s, legacy_claim_recovered = true
             WHERE id = %s
        """, [source_model, claim_id])
    env.flush_all()
    env.cr.execute('ALTER TABLE ab_supplier_claim_cycle ALTER COLUMN supplier_id SET NOT NULL')
