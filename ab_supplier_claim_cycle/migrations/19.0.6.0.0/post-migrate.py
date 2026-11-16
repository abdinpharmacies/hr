from odoo import api, Command, SUPERUSER_ID


GROUPS = {
    'inventory': 'ab_supplier_claim_cycle.supplier_claim_group_inventory',
    'purchasing': 'ab_supplier_claim_cycle.supplier_claim_group_purchasing',
    'tax': 'ab_supplier_claim_cycle.supplier_claim_group_tax',
    'supplier_accounts': 'ab_supplier_claim_cycle.supplier_claim_group_supplier_accounts',
    'bank_accounts': 'ab_supplier_claim_cycle.supplier_claim_group_bank_accounts',
    'secretarial': 'ab_supplier_claim_cycle.supplier_claim_group_user',
}

ALLOWED_FIELDS = {
    'inventory': ('inventory_notes', 'inventory_followup_date'),
    'purchasing': ('purchasing_notes', 'purchasing_followup_date'),
    'tax': ('tax_notes', 'tax_followup_date', 'tax_discount_decision',
            'tax_review_attachment', 'tax_review_filename'),
    'supplier_accounts': ('supplier_accounts_notes', 'supplier_accounts_followup_date',
                          'supplier_cheque_attachment', 'supplier_cheque_filename'),
    'secretarial': ('secretarial_notes', 'payment_request_attachment', 'payment_request_filename'),
    'bank_accounts': ('bank_accounts_notes', 'bank_accounts_followup_date',
                      'bank_cheque_attachment', 'bank_cheque_filename'),
    'close': (),
}


def _workflow_specs(cash, include_tax):
    sequence = 1
    specs = []
    if not cash:
        specs += [('inventory', 'Inventory', sequence), ('purchasing', 'Purchasing', sequence)]
        sequence += 1
    if include_tax:
        specs.append(('tax', 'Tax', sequence))
    specs.append(('supplier_accounts', 'Supplier Accounts', sequence))
    sequence += 1
    specs.append(('secretarial', 'Secretarial Preparation', sequence))
    sequence += 1
    if not cash:
        specs.append(('bank_accounts', 'Bank Accounts', sequence))
        sequence += 1
    specs.append(('close', 'Secretarial Close', sequence))
    return specs


def _get_or_create_workflow(env, cash, include_tax, field_ids, approvers):
    payment_label = 'Cash' if cash else 'Non-Cash'
    tax_label = 'Tax' if include_tax else 'Non-Tax'
    name = f'Legacy {payment_label} {tax_label}'
    Workflow = env['ab_supplier_claim_workflow'].with_context(active_test=False)
    workflow = Workflow.search([('name', '=', name), ('version', '=', 1)], limit=1)
    if workflow:
        return workflow
    payment_domain = [('payment_nature', '=', 'cash')] if cash else [
        ('payment_nature', 'in', ['check', 'bank_transfer'])]
    tax_domain = [('tax_classification', '=', 'non_tax_payment')] if not include_tax else [
        ('tax_classification', '!=', 'non_tax_payment')]
    workflow = Workflow.create({
        'name': name,
        'claim_domain': repr(payment_domain + tax_domain),
        'priority': 100,
    })
    for key, label, sequence in _workflow_specs(cash, include_tax):
        users = approvers['secretarial' if key == 'close' else key]
        env['ab_supplier_claim_workflow_stage'].create({
            'workflow_id': workflow.id,
            'name': label,
            'sequence': sequence,
            'approver_ids': [Command.set(users.ids)],
            'allowed_field_ids': [Command.set([
                field_ids[name] for name in ALLOWED_FIELDS[key] if name in field_ids
            ])],
        })
    workflow.action_publish()
    return workflow


