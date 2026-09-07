from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.workflow_guard import WORKFLOW_WRITE_TOKEN


@tagged('post_install', '-at_install')
class TestReviewSkip(TransactionCase):
    def setUp(self):
        super().setUp()
        users = self.env['res.users'].search([])
        self.secretary = users.filtered(lambda u: u.has_group('ab_supplier_claim_cycle.supplier_claim_group_user'))[:1]
        self.admin = users.filtered(lambda u: u.has_group('ab_supplier_claim_cycle.supplier_claim_group_admin'))[:1]
        self.department = users.filtered(lambda u: u.has_group('ab_supplier_claim_workflow.supplier_claim_group_purchase')
                                         and not u.has_group('ab_supplier_claim_cycle.supplier_claim_group_admin')
                                         and not u.has_group('ab_supplier_claim_cycle.supplier_claim_group_user'))[:1]
        self.suppliers = users.filtered(lambda u: u.has_group('ab_supplier_claim_workflow.supplier_claim_group_suppliers')
                                        and not u.has_group('ab_supplier_claim_cycle.supplier_claim_group_admin'))[:1]
        self.assertTrue(self.secretary and self.admin and self.department and self.suppliers)
        self.model = self.env['ab_supplier_claim_cycle']
        for method in ('_notify_claim_created_to_module_users', '_notify_department_turn_started',
                       '_notify_secretarial_department_accepted'):
            mock = self.enterContext(patch.object(type(self.model), method, return_value=False))
            if method == '_notify_department_turn_started':
                self.notify = mock
        supplier = self.env['ab_costcenter'].search([('code', '=like', '1-%')], limit=1)
        self.claim = self.model.with_user(self.secretary).create({
            'supplier_id': supplier.id, 'supplier_type': 'non_taxable', 'supplier_section': 'medicine',
            'num_of_invoice': 2, 'area': 'south', 'amount_of_check': 1000,
            'type_of_invoice': 'original', 'claim_document': b'dGVzdA==',
            'claim_document_filename': 'claim.pdf',
        })

    def skip(self, user=None, reason='Review not required'):
        return self.env['ab_supplier_claim_skip_wizard'].with_user(user or self.secretary).create({
            'claim_id': self.claim.id, 'reason': reason,
        }).action_confirm()

    def test_secretary_and_admin_can_open(self):
        for user in (self.secretary, self.admin):
            self.assertEqual(self.claim.with_user(user).action_open_skip_reviews()['res_model'], 'ab_supplier_claim_skip_wizard')

    def test_admin_can_confirm(self):
        self.skip(self.admin)
        history = self.claim.sudo().stage_history_ids.filtered(lambda h: h.decision == 'skipped')
        self.assertEqual(history.user_id, self.admin)
        self.assertEqual(len(history.with_user(self.admin).read(['notes'])), 2)

    def test_department_cannot_skip(self):
        with self.assertRaises(AccessError):
            self.claim.with_user(self.department).action_open_skip_reviews()
        with self.assertRaises(AccessError):
            self.skip(self.department)
        with self.assertRaises(AccessError):
            self.claim.with_user(self.department)._skip_inventory_purchase('Forged')

    def test_reason_required(self):
        with self.assertRaises(ValidationError):
            self.skip(reason='   ')
        self.assertEqual(self.claim.status, 'secretarial')

    def test_skip_history_timeline_and_notification(self):
        self.skip(reason='<script>test</script> No review')
        self.assertEqual(self.claim.status, 'suppliers')
        self.assertEqual((self.claim.inv_decision, self.claim.pur_decision), ('skipped', 'skipped'))
        self.assertFalse(self.claim.inv_finished or self.claim.pur_finished)
        self.assertEqual(self.claim.sup_decision, 'pending')
        history = self.claim.stage_history_ids.filtered(lambda h: h.decision == 'skipped')
        self.assertEqual(set(history.mapped('stage')), {'inventory', 'purchase'})
        self.assertEqual(history.user_id, self.secretary)
        self.assertTrue(all(h.action_date and h.notes == self.claim.review_skip_reason for h in history))
        stages = self.claim.action_get_timeline_data()['timeline']
        skipped = [s for s in stages if s.get('stage') in ('inventory', 'purchase')]
        self.assertTrue(all(s['is_skipped'] and not s['is_completed'] and not s['is_current'] for s in skipped))
        html = self.claim.with_context(lang='en_US')._render_timeline_html()
        self.assertIn('Skipped', html)
        self.assertNotIn('<script>', html)
        self.notify.assert_called_once_with('suppliers')
        self.assertFalse(self.claim.stage_history_ids.filtered(lambda h: h.stage in ('inventory', 'purchase') and h.decision == 'pending'))
        self.assertEqual(self.claim.amount_of_check, 1000)

    def test_skip_history_and_reason_are_immutable(self):
        self.skip()
        history = self.claim.stage_history_ids.filtered(lambda h: h.decision == 'skipped')
        with self.assertRaises(AccessError):
            history.write({'notes': 'Changed'})
        with self.assertRaises(AccessError):
            history.with_user(self.admin).unlink()
        with self.assertRaises(AccessError):
            self.claim.write({'review_skip_reason': False})
        with self.assertRaises(AccessError):
            history.copy()

    def test_cannot_skip_after_start(self):
        self.claim.action_done()
        with self.assertRaises(UserError):
            self.skip()

    def test_cannot_skip_twice(self):
        self.skip()
        with self.assertRaises(UserError):
            self.skip()

    def test_direct_writes_and_forged_context_are_blocked(self):
        self.claim.action_done()
        with self.assertRaises(AccessError):
            self.claim.with_user(self.department).action_done()
        for values in ({'status': 'suppliers'}, {'inv_decision': 'skipped'},
                       {'pur_decision': 'accepted'}, {'pur_finished': True}):
            with self.assertRaises(AccessError):
                self.claim.with_user(self.department).write(values)
            with self.assertRaises(AccessError):
                self.claim.with_user(self.department).with_context(supplier_claim_internal_write=True).write(values)

    def test_normal_parallel_review_still_required(self):
        self.claim.action_done()
        self.assertEqual(self.claim.status, 'inventory')
        self.assertEqual((self.claim.inv_decision, self.claim.pur_decision), ('pending', 'pending'))
        self.assertEqual([c.args[0] for c in self.notify.call_args_list], ['inventory', 'purchase'])
        self.claim.with_user(self.department).action_accept()
        self.assertEqual(self.claim.status, 'inventory')
        self.assertEqual(self.claim.pur_decision, 'accepted')
        self.assertFalse(self.claim.review_skip_reason)

    def test_rejection_deferral_and_close_validation_remain(self):
        self.skip()
        claim = self.claim.with_user(self.suppliers)
        result = claim.action_defer()
        self.assertEqual(result['res_model'], 'ab_supplier_claim_defer_wizard')
        self.env['ab_supplier_claim_defer_wizard'].with_user(self.suppliers).create({
            'claim_id': claim.id, 'stage_key': 'suppliers',
            'expected_completion_date': fields.Date.today() + timedelta(days=1),
            'deferral_reason': 'Awaiting documents',
        }).action_confirm()
        self.assertEqual(self.claim.sup_decision, 'deferred')
        self.assertTrue(self.claim.action_validate_close())
        with self.assertRaises(UserError):
            self.claim.action_close_claim()

    def test_skip_keeps_initial_required_information(self):
        self.claim.write({'num_of_invoice': 0})
        with self.assertRaises(ValidationError):
            self.skip()

    def test_sla_only_considers_suppliers_after_skip(self):
        self.skip()
        self.claim.stage_history_ids.filtered(lambda h: h.stage == 'suppliers').write({
            'action_date': fields.Datetime.now() - timedelta(days=30),
        })
        original_search = type(self.model).search
        def scoped_search(model, domain, *args, **kwargs):
            return original_search(model, fields.Domain(domain) & fields.Domain('id', '=', self.claim.id), *args, **kwargs)
        with patch.object(type(self.model), 'search', scoped_search), patch.object(type(self.model), '_send_escalation_notification', return_value=False):
            self.model._cron_escalate_overdue_stages()
        self.assertFalse(self.claim.stage_history_ids.filtered(lambda h: h.stage in ('inventory', 'purchase') and h.decision.startswith('escalated')))
        self.assertTrue(self.claim.stage_history_ids.filtered(lambda h: h.stage == 'suppliers' and h.decision == 'escalated'))

    def test_suppliers_accept_advances_remaining_workflow(self):
        self.skip()
        self.claim.with_user(self.suppliers).action_accept()
        self.assertEqual(self.claim.status, 'bank_acc')
        self.assertEqual(self.claim.inv_decision, 'skipped')
        self.notify.assert_called_with('bank_acc')

    def test_rejection_requires_reason_and_records_it(self):
        self.skip()
        claim = self.claim.with_user(self.suppliers)
        self.assertEqual(claim.action_reject()['res_model'], 'ab_claim_error_wizard')
        claim.write({'sup_reason': 'Missing supporting documents'})
        claim.action_reject()
        self.assertEqual(self.claim.sup_decision, 'rejected')
        self.assertTrue(self.claim.stage_history_ids.filtered(lambda h: h.stage == 'suppliers' and h.decision == 'rejected'))

    def test_standard_review_advances_only_after_both_approvals(self):
        self.claim.action_done()
        self.claim.with_context(supplier_claim_internal_write=WORKFLOW_WRITE_TOKEN).write({
            'inv_decision': 'accepted', 'inv_finished': True,
        })
        self.claim._try_advance_from_parallel()
        self.assertEqual(self.claim.status, 'inventory')
        self.claim.with_user(self.department).action_accept()
        self.assertEqual(self.claim.status, 'suppliers')
        self.assertFalse(self.claim.review_skip_reason)

    def _run_claim_sla(self):
        original_search = type(self.model).search

        def scoped_search(model, domain, *args, **kwargs):
            return original_search(
                model, fields.Domain(domain) & fields.Domain('id', '=', self.claim.id),
                *args, **kwargs,
            )

        with patch.object(type(self.model), 'search', scoped_search), patch.object(
            type(self.model), '_send_escalation_notification', return_value=False,
        ):
            self.model._cron_escalate_overdue_stages()
        return self.claim.stage_history_ids.filtered(lambda history: history.decision == 'escalated')

    def _age_pending_review_history(self):
        self.claim.stage_history_ids.filtered(lambda history: history.decision == 'pending').write({
            'action_date': fields.Datetime.now() - timedelta(days=30),
        })

    def test_completed_purchase_does_not_escalate_while_inventory_pending(self):
        self.claim.action_done()
        self.claim.with_user(self.department).action_accept()
        self.assertEqual(self.claim.pur_decision, 'accepted')
        self.assertTrue(self.claim.pur_finished)
        self.assertEqual(self.claim.status, 'inventory')
        self._age_pending_review_history()
        history_before = self.claim.stage_history_ids
        escalations = self._run_claim_sla()
        self.assertEqual(set(escalations.mapped('stage')), {'inventory'})
        self.assertTrue(history_before <= self.claim.stage_history_ids)
        self.assertEqual(self._run_claim_sla(), escalations)

    def test_completed_inventory_does_not_escalate_while_purchase_pending(self):
        self.claim.action_done()
        self.claim.with_context(supplier_claim_internal_write=WORKFLOW_WRITE_TOKEN).write({
            'inv_decision': 'accepted', 'inv_finished': True,
        })
        self._age_pending_review_history()
        self.assertEqual(set(self._run_claim_sla().mapped('stage')), {'purchase'})

    def test_unfinished_approval_remains_eligible_for_escalation(self):
        self.claim.action_done()
        self.claim.with_context(supplier_claim_internal_write=WORKFLOW_WRITE_TOKEN).write({
            'pur_decision': 'accepted', 'pur_finished': False,
        })
        self._age_pending_review_history()
        self.assertEqual(set(self._run_claim_sla().mapped('stage')), {'inventory', 'purchase'})

    def test_deferred_purchase_escalates_only_after_its_deadline(self):
        self.claim.action_done()
        self.env['ab_supplier_claim_defer_wizard'].with_user(self.department).create({
            'claim_id': self.claim.id, 'stage_key': 'purchase',
            'expected_completion_date': fields.Date.today() + timedelta(days=1),
            'deferral_reason': 'Waiting for documents',
        }).action_confirm()
        self._age_pending_review_history()
        self.assertEqual(set(self._run_claim_sla().mapped('stage')), {'inventory'})
        self.claim.with_user(self.department).write({
            'pur_deferred_expected_date': fields.Date.today() - timedelta(days=30),
        })
        self.assertEqual(set(self._run_claim_sla().mapped('stage')), {'inventory', 'purchase'})
