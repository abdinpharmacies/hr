from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tools import config
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSupplierClaimNotificationGate(TransactionCase):
    PARAMETER = 'supplier_claim.telegram_notifications_enabled'

    def setUp(self):
        super().setUp()
        self.Model = self.env['ab_supplier_claim_cycle']
        self.Parameter = self.env['ir.config_parameter'].sudo()
        self.Registration = self.env['ab_supplier_claim_telegram_registration'].sudo()
        self.registration = self.Registration.search([
            ('active', '=', True), ('workflow_department', '=', 'suppliers'),
            ('telegram_connected', '=', True), ('employee_id.user_id', '!=', False),
        ], limit=1)
        self.assertTrue(self.registration, 'A connected Suppliers registration is required for replica tests.')
        self.manager = self.registration.employee_id.user_id
        self.secretary = self.env['res.users'].search([]).filtered(
            lambda user: user.has_group('ab_supplier_claim_cycle.supplier_claim_group_user')
        )[:1]
        self.supplier = self.env['ab_costcenter'].search([('code', '=like', '1-%')], limit=1)
        self.send = self.enterContext(patch.object(
            type(self.env['ab_telegram_bot']), 'send_message', return_value={'sent': True},
        ))
        # Exercise the real notification branches; only the transport is mocked.
        self.enterContext(patch.dict(config.options, {'test_enable': False}))

    def _new_claim(self):
        return self.Model.with_user(self.secretary).with_context(mail_notify_force_send=False).create({
            'supplier_id': self.supplier.id, 'supplier_type': 'non_taxable',
            'supplier_section': 'medicine', 'num_of_invoice': 1, 'area': 'south',
            'amount_of_check': 1, 'type_of_invoice': 'original',
            'claim_document': b'dGVzdA==', 'claim_document_filename': 'test.txt',
        })

    def _run_automatic_escalation(self, claim):
        claim.action_done()
        claim.stage_history_ids.filtered(lambda history: history.decision == 'pending').write({
            'action_date': fields.Datetime.now() - timedelta(days=30),
        })
        original_search = type(self.Model).search
        details = claim._resolve_escalation_details(stage_key='inventory')
        details['manager_users'] = [self.manager]

        def scoped_search(model, domain, *args, **kwargs):
            return original_search(
                model, fields.Domain(domain) & fields.Domain('id', '=', claim.id), *args, **kwargs,
            )

        with patch.object(type(self.Model), 'search', scoped_search), patch.object(
            type(self.Model), '_resolve_escalation_details', return_value=details,
        ):
            self.Model.with_context(mail_notify_force_send=False)._cron_escalate_overdue_stages()
        self.assertTrue(claim.stage_history_ids.filtered(lambda history: history.decision == 'escalated'))

    def test_missing_and_false_disable_every_notification_path(self):
        for value in (False, 'False'):
            with self.subTest(value=value):
                self.Parameter.set_param(self.PARAMETER, value)
                self.send.reset_mock()
                self.assertFalse(self.Model._supplier_claim_telegram_notifications_enabled())
                claim = self._new_claim()
                claim._notify_department_turn_started('suppliers')
                claim._send_escalation_notification(self.manager, stage_key='suppliers')
                self._run_automatic_escalation(claim)
                self.send.assert_not_called()
                self.assertTrue(claim.message_ids)
                self.assertTrue(claim.activity_ids or claim.escalation_ids)

    def test_true_restores_creation_turn_and_manual_escalation(self):
        self.Parameter.set_param(self.PARAMETER, 'True')
        claim = self._new_claim()
        self.assertTrue(self.send.called)
        self.send.reset_mock()
        claim._notify_department_turn_started('suppliers')
        self.assertTrue(self.send.called)
        self.assertIn(self.registration.telegram_account_id.chat_id, [call.args[0] for call in self.send.call_args_list])
        self.send.reset_mock()
        claim._send_escalation_notification(self.manager, stage_key='suppliers')
        self.send.assert_called_once()

    def test_true_restores_automatic_escalation(self):
        self.Parameter.set_param(self.PARAMETER, 'True')
        claim = self._new_claim()
        self.send.reset_mock()
        self._run_automatic_escalation(claim)
        self.assertGreaterEqual(self.send.call_count, 2)

    def test_toggling_preserves_registration_and_manager_resolution(self):
        fields_to_read = ['employee_id', 'workflow_department', 'manager_department', 'active', 'telegram_account_id']
        records = self.Registration.with_context(active_test=False).search([])
        before = records.read(fields_to_read)
        self.Parameter.set_param(self.PARAMETER, 'False')
        claim = self._new_claim()
        disabled = claim._resolve_escalation_details(stage_key='suppliers')
        self.Parameter.set_param(self.PARAMETER, 'True')
        enabled = claim._resolve_escalation_details(stage_key='suppliers')
        self.assertEqual(disabled, enabled)
        self.assertEqual(records.read(fields_to_read), before)
        self.assertFalse(self.env.ref('ab_supplier_claim_workflow_telegram.ir_cron_ab_supplier_claim_telegram_import').active)

    def test_disabling_does_not_gate_generic_telegram_service(self):
        self.Parameter.set_param(self.PARAMETER, 'False')
        bot = self.env['ab_telegram_bot']
        # Bypass only our transport spy to exercise the unchanged generic service.
        from odoo.addons.ab_telegram_bot.models.telegram_service import AbTelegramBot
        with patch.object(type(bot), '_call_telegram_api', return_value={'ok': True, 'result': {'message_id': 123}}) as api:
            result = AbTelegramBot.send_message(bot, 'test-chat', 'Other module notification')
        self.assertTrue(result['sent'])
        api.assert_called_once()
