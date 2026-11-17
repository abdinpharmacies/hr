from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ConcurrencyError, LockError, UserError
from odoo.tests import tagged

from .test_workspace import TestWorkspace
from ..models.workspace import _WORKSPACE


@tagged('post_install', '-at_install', 'customer_locking')
class TestCustomerLocking(TestWorkspace):
    def setUp(self):
        super().setUp()
        self.contact = self.chatter_api.contact_save(self.session_token, {
            'name': 'Lock test customer', 'phone': '01012345678', 'address': '',
        }, branch_id=self.branch.id)
        self.stream = self.conversation()

    def refresh_all(self):
        self.assertEqual(len(self.stream.workspace_customer_inbox()['items']), 1)
        self.assertTrue(self.stream.workspace_detail()['messages'])
        self.assertTrue(self.chatter_api.notifications(self.session_token)['items'])

    def test_explicit_unlink_skips_locks_during_refresh(self):
        flag = _WORKSPACE.set(True)
        try:
            identity = self.env['ab_crm_identity'].create({
                'customer_id': self.contact['id'], 'channel_id': self.stream.channel_id.id,
                'external_key': self.stream.external_key, 'branch_id': self.branch.id,
                'company_id': self.branch.company_id.id, 'active': False,
            })
        finally:
            _WORKSPACE.reset(flag)
        original_date = self.branch.write_date
        with patch('odoo.addons.ab_crm_sales_workspace.models.customer_streams._lock_customer_records',
                   side_effect=AssertionError('An explicitly unlinked identity must not lock records')):
            self.refresh_all()
        self.assertEqual(self.branch.write_date, original_date)
        self.assertFalse(identity.active)
        self.assertFalse(self.stream.customer_id)

    def test_refresh_skips_busy_branch(self):
        with patch.object(type(self.branch), 'lock_for_update', side_effect=LockError('Synthetic contention')):
            self.refresh_all()
        self.assertFalse(self.stream.customer_id)
        self.assertFalse(self.env['ab_crm_workspace_audit'].search([
            ('conversation_id', '=', self.stream.id), ('action', '=', 'auto_link_customer')]))

    def test_refresh_rolls_back_if_account_becomes_busy(self):
        original_date = self.branch.write_date
        with patch.object(type(self.account), 'lock_for_update', side_effect=LockError('Synthetic contention')):
            self.refresh_all()
        self.assertEqual(self.branch.write_date, original_date)
        self.assertFalse(self.stream.customer_id)
        self.assertFalse(self.env['ab_crm_identity'].search([
            ('channel_id', '=', self.stream.channel_id.id), ('external_key', '=', self.stream.external_key)]))
        self.assertFalse(self.env['ab_crm_workspace_audit'].search([
            ('conversation_id', '=', self.stream.id), ('action', '=', 'auto_link_customer')]))

    def test_manual_link_is_retryable_and_access_checked_first(self):
        preview = self.stream.action_preview_customer_link(self.contact['id'])
        original_date = self.branch.write_date
        with patch.object(type(self.account), 'lock_for_update', side_effect=LockError('Synthetic contention')):
            with self.assertRaises(AccessError):
                self.stream.with_user(self.other).action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
            with self.assertRaises(AccessError):
                self.stream.with_context(ab_chatter_session_token='forged').action_confirm_customer_link(
                    self.contact['id'], preview['fingerprint'])
            with self.assertRaises(ConcurrencyError):
                self.stream.action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
        self.assertEqual(self.branch.write_date, original_date)
        self.assertFalse(self.stream.customer_id)
        self.stream.action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
        self.assertEqual(self.stream.customer_id.id, self.contact['id'])
        self.assertEqual(self.env['ab_crm_workspace_audit'].search_count([
            ('conversation_id', '=', self.stream.id), ('action', '=', 'auto_link_customer')]), 1)
        with self.assertRaises(UserError):
            self.stream.action_confirm_customer_link(self.contact['id'], 'stale')

    def test_manual_unlink_is_atomic_and_retryable(self):
        received = self.env['ab_crm_messaging_api'].with_user(self.service).receive_event(
            self.account.code, self.account.provider_account, {
                'id': 'locking-second', 'sender': '54321', 'body': 'Second conversation',
                'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
                'unsupported': False, 'source_digest': 'd' * 64,
            })
        second = self.env['ab_crm_message'].browse(received['message_id']).conversation_id.with_env(self.stream.env)
        streams = self.stream | second
        for stream in streams:
            preview = stream.action_preview_customer_link(self.contact['id'])
            stream.action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
        preview = self.stream.action_preview_customer_unlink(self.contact['id'])
        original_date = self.branch.write_date
        with patch.object(type(self.account), 'lock_for_update', side_effect=LockError('Synthetic contention')):
            with self.assertRaises(AccessError):
                self.stream.with_user(self.other).action_unlink_customer(self.contact['id'], preview['fingerprint'])
            with self.assertRaises(ConcurrencyError):
                self.stream.action_unlink_customer(self.contact['id'], preview['fingerprint'])
        self.assertEqual(self.branch.write_date, original_date)
        self.assertTrue(all(stream.customer_id.id == self.contact['id'] for stream in streams))
        self.assertFalse(self.env['ab_crm_workspace_audit'].search([
            ('conversation_id', 'in', streams.ids), ('action', '=', 'unlink_customer')]))
        self.stream.action_unlink_customer(self.contact['id'], preview['fingerprint'])
        self.assertFalse(streams.customer_id)
        self.assertEqual(self.env['ab_crm_workspace_audit'].search_count([
            ('conversation_id', 'in', streams.ids), ('action', '=', 'unlink_customer')]), 2)
