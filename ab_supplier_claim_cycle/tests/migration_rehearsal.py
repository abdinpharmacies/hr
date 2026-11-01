import base64


def seed_legacy(env):
    supplier = env['ab_costcenter'].create({'name': 'Migration fixture supplier', 'code': '1-migration'})
    for state in ('draft', 'inventory', 'purchasing', 'supplier_accounts', 'bank_accounts', 'returned_secretarial', 'ready_to_close', 'closed'):
        claim = env['ab_supplier_claim_cycle'].create(dict(supplier_id=supplier.id, num_of_invoice=1,
            amount_of_check=' 1,234.50 ', area='north', type_of_invoice='original', payment_nature='check',
            tax_classification='tax_payment', claim_reference='MIG-'+state))
        claim._workflow_write(dict(state=state, resume_stage='supplier_accounts' if state=='returned_secretarial' else False,
            inventory_decision='approved' if state not in ('draft','inventory') else 'pending',
            purchasing_decision='approved' if state in ('supplier_accounts','bank_accounts','ready_to_close','closed') else 'pending',
            supplier_accounts_decision='approved' if state in ('bank_accounts','ready_to_close','closed') else 'pending',
            bank_accounts_decision='pending' if state=='bank_accounts' else 'not_required',
            cheque_attachment=base64.b64encode(b'legacy supplier evidence'), cheque_filename='legacy.pdf'))
        claim._log('secretarial_note', reason='Original legacy history')
    print('Created 8 legacy-state fixtures with preserved evidence and history')


def verify_upgraded(env):
    claims = env['ab_supplier_claim_cycle'].with_context(active_test=False).search([('claim_reference', '=like', 'MIG-%')])
    assert len(claims) == 8
    mapping = {'inventory':'operational_review','purchasing':'operational_review','supplier_accounts':'financial_review'}
    for claim in claims:
        old = claim.claim_reference[4:].lower()
        assert claim.state == mapping.get(old, old), (old, claim.state)
        assert claim.claim_amount == 1234.50
        assert claim.supplier_cheque_attachment == base64.b64encode(b'legacy supplier evidence')
        assert claim.supplier_cheque_filename == 'legacy.pdf'
        history = claim.history_ids.filtered(lambda h: h.reason == 'Original legacy history')
        assert len(history) == 1 and history.to_state == old
        if old in ('bank_accounts','ready_to_close','closed'):
            assert claim.migration_gate_exception
            assert claim.history_ids.filtered(lambda h: h.event == 'migration_exception')
        if old == 'bank_accounts':
            assert not claim.payment_request_attachment
            claim.action_decide('bank_accounts', 'approved')
            assert claim.state == 'ready_to_close'
    print('PASS: 8 legacy states; amounts, bytes, filenames, historical states; legacy bank continuation without fabricated documents')