def _legacy_current_key(claim):
    if claim.state == 'operational_review':
        return 'inventory'
    if claim.state == 'financial_review':
        return 'tax' if claim.tax_classification != 'non_tax_payment' else 'supplier_accounts'
    if claim.state == 'secretarial_preparation':
        return 'secretarial'
    if claim.state == 'bank_accounts':
        return 'bank_accounts'
    if claim.state == 'ready_to_close':
        return 'close'
    if claim.state == 'returned_secretarial':
        return claim.rejection_department or 'secretarial'
    return False


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    participant = env.ref('ab_supplier_claim_cycle.supplier_claim_group_participant')
    fallback = env.ref('ab_supplier_claim_cycle.supplier_claim_group_admin').user_ids or env.user
    approvers = {
        key: (env.ref(xmlid).user_ids or fallback)
        for key, xmlid in GROUPS.items()
    }
    all_approvers = env['res.users'].browse({
        user_id for users in approvers.values() for user_id in users.ids
    })
    for user in all_approvers.filtered(lambda record: participant not in record.all_group_ids):
        user.group_ids = [Command.link(participant.id)]

    fields_by_name = env['ir.model.fields'].search([
        ('model', '=', 'ab_supplier_claim_cycle'),
    ])
    field_ids = {field.name: field.id for field in fields_by_name}
    workflows = {
        (cash, include_tax): _get_or_create_workflow(
            env, cash, include_tax, field_ids, approvers)
        for cash in (False, True) for include_tax in (False, True)
    }

    StageState = env['ab_supplier_claim_stage_state'].with_context(
        _supplier_claim_workflow_internal=True)
    claims = env['ab_supplier_claim_cycle'].with_context(active_test=False).search([])
    for claim in claims:
        if claim.stage_state_ids:
            continue
        cash = claim.payment_nature == 'cash'
        include_tax = claim.tax_classification != 'non_tax_payment'
        workflow = workflows[cash, include_tax]
        if claim.state == 'draft':
            claim._workflow_write({'workflow_id': workflow.id})
            continue

        stages = workflow.workflow_stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
        current_key = _legacy_current_key(claim)
        key_by_name = {
            'Inventory': 'inventory', 'Purchasing': 'purchasing', 'Tax': 'tax',
            'Supplier Accounts': 'supplier_accounts',
            'Secretarial Preparation': 'secretarial', 'Bank Accounts': 'bank_accounts',
            'Secretarial Close': 'close',
        }
        current_stage = stages.filtered(lambda stage: key_by_name[stage.name] == current_key)[:1]
        current_sequence = current_stage.sequence if current_stage else 0
        values = []
        for stage in stages:
            key = key_by_name[stage.name]
            decision = claim[f'{key}_decision'] if key in (
                'inventory', 'purchasing', 'tax', 'supplier_accounts', 'bank_accounts') else False
            if claim.state == 'closed':
                status = 'approved'
            elif key == 'close' and claim.state == 'ready_to_close':
                status = 'pending'
            elif key == 'secretarial' and claim.state in ('bank_accounts', 'ready_to_close'):
                status = 'approved'
            elif key == 'bank_accounts' and claim.state == 'ready_to_close':
                status = 'approved'
            elif decision == 'approved':
                status = 'approved'
            elif claim.state == 'returned_secretarial' and key == current_key:
                status = 'rejected'
            elif current_sequence and stage.sequence == current_sequence:
                status = decision if decision == 'deferred' else 'pending'
            elif current_sequence and stage.sequence < current_sequence:
                status = 'approved'
            else:
                status = 'waiting'
            values.append({'claim_id': claim.id, 'stage_id': stage.id, 'status': status})
        rows = StageState.create(values)
        rejected = rows.filtered(lambda row: row.status == 'rejected')[:1]
        new_state = ('closed' if claim.state == 'closed' else
                     'returned' if claim.state == 'returned_secretarial' else 'in_progress')
        claim._workflow_write({
            'workflow_id': workflow.id,
            'state': new_state,
            'current_sequence': 0 if new_state == 'closed' else current_sequence,
            'rejection_stage_state_id': rejected.id if rejected else False,
        })
