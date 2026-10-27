from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.addons.queue_job.job import Job
from odoo.addons.queue_job.tests.common import trap_jobs


@tagged('post_install', '-at_install')
class TestCycleTelegramNotifications(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        costcenter_class = type(cls.env['ab_costcenter'])
        if hasattr(costcenter_class, '_get_active_replication_override_policy'):
            cls.enterClassContext(patch.object(
                costcenter_class, '_get_active_replication_override_policy', return_value=None))
        cls.claim_model = cls.env['ab_supplier_claim_cycle']
        cls.bot_class = type(cls.env['ab_telegram_bot'])
        cls.roles = ('user', 'inventory', 'purchasing', 'supplier_accounts', 'bank_accounts')
        cls.users = {}
        cls.chats = {}
        cls.centers = {}
        for number, role in enumerate(cls.roles, 1):
            user = new_test_user(
                cls.env(context=dict(cls.env.context, no_reset_password=True)),
                login='cycle_telegram_test_' + role,
                groups='ab_supplier_claim_cycle.supplier_claim_group_' + role)
            center = cls.env['ab_costcenter'].create({
                'name': 'Telegram Test ' + role, 'code': f'9-TG-{number}'})
            cls.env['ab_hr_employee'].create({
                'name': 'Telegram Test ' + role, 'user_id': user.id, 'costcenter_id': center.id})
            chat_id = str(-99900000 - number)
            cls.env['ab_partner_bot'].create({'costcenter_id': center.id, 'chat_id': chat_id})
            cls.users[role], cls.chats[role], cls.centers[role] = user, chat_id, center
        cls.supplier = cls.env['ab_costcenter'].create({
            'name': 'Telegram Supplier <Test>', 'code': '1-TG-TEST'})
        cls.env['ir.config_parameter'].sudo().set_param(
            'supplier_claim_cycle.telegram_notifications_enabled', 'True')

    def claim(self, cash=False):
        return self.claim_model.with_user(self.users['user']).create({
            'supplier_id': self.supplier.id, 'num_of_invoice': 1, 'area': 'north',
            'amount_of_check': '1250', 'type_of_invoice': 'original',
            'payment_nature': 'cash' if cash else 'bank_transfer',
            'tax_classification': 'tax_payment', 'section': 'medical',
        })

    def transition(self, claim, callback, role):
        with patch.object(self.bot_class, 'send_message') as send, trap_jobs() as trap:
            callback()
            send.assert_not_called()
            chat_ids = claim._cycle_telegram_chat_ids()
            trap.assert_jobs_count(len(chat_ids))
            self.assertIn(self.chats[role], chat_ids)
            trap.assert_enqueued_job(
                claim.sudo()._deliver_cycle_telegram_notification,
                args=(self.chats[role], claim._cycle_telegram_message()),
                properties={'channel': 'root.supplier_claim_cycle_telegram', 'max_retries': 0,
                            'description': f'Supplier claim {claim.id}: {claim.state}'})
            return trap

    def test_non_cash_route_and_closure(self):
        claim = self.claim()
        self.transition(claim, claim.action_submit, 'inventory')
        for department, target in (
            ('inventory', 'purchasing'), ('purchasing', 'supplier_accounts'),
            ('supplier_accounts', 'bank_accounts'), ('bank_accounts', 'user'),
        ):
            self.transition(claim, lambda: claim.with_user(self.users[department]).action_decide(
                department, 'approved'), target)
        self.transition(claim, claim.action_close, 'user')
        self.assertEqual(claim._cycle_telegram_chat_ids(), [self.chats['user']])

    def test_cash_route(self):
        claim = self.claim(cash=True)
        self.transition(claim, claim.action_submit, 'supplier_accounts')
        self.transition(claim, lambda: claim.with_user(self.users['supplier_accounts']).action_decide(
            'supplier_accounts', 'approved'), 'user')
        self.assertEqual(claim.state, 'ready_to_close')
        self.transition(claim, claim.action_close, 'user')

    def test_rejection_resubmission_and_deferral(self):
        claim = self.claim()
        self.transition(claim, claim.action_submit, 'inventory')
        for department in ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts'):
            with trap_jobs() as trap:
                claim.with_user(self.users[department]).action_decide(
                    department, 'deferred', reason='Waiting', followup_date=fields.Date.today())
                trap.assert_jobs_count(0)
            self.transition(claim, lambda: claim.with_user(self.users[department]).action_decide(
                department, 'rejected', reason='<Correction needed>'), 'user')
            self.assertIn('&lt;Correction needed&gt;', claim._cycle_telegram_message())
            self.transition(claim, claim.action_submit, department)
            with trap_jobs():
                claim.with_user(self.users[department]).action_decide(department, 'approved')

    def test_delivery_uses_bot_and_preserves_event_snapshot(self):
        claim = self.claim(cash=True)
        trap = self.transition(claim, claim.action_submit, 'supplier_accounts')
        with trap_jobs():
            claim.with_user(self.users['supplier_accounts']).action_decide('supplier_accounts', 'approved')
        with patch.object(self.bot_class, 'send_message', return_value={'sent': True}) as send:
            expected_count = len(trap.enqueued_jobs)
            trap.perform_enqueued_jobs()
            self.assertEqual(send.call_count, expected_count)
            for call in send.call_args_list:
                self.assertIn('Current stage: Supplier Accounts', call.args[1])
                self.assertIn('Supplier: Telegram Supplier &lt;Test&gt;', call.args[1])
                self.assertIn('Amount: 1250', call.args[1])
                self.assertIn(f'/odoo/ab_supplier_claim_cycle/{claim.id}', call.args[1])
                self.assertTrue(call.kwargs['disable_web_page_preview'])

    def test_delivery_failure_is_retryable_and_claim_remains_submitted(self):
        claim = self.claim(cash=True)
        self.transition(claim, claim.action_submit, 'supplier_accounts')
        for failure in ({'sent': False}, False, TimeoutError('timeout')):
            kwargs = {'side_effect': failure} if isinstance(failure, Exception) else {'return_value': failure}
            with patch.object(self.bot_class, 'send_message', **kwargs):
                with self.assertRaises(RetryableJobError), self.env.cr.savepoint():
                    claim.sudo()._deliver_cycle_telegram_notification(self.chats['supplier_accounts'], 'Message')
            self.assertEqual(claim.state, 'supplier_accounts')
        job = Job(claim.sudo()._deliver_cycle_telegram_notification,
                  args=(self.chats['supplier_accounts'], 'Message'), max_retries=0)
        with patch.object(self.bot_class, 'send_message', return_value={'sent': False}):
            with self.assertRaises(RetryableJobError):
                job.perform()
        self.assertEqual(job.retry, 1)
        self.assertEqual(job._get_retry_seconds(), 60)
        with patch.object(self.bot_class, 'send_message', return_value={'sent': True}) as send:
            job.perform()
            send.assert_called_once()

    def test_transaction_rollback_removes_job(self):
        claim = self.claim(cash=True)
        job_model = self.env['queue.job'].sudo()
        domain = fields.Domain('method_name', '=', '_deliver_cycle_telegram_notification')
        before = job_model.search_count(domain)
        with self.assertRaisesRegex(ValueError, 'Rollback'), self.env.cr.savepoint():
            claim.action_submit()
            self.assertGreater(job_model.search_count(domain), before)
            raise ValueError('Rollback')
        self.assertEqual(job_model.search_count(domain), before)
        self.assertEqual(claim.state, 'draft')

    def test_missing_connections_and_shared_chat(self):
        shared_user = new_test_user(
            self.env(context=dict(self.env.context, no_reset_password=True)),
            login='cycle_telegram_shared',
            groups='ab_supplier_claim_cycle.supplier_claim_group_inventory')
        self.env['ab_hr_employee'].create({
            'name': 'Shared chat', 'user_id': shared_user.id,
            'costcenter_id': self.centers['inventory'].id})
        new_test_user(self.env(context=dict(self.env.context, no_reset_password=True)),
                      login='cycle_telegram_unconnected',
                      groups='ab_supplier_claim_cycle.supplier_claim_group_inventory')
        claim = self.claim()
        trap = self.transition(claim, claim.action_submit, 'inventory')
        chat_ids = [job.args[0] for job in trap.enqueued_jobs]
        self.assertEqual(chat_ids.count(self.chats['inventory']), 1)
        self.env['ab_partner_bot'].search(
            fields.Domain('chat_id', '=', self.chats['inventory'])).write({'active': False})
        self.assertNotIn(self.chats['inventory'], claim._cycle_telegram_chat_ids())

    def test_disabled_parameter_and_access_control(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'supplier_claim_cycle.telegram_notifications_enabled', 'False')
        claim = self.claim()
        with trap_jobs() as trap:
            claim.action_submit()
            trap.assert_jobs_count(0)
        with patch.object(self.bot_class, 'send_message') as send:
            claim.sudo()._deliver_cycle_telegram_notification(self.chats['inventory'], 'Message')
            send.assert_not_called()
        other = self.claim()
        with trap_jobs() as trap, self.assertRaises(AccessError), self.env.cr.savepoint():
            other.with_user(self.users['bank_accounts']).action_submit()
        trap.assert_jobs_count(0)

    def test_multi_record_submission(self):
        claims = self.claim() | self.claim(cash=True)
        with trap_jobs() as trap, patch.object(self.bot_class, 'send_message') as send:
            claims.action_submit()
            send.assert_not_called()
            expected = sum(len(claim._cycle_telegram_chat_ids()) for claim in claims)
            trap.assert_jobs_count(expected)
        self.assertEqual(claims.mapped('state'), ['inventory', 'supplier_accounts'])
