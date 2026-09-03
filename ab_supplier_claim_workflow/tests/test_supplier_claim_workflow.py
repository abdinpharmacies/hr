from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestSupplierClaimWorkflow(TransactionCase):
    def setUp(self):
        super().setUp()
        self.group_user = self.env.ref('base.group_user')
        self.group_secretarial = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_user')
        self.group_inventory = self.env.ref('ab_supplier_claim_workflow.supplier_claim_group_inventory')
        self.group_purchase = self.env.ref('ab_supplier_claim_workflow.supplier_claim_group_purchase')
        self.group_suppliers = self.env.ref('ab_supplier_claim_workflow.supplier_claim_group_suppliers')
        self.group_tax_accounts = self.env.ref('ab_supplier_claim_workflow.supplier_claim_group_tax_accounts')
        self.group_bank_acc = self.env.ref('ab_supplier_claim_workflow.supplier_claim_group_bank_acc')
        self.group_admin = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_admin')
        self.group_reviewer = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_reviewer')
        self.workflow_groups = (
            self.group_secretarial
            | self.group_inventory
            | self.group_purchase
            | self.group_suppliers
            | self.group_tax_accounts
            | self.group_bank_acc
            | self.group_admin
            | self.group_reviewer
        )
        self.workflow_user = self.env.ref('base.user_admin').sudo()

        seed = (self.env['ab_costcenter'].sudo().search([], order='id desc', limit=1).id or 0) + 1000000
        try:
            self.supplier = self.env['ab_costcenter'].sudo().create({
                'name': 'Supplier Claim Test Supplier',
                'code': '1-SCT%s' % seed,
            })
        except ValidationError:
            self.supplier = self.env['ab_costcenter'].sudo().search([('code', '=like', '1-%')], limit=1)
            self.assertTrue(self.supplier, 'At least one supplier cost center is required for workflow tests.')

        self.secretarial_user = self._make_role_user('claim_secretarial_user', self.group_secretarial)
        self.inventory_user = self._make_role_user('claim_inventory_user', self.group_inventory)
        self.purchase_user = self._make_role_user('claim_purchase_user', self.group_purchase)
        self.suppliers_user = self._make_role_user('claim_suppliers_user', self.group_suppliers)
        self.admin_user = self._make_role_user('claim_admin_user', self.group_admin)

    def _make_role_user(self, login, group):
        return self.env['res.users'].with_context(no_reset_password=True).sudo().create({
            'name': login.replace('_', ' ').title(),
            'login': '%s@example.com' % login,
            'email': '%s@example.com' % login,
            'group_ids': [(6, 0, [self.group_user.id, group.id])],
        })

    def _set_workflow_group(self, group):
        self.workflow_user.write({
            'group_ids': [(3, g.id) for g in self.workflow_groups] + [
                (4, self.group_user.id),
                (4, group.id),
            ],
        })
        self.env.invalidate_all()

    def _create_claim(self, supplier_type='non_taxable'):
        self._set_workflow_group(self.group_secretarial)
        return self.env['ab_supplier_claim_cycle'].with_user(self.workflow_user).create({
            'supplier_id': self.supplier.id,
            'supplier_type': supplier_type,
            'supplier_section': 'medicine',
            'num_of_invoice': 2,
            'area': 'south',
            'amount_of_check': 1000.0,
            'type_of_invoice': 'original',
            'claim_document': b'dGVzdF9jbGFpbV9kb2N1bWVudA==',
            'claim_document_filename': 'claim.pdf',
        })

    def _start_cycle(self, claim):
        self._set_workflow_group(self.group_secretarial)
        claim.with_user(self.workflow_user).action_done()

    def _department_accept(self, claim, group):
        self._set_workflow_group(group)
        claim.with_user(self.workflow_user).action_accept()

    def _department_finish(self, claim, group):
        self._set_workflow_group(group)
        claim.with_user(self.workflow_user).action_finish()

    def _department_accept_and_finish(self, claim, group):
        self._department_accept(claim, group)
        self._department_finish(claim, group)

    def _all_departments_finish(self, claim):
        groups = [self.group_inventory, self.group_purchase, self.group_suppliers]
        if claim.supplier_type == 'withholding_tax':
            groups.append(self.group_tax_accounts)
        groups.append(self.group_bank_acc)
        for group in groups:
            self._department_accept_and_finish(claim, group)

    def test_secretarial_start_requires_cheque_amount_dialog(self):
        self._set_workflow_group(self.group_secretarial)
        claim = self.env['ab_supplier_claim_cycle'].with_user(self.workflow_user).create({
            'supplier_id': self.supplier.id,
            'supplier_type': 'non_taxable',
            'supplier_section': 'medicine',
            'num_of_invoice': 2,
            'area': 'south',
            'amount_of_check': 0.0,
            'type_of_invoice': 'original',
            'claim_document': b'dGVzdF9jbGFpbV9kb2N1bWVudA==',
            'claim_document_filename': 'claim.pdf',
        })

        action = claim.with_user(self.workflow_user).with_context(lang='en_US').action_done()

        self.assertEqual(action['res_model'], 'ab_claim_error_wizard')
        self.assertEqual(action['context']['default_error_message'], 'Please enter the cheque amount.')

    def test_supplier_lookup_uses_normal_costcenter_domain(self):
        Supplier = self.env['ab_costcenter'].sudo()
        supplier_before = self.supplier.read(['name', 'code', 'mobile_phone', 'work_email'])[0]

        results = Supplier.name_search(
            name='',
            domain=[('code', '=like', '1-%'), ('id', '=', self.supplier.id)],
            operator='ilike',
            limit=10,
        )

        supplier_after = self.supplier.read(['name', 'code', 'mobile_phone', 'work_email'])[0]
        self.assertIn(self.supplier.id, [result[0] for result in results])
        self.assertEqual(supplier_before, supplier_after)

    def test_supplier_defaults_are_filled_from_previous_claim(self):
        previous = self._create_claim(supplier_type='withholding_tax')
        previous.write({
            'supplier_section': 'cosmetics',
            'area': 'north',
            'supplier_email': 'supplier@example.com',
            'contact_phone': '01000000001',
            'representative_phone': '01000000002',
        })

        self._set_workflow_group(self.group_secretarial)
        claim = self.env['ab_supplier_claim_cycle'].with_user(self.workflow_user).create({
            'supplier_id': self.supplier.id,
            'num_of_invoice': 1,
            'amount_of_check': 500.0,
            'type_of_invoice': 'original',
        })

        self.assertEqual(claim.supplier_type, 'withholding_tax')
        self.assertEqual(claim.supplier_section, 'cosmetics')
        self.assertEqual(claim.area, 'north')
        self.assertEqual(claim.supplier_email, 'supplier@example.com')
        self.assertEqual(claim.contact_phone, '01000000001')
        self.assertEqual(claim.representative_phone, '01000000002')

    def test_supplier_defaults_do_not_overwrite_claim_values(self):
        previous = self._create_claim(supplier_type='withholding_tax')
        previous.write({
            'supplier_section': 'cosmetics',
            'area': 'north',
            'contact_phone': '01000000001',
        })

        self._set_workflow_group(self.group_secretarial)
        claim = self.env['ab_supplier_claim_cycle'].with_user(self.workflow_user).create({
            'supplier_id': self.supplier.id,
            'supplier_type': 'non_taxable',
            'supplier_section': 'supplies',
            'area': 'south',
            'contact_phone': '01000000003',
            'num_of_invoice': 1,
            'amount_of_check': 500.0,
            'type_of_invoice': 'original',
        })

        self.assertEqual(claim.supplier_type, 'non_taxable')
        self.assertEqual(claim.supplier_section, 'supplies')
        self.assertEqual(claim.area, 'south')
        self.assertEqual(claim.contact_phone, '01000000003')

    def test_reviewer_can_open_claim_with_blocking_issues(self):
        claim = self._create_claim()
        self.env['ab_supplier_claim_issue'].sudo().create({
            'claim_id': claim.id,
            'title': 'Missing approval',
            'description': 'Waiting for approval.',
            'stage': 'inventory',
        })

        self._set_workflow_group(self.group_reviewer)
        reviewer_claim = claim.with_user(self.workflow_user)
        self.assertEqual(len(reviewer_claim.issue_ids), 1)

    def test_secretarial_starts_cycle(self):
        claim = self._create_claim()
        self.assertEqual(claim.status, 'secretarial')
        self._start_cycle(claim)
        self.assertEqual(claim.status, 'inventory')

    def test_department_accept_marks_own_decision_only(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._department_accept(claim, self.group_inventory)
        self.assertEqual(claim.inv_decision, 'accepted')
        self.assertEqual(claim.pur_decision, 'pending')
        self.assertEqual(claim.sup_decision, 'pending')
        self.assertEqual(claim.bank_decision, 'pending')
        self.assertEqual(claim.status, 'inventory')

        self._department_accept(claim, self.group_purchase)
        self.assertEqual(claim.pur_decision, 'accepted')
        self.assertEqual(claim.status, 'inventory')

    def test_accept_alone_does_not_advance(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._department_accept(claim, self.group_inventory)
        self._department_accept(claim, self.group_purchase)
        self.assertEqual(claim.status, 'inventory')

    def test_finish_requires_accept_first(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._set_workflow_group(self.group_inventory)
        with self.assertRaises(UserError):
            claim.with_user(self.workflow_user).action_finish()

    def test_all_finish_advances_to_sign_check(self):
        claim = self._create_claim()
        self._start_cycle(claim)
        self._all_departments_finish(claim)
        self.assertEqual(claim.status, 'sign_check')

    def test_withholding_tax_supplier_requires_tax_accounts_finish(self):
        claim = self._create_claim(supplier_type='withholding_tax')
        self._start_cycle(claim)

        # Sequential workflow: inventory + purchase together → suppliers
        self._department_accept_and_finish(claim, self.group_inventory)
        self._department_accept_and_finish(claim, self.group_purchase)
        self.assertEqual(claim.status, 'suppliers')

        # suppliers → tax_accounts
        self._department_accept_and_finish(claim, self.group_suppliers)
        self.assertEqual(claim.status, 'tax_accounts')
        self.assertEqual(claim.tax_decision, 'pending')

        # tax_accounts → bank_acc → sign_check
        self._department_accept_and_finish(claim, self.group_tax_accounts)
        self.assertEqual(claim.tax_decision, 'accepted')
        self.assertTrue(claim.tax_finished)
        self.assertEqual(claim.status, 'bank_acc')

        self._department_accept_and_finish(claim, self.group_bank_acc)
        self.assertEqual(claim.status, 'sign_check')

    def test_non_withholding_supplier_skips_tax_accounts(self):
        claim = self._create_claim(supplier_type='non_taxable')
        self._start_cycle(claim)

        self._all_departments_finish(claim)

        self.assertEqual(claim.status, 'sign_check')
        self.assertFalse(claim.stage_history_ids.filtered(lambda h: h.stage == 'tax_accounts'))

    def test_department_finish_sets_finished_flag(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._department_accept_and_finish(claim, self.group_inventory)
        self.assertTrue(claim.inv_finished)
        self.assertFalse(claim.pur_finished)
        self.assertEqual(claim.status, 'inventory')

    def test_department_rejection_requires_reason(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._set_workflow_group(self.group_inventory)
        action = claim.with_user(self.workflow_user).action_reject()
        self.assertEqual(action['res_model'], 'ab_claim_error_wizard')

    def test_department_rejection_sets_individual_decision(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._set_workflow_group(self.group_inventory)
        claim.with_user(self.workflow_user).write({'inv_reason': 'Missing documents.'})
        claim.with_user(self.workflow_user).action_reject()
        self.assertEqual(claim.inv_decision, 'rejected')
        self.assertEqual(claim.pur_decision, 'pending')

    def test_department_defer_requires_date_and_reason_then_blocks_finish(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._set_workflow_group(self.group_inventory)
        localized_claim = claim.with_user(self.workflow_user).with_context(lang='ar_001')
        action = localized_claim.action_defer()
        self.assertEqual(action['res_model'], 'ab_supplier_claim_defer_wizard')
        self.assertEqual(action['context']['default_claim_id'], claim.id)
        self.assertEqual(action['context']['default_stage_key'], 'inventory')

        yesterday = fields.Date.subtract(fields.Date.context_today(claim), days=1)
        wizard = self.env['ab_supplier_claim_defer_wizard'].with_user(self.workflow_user).with_context(
            lang='ar_001'
        ).create({
            'claim_id': claim.id,
            'stage_key': 'inventory',
            'expected_completion_date': yesterday,
            'deferral_reason': 'Waiting for supplier documents.',
        })
        wizard.action_confirm()
        self.assertEqual(claim.inv_decision, 'deferred')
        self.assertEqual(claim.department_decision, 'deferred')
        self.assertEqual(claim.inv_deferred_overdue_days, 1)
        deferred_history = claim.stage_history_ids.filtered(
            lambda history: history.stage == 'inventory' and history.decision == 'deferred'
        )[-1]
        self.assertNotIn('Expected completion date:', deferred_history.notes)
        self.assertNotIn('Reason:', deferred_history.notes)
        self.assertNotIn('Actual overdue days:', deferred_history.notes)
        self.assertIn('أيام التأخير الفعلية: 1', deferred_history.notes)

        tomorrow = fields.Date.add(fields.Date.context_today(claim), days=1)
        claim.with_user(self.workflow_user).write({'inv_deferred_expected_date': tomorrow})
        timeline = localized_claim.action_get_timeline_data()['timeline']
        inventory_stage = next(
            entry for entry in timeline
            if entry.get('type') == 'stage' and entry.get('stage') == 'inventory'
        )
        self.assertTrue(inventory_stage['show_defer_overdue_days'])
        self.assertEqual(inventory_stage['defer_overdue_days'], 0)
        self.assertEqual(inventory_stage['defer_remaining_days'], 1)
        self.assertIn('أيام التأخير الفعلية: 0', inventory_stage['notes'])
        timeline_html = localized_claim._render_timeline_html()
        self.assertIn('الأيام المتبقية حتى الوقت المتوقع للتأجيل: 1 أيام', timeline_html)
        self.assertIn('scc-timeline-defer-overdue is-due-soon', timeline_html)
        localized_claim.invalidate_recordset(['timeline_display'])
        self.assertIn('الأيام المتبقية حتى الوقت المتوقع للتأجيل: 1 أيام', localized_claim.timeline_display)

        with self.assertRaises(UserError):
            claim.with_user(self.workflow_user).action_finish()

    def test_deferred_department_escalation_counts_after_expected_date(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        old_pending_date = fields.Datetime.subtract(fields.Datetime.now(), days=3)
        inventory_pending = self.env['ab_supplier_claim_stage_history'].search([
            ('claim_id', '=', claim.id),
            ('stage', '=', 'inventory'),
            ('decision', '=', 'pending'),
        ], limit=1)
        inventory_pending.write({'action_date': old_pending_date})

        self._set_workflow_group(self.group_inventory)
        tomorrow = fields.Date.add(fields.Date.context_today(claim), days=1)
        claim.with_user(self.workflow_user).write({
            'inv_deferred_expected_date': tomorrow,
            'inv_deferred_reason': 'Waiting for supplier documents.',
        })
        claim.with_user(self.workflow_user).action_defer()

        self.env['ir.config_parameter'].sudo().set_param('supplier_claim.escalation_sla_seconds', '0')
        self.env['ab_supplier_claim_cycle']._cron_escalate_overdue_stages()
        inventory_escalations = self.env['ab_supplier_claim_stage_history'].search_count([
            ('claim_id', '=', claim.id),
            ('stage', '=', 'inventory'),
            ('decision', '=', 'escalated'),
        ])
        self.assertEqual(inventory_escalations, 0)

        yesterday = fields.Date.subtract(fields.Date.context_today(claim), days=1)
        claim.with_user(self.workflow_user).write({'inv_deferred_expected_date': yesterday})
        self.env['ab_supplier_claim_cycle']._cron_escalate_overdue_stages()
        inventory_escalations = self.env['ab_supplier_claim_stage_history'].search_count([
            ('claim_id', '=', claim.id),
            ('stage', '=', 'inventory'),
            ('decision', '=', 'escalated'),
        ])
        self.assertEqual(inventory_escalations, 1)

    def test_all_departments_can_act_simultaneously(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._set_workflow_group(self.group_purchase)
        claim.with_user(self.workflow_user).action_accept()
        self.assertEqual(claim.pur_decision, 'accepted')

        self._set_workflow_group(self.group_inventory)
        claim.with_user(self.workflow_user).action_accept()
        self.assertEqual(claim.inv_decision, 'accepted')

    def test_direct_status_jump_is_blocked(self):
        claim = self._create_claim()
        with self.assertRaises(AccessError):
            claim.with_user(self.workflow_user).write({'status': 'sign_check'})

    def test_stage_history_created_on_create(self):
        claim = self._create_claim()
        self.assertEqual(len(claim.stage_history_ids), 1)
        self.assertIn('secretarial', claim.stage_history_ids.mapped('stage'))

    def test_stage_history_on_accept(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._department_accept(claim, self.group_inventory)
        inv_history = claim.stage_history_ids.filtered(lambda h: h.stage == 'inventory')
        self.assertTrue(inv_history)
        self.assertEqual(inv_history[-1].decision, 'accepted')

    def test_cheque_delivery_documents_required(self):
        claim = self._create_claim()
        self._start_cycle(claim)
        self._all_departments_finish(claim)
        self.assertEqual(claim.status, 'sign_check')

        wizard = self.env['ab_check_delivery_wizard'].with_user(self.workflow_user).create({
            'claim_id': claim.id,
            'check_delivery_status': 'check_delivered',
        })

        action = wizard.action_confirm()
        self.assertEqual(action['type'], 'ir.actions.act_window_close')
        self.assertEqual(claim.status, 'supplier_notification')

        self._set_workflow_group(self.group_secretarial)
        claim.with_user(self.workflow_user).write({
            'contact_result': 'contacted',
            'contact_name': 'Supplier Rep',
            'contact_phone': '01000000000',
            'sub_delivery_status': 'ready',
        })
        action = claim.with_user(self.workflow_user).action_supplier_notified()
        self.assertEqual(action['res_model'], 'ab_claim_error_wizard')

        claim.with_user(self.workflow_user).write({
            'cheque_image': b'ZmFrZV9jaGVxdWVfcG5n',
            'cheque_image_filename': 'cheque.png',
            'supplier_id_image': b'ZmFrZV9pZF9wbmc=',
            'supplier_id_image_filename': 'id.png',
        })
        claim.with_user(self.workflow_user).action_supplier_notified()
        self.assertTrue(claim.supplier_notified)

    def test_department_visibility_tracks_pending_department_work(self):
        claim = self._create_claim()
        self._start_cycle(claim)
        Claim = self.env['ab_supplier_claim_cycle']

        self.assertEqual(Claim.with_user(self.inventory_user).search_count([('id', '=', claim.id)]), 1)
        self.assertEqual(Claim.with_user(self.purchase_user).search_count([('id', '=', claim.id)]), 1)

        claim.with_user(self.inventory_user).action_accept()
        self.assertEqual(Claim.with_user(self.inventory_user).search_count([('id', '=', claim.id)]), 1)
        claim.with_user(self.inventory_user).action_finish()

        self.assertEqual(Claim.with_user(self.inventory_user).search_count([('id', '=', claim.id)]), 0)
        self.assertEqual(Claim.with_user(self.purchase_user).search_count([('id', '=', claim.id)]), 1)
        with self.assertRaises(AccessError):
            claim.with_user(self.inventory_user).read(['name'])
        self.assertEqual(Claim.with_user(self.admin_user).search_count([('id', '=', claim.id)]), 1)
        self.assertEqual(Claim.with_user(self.secretarial_user).search_count([('id', '=', claim.id)]), 1)

    def test_purchase_finish_advances_to_suppliers_without_access_error(self):
        claim = self._create_claim()
        self._start_cycle(claim)
        Claim = self.env['ab_supplier_claim_cycle']

        claim.with_user(self.inventory_user).action_accept()
        claim.with_user(self.inventory_user).action_finish()
        claim.with_user(self.purchase_user).action_accept()
        action = claim.with_user(self.purchase_user).action_finish()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(claim.status, 'suppliers')
        self.assertEqual(Claim.with_user(self.purchase_user).search_count([('id', '=', claim.id)]), 0)
        self.assertEqual(Claim.with_user(self.suppliers_user).search_count([('id', '=', claim.id)]), 1)

    def test_department_notes_are_scoped_and_copied_on_accept(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        claim.with_user(self.inventory_user).write({'inv_notes': 'Apply 5% discount on damaged items.'})
        with self.assertRaises(AccessError):
            claim.with_user(self.purchase_user).write({'inv_notes': 'Purchase cannot edit inventory notes.'})

        claim.with_user(self.inventory_user).action_accept()
        accepted_history = claim.stage_history_ids.filtered(
            lambda history: history.stage == 'inventory' and history.decision == 'accepted'
        )[-1]
        self.assertIn('Apply 5% discount on damaged items.', accepted_history.notes)

        with self.assertRaises(AccessError):
            claim.with_user(self.inventory_user).write({'inv_notes': 'Changed after decision.'})

        claim.with_user(self.admin_user).write({'inv_notes': 'Admin correction.'})
        self.assertEqual(claim.inv_notes, 'Admin correction.')

    def test_department_notes_are_copied_on_reject_and_defer(self):
        reject_claim = self._create_claim()
        self._start_cycle(reject_claim)
        reject_claim.with_user(self.inventory_user).write({
            'inv_notes': 'Deduction note for short shipment.',
            'inv_reason': 'Missing stamped invoice.',
        })
        reject_claim.with_user(self.inventory_user).action_reject()
        rejected_history = reject_claim.stage_history_ids.filtered(
            lambda history: history.stage == 'inventory' and history.decision == 'rejected'
        )[-1]
        self.assertIn('Missing stamped invoice.', rejected_history.notes)
        self.assertIn('Deduction note for short shipment.', rejected_history.notes)

        defer_claim = self._create_claim()
        self._start_cycle(defer_claim)
        defer_claim.with_user(self.inventory_user).write({'inv_notes': 'Awaiting deduction confirmation.'})
        tomorrow = fields.Date.add(fields.Date.context_today(defer_claim), days=1)
        wizard = self.env['ab_supplier_claim_defer_wizard'].with_user(self.inventory_user).create({
            'claim_id': defer_claim.id,
            'stage_key': 'inventory',
            'expected_completion_date': tomorrow,
            'deferral_reason': 'Waiting for supplier statement.',
        })
        wizard.action_confirm()
        deferred_history = defer_claim.stage_history_ids.filtered(
            lambda history: history.stage == 'inventory' and history.decision == 'deferred'
        )[-1]
        self.assertIn('Waiting for supplier statement.', deferred_history.notes)
        self.assertIn('Awaiting deduction confirmation.', deferred_history.notes)

    def test_account_statement_invoice_type_is_valid(self):
        for invoice_type in ('original', 'copy', 'account_statement'):
            claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial_user).create({
                'supplier_id': self.supplier.id,
                'supplier_type': 'non_taxable',
                'supplier_section': 'medicine',
                'num_of_invoice': 1,
                'area': 'south',
                'amount_of_check': 750.0,
                'type_of_invoice': invoice_type,
                'claim_document': b'dGVzdF9jbGFpbV9kb2N1bWVudA==',
                'claim_document_filename': 'claim.pdf',
            })
            self.assertEqual(claim.type_of_invoice, invoice_type)

    def test_department_notes_do_not_change_amounts(self):
        claim = self._create_claim(supplier_type='withholding_tax')
        self._start_cycle(claim)
        amount = claim.amount_of_check
        tax_amount = claim.tax_amount
        net_payable = claim.net_payable

        claim.with_user(self.inventory_user).write({'inv_notes': 'Discount note only; do not calculate.'})

        self.assertEqual(claim.amount_of_check, amount)
        self.assertEqual(claim.tax_amount, tax_amount)
        self.assertEqual(claim.net_payable, net_payable)
