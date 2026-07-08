from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestSupplierClaimWorkflow(TransactionCase):
    def setUp(self):
        super().setUp()
        self.group_user = self.env.ref('base.group_user')
        self.group_secretarial = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_user')
        self.group_inventory = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_inventory')
        self.group_purchase = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_purchase')
        self.group_suppliers = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_suppliers')
        self.group_tax_accounts = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_tax_accounts')
        self.group_bank_acc = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_bank_acc')
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
            self.supplier.with_context(replication=True).sudo().write({'supplier_type': False})

    def _set_workflow_group(self, group):
        self.workflow_user.write({
            'group_ids': [(3, g.id) for g in self.workflow_groups] + [
                (4, self.group_user.id),
                (4, group.id),
            ],
        })
        self.env.invalidate_all()

    def _create_claim(self):
        self._set_workflow_group(self.group_secretarial)
        return self.env['ab_supplier_claim_cycle'].with_user(self.workflow_user).create({
            'supplier_id': self.supplier.id,
            'num_of_invoice': 2,
            'area': 'south',
            'amount_of_check': '1000',
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
        self._department_accept(claim, self.group_suppliers)
        self._department_accept(claim, self.group_bank_acc)
        # All accepted but none finished — should NOT advance
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
        self.supplier.with_context(replication=True).sudo().write({'supplier_type': 'withholding_tax'})
        claim = self._create_claim()
        self._start_cycle(claim)

        for group in (self.group_inventory, self.group_purchase, self.group_suppliers, self.group_bank_acc):
            self._department_accept_and_finish(claim, group)

        self.assertEqual(claim.status, 'inventory')
        self.assertEqual(claim.tax_decision, 'pending')

        self._department_accept_and_finish(claim, self.group_tax_accounts)
        self.assertEqual(claim.tax_decision, 'accepted')
        self.assertTrue(claim.tax_finished)
        self.assertEqual(claim.status, 'sign_check')

    def test_non_withholding_supplier_skips_tax_accounts(self):
        self.supplier.with_context(replication=True).sudo().write({'supplier_type': 'non_taxable'})
        claim = self._create_claim()
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
        self.assertEqual(action['res_model'], 'ab.claim.error.wizard')

    def test_department_rejection_sets_individual_decision(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._set_workflow_group(self.group_inventory)
        claim.with_user(self.workflow_user).write({'inv_reason': 'Missing documents.'})
        claim.with_user(self.workflow_user).action_reject()
        self.assertEqual(claim.inv_decision, 'rejected')
        self.assertEqual(claim.pur_decision, 'pending')

    def test_all_departments_can_act_simultaneously(self):
        claim = self._create_claim()
        self._start_cycle(claim)

        self._set_workflow_group(self.group_purchase)
        claim.with_user(self.workflow_user).action_accept()
        self.assertEqual(claim.pur_decision, 'accepted')

        self._set_workflow_group(self.group_suppliers)
        claim.with_user(self.workflow_user).action_accept()
        self.assertEqual(claim.sup_decision, 'accepted')

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

        wizard = self.env['ab.check.delivery.wizard'].with_user(self.workflow_user).create({
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
        self.assertEqual(action['res_model'], 'ab.claim.error.wizard')
        self.assertTrue('cheque image' in action['context'].get('default_error_message', '').lower()
                        or 'supplier id image' in action['context'].get('default_error_message', '').lower())

        claim.with_user(self.workflow_user).write({
            'cheque_image': b'ZmFrZV9jaGVxdWVfcG5n',
            'cheque_image_filename': 'cheque.png',
            'supplier_id_image': b'ZmFrZV9pZF9wbmc=',
            'supplier_id_image_filename': 'id.png',
        })
        claim.with_user(self.workflow_user).action_supplier_notified()
        self.assertTrue(claim.supplier_notified)
