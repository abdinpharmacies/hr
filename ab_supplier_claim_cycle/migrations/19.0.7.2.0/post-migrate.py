def migrate(cr, version):
    if not version:
        return
    # Preserve membership independently from the live stage configuration.
    cr.execute('''
        INSERT INTO ab_supplier_claim_stage_historical_user_rel (stage_state_id, user_id)
        SELECT state.id, approver.user_id
          FROM ab_supplier_claim_stage_state state
          JOIN ab_supplier_claim_stage_approver_rel approver ON approver.stage_id = state.stage_id
        UNION
        SELECT id, user_id FROM ab_supplier_claim_stage_state WHERE user_id IS NOT NULL
        UNION
        SELECT stage_state_id, user_id FROM ab_supplier_claim_cycle_history
         WHERE stage_state_id IS NOT NULL AND user_id IS NOT NULL
        ON CONFLICT DO NOTHING
    ''')
