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
        self.group_bank_acc = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_bank_acc')
        self.group_admin = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_admin')
        self.group_reviewer = self.env.ref('ab_supplier_claim_cycle.supplier_claim_group_reviewer')
        self.workflow_groups = (
            self.group_secretarial
            | self.group_inventory
            | self.group_purchase
            | self.group_suppliers
            | self.group_bank_acc
            | self.group_admin
            | self.group_reviewer
        )
        self.workflow_user = self.env.ref('base.user_admin').sudo()

        seed = (self.env['ab_costcenter'].sudo().search([], order='id desc', limit=1).id or 0) + 1000000
        self.supplier = self.env['ab_costcenter'].sudo().create({
            'name': 'Supplier Claim Test Supplier',
            'code': '1-SCT%s' % seed,
        })

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
        })

    def _move_to_inventory(self, claim):
        self._set_workflow_group(self.group_secretarial)
        claim.with_user(self.workflow_user).action_done()

    def _move_to_next_n_stages(self, claim, count):
        """Helper: move claim through N accepted stages starting from current status.
        Assumes each department auto accepts and moves forward.
        """
        stages = ['inventory', 'purchase', 'suppliers', 'bank_acc', 'sign_check']
        idx = stages.index(claim.status) if claim.status in stages else 0
        for i in range(count):
            if idx + i >= len(stages):
                break
            next_stage = stages[idx + i]
            group_map = {
                'inventory': self.group_inventory,
                'purchase': self.group_purchase,
                'suppliers': self.group_suppliers,
                'bank_acc': self.group_bank_acc,
                'sign_check': self.group_secretarial,
            }
            self._set_workflow_group(group_map.get(next_stage, self.group_secretarial))
            claim.with_user(self.workflow_user).action_accept()
            claim.with_user(self.workflow_user).action_done()

    def test_department_confirm_moves_only_to_next_stage(self):
        claim = self._create_claim()
        self.assertEqual(claim.status, 'secretarial')

        self._move_to_inventory(claim)
        self.assertEqual(claim.status, 'inventory')

        self._set_workflow_group(self.group_inventory)
        claim.with_user(self.workflow_user).action_accept()
        self.assertEqual(claim.department_decision, 'accepted')

        claim.with_user(self.workflow_user).action_done()
        self.assertEqual(claim.status, 'purchase')
        self.assertEqual(claim.department_decision, 'pending')

    def test_non_current_department_cannot_edit_or_move(self):
        claim = self._create_claim()
        self._move_to_inventory(claim)

        self._set_workflow_group(self.group_purchase)
        with self.assertRaises(AccessError):
            claim.with_user(self.workflow_user).write({'amount_of_check': '1200'})

        with self.assertRaises(AccessError):
            claim.with_user(self.workflow_user).action_accept()

    def test_direct_status_jump_is_blocked(self):
        claim = self._create_claim()

        with self.assertRaises(AccessError):
            claim.with_user(self.workflow_user).write({'status': 'bank_acc'})

        claim.with_user(self.workflow_user).action_done()
        self.assertEqual(claim.status, 'inventory')

    def test_rejection_requires_reason(self):
        claim = self._create_claim()
        self._move_to_inventory(claim)

        self._set_workflow_group(self.group_inventory)
        with self.assertRaises(ValidationError):
            claim.with_user(self.workflow_user).action_reject()

        claim.with_user(self.workflow_user).write({'delay_reason': 'Missing supplier documents.'})
        claim.with_user(self.workflow_user).action_reject()
        self.assertEqual(claim.department_decision, 'rejected')

    def test_stage_history_created_on_create(self):
        claim = self._create_claim()
        histories = claim.stage_history_ids
        self.assertEqual(len(histories), 1)
        stages = histories.mapped('stage')
        self.assertIn('secretarial', stages)

    def test_stage_history_on_accept(self):
        claim = self._create_claim()
        self._move_to_inventory(claim)

        self._set_workflow_group(self.group_inventory)
        claim.with_user(self.workflow_user).action_accept()

        inv_history = claim.stage_history_ids.filtered(lambda h: h.stage == 'inventory')
        self.assertTrue(inv_history)
        self.assertEqual(inv_history[-1].decision, 'accepted')

    def test_cheque_delivery_documents_required(self):
        """Verify cheque delivery validates both required images."""
        claim = self._create_claim()
        self._move_to_inventory(claim)

        # Move through inventory, purchase, suppliers, bank_acc → sign_check
        self._move_to_next_n_stages(claim, 4)
        self.assertEqual(claim.status, 'sign_check')

        # Accept at sign_check
        self._set_workflow_group(self.group_secretarial)
        claim.with_user(self.workflow_user).action_accept()

        # Open wizard — simulates Complete Sign Check button
        wizard = self.env['ab.check.delivery.wizard'].with_user(self.workflow_user).create({
            'claim_id': claim.id,
            'check_delivery_status': 'check_delivered',
        })

        # Validate returns error wizard (dict) because no images
        action = wizard.action_confirm()
        self.assertEqual(action['res_model'], 'ab.claim.error.wizard')
        self.assertTrue('cheque image' in action['context'].get('default_error_message', '').lower()
                        or 'supplier id image' in action['context'].get('default_error_message', '').lower())

        # Add images and retry
        claim.with_user(self.workflow_user).write({
            'cheque_image': b'fake_cheque_png',
            'cheque_image_filename': 'cheque.png',
            'supplier_id_image': b'fake_id_png',
            'supplier_id_image_filename': 'id.png',
        })
        action = wizard.action_confirm()
        self.assertEqual(action['type'], 'ir.actions.act_window_close')
        self.assertEqual(claim.status, 'supplier_notification')
