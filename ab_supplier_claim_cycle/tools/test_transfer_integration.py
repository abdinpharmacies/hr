"""Offline integration tests; require an explicitly disposable installed database.

CLAIM_TRANSFER_TEST_DB=supplier_claim_migration_test_20261116 python -m unittest \
    discover -s ab_supplier_claim_cycle/tools -p test_transfer_integration.py -v
"""
import base64
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

from claim_transfer import Bundle, digest, save_json
from transfer_target import Transfer


@unittest.skipUnless(os.environ.get('CLAIM_TRANSFER_TEST_DB', '').startswith('supplier_claim_migration_test_'), 'requires disposable database')
class TestOfflineTransfer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, '/opt/odoo19/server')
        import odoo
        from odoo import api
        odoo.tools.config.parse_config(['-c', '/opt/odoo19/config/hr19.conf', '-d', os.environ['CLAIM_TRANSFER_TEST_DB'], '--no-http'])
        cls.registry = odoo.modules.registry.Registry(os.environ['CLAIM_TRANSFER_TEST_DB'])
        cls.api = api

    def test_import_resume_permissions_and_idempotency(self):
        from odoo import Command
        from odoo.exceptions import AccessError
        with self.registry.cursor() as cr, tempfile.TemporaryDirectory() as directory:
            env = self.api.Environment(cr, 1, {'active_test': False, 'tracking_disable': True, 'mail_create_nosubscribe': True})
            user = env['res.users'].create({'name': 'Migration approver', 'login': 'migration_fixture_user',
                'company_id': env.company.id, 'company_ids': [Command.set(env.company.ids)],
                'group_ids': [Command.link(env.ref('base.group_user').id)]})
            outsider = env['res.users'].create({'name': 'Migration outsider', 'login': 'migration_fixture_outsider',
                'company_id': env.company.id, 'company_ids': [Command.set(env.company.ids)],
                'group_ids': [Command.link(env.ref('ab_supplier_claim_cycle.supplier_claim_group_participant').id)]})
            supplier = env['ab_costcenter'].create({'name': 'Migration fixture supplier', 'code': '1-MIG-TEST'})
            root = Path(directory)
            (root / 'blobs').mkdir()
            encoded = base64.b64encode(b'legacy inline evidence')
            sha = digest(encoded)
            (root / 'blobs' / sha).write_bytes(encoded)
            attachment = b'original chatter file'
            attachment_sha = digest(attachment)
            (root / 'blobs' / attachment_sha).write_bytes(attachment)
            tables = {
                'res_users': [{'id': 1, 'login': user.login, 'partner_id': 1, 'active': True, 'share': False}],
                'res_partner': [{'id': 1, 'name': user.name, 'email': None, 'ref': None}],
                'res_company': [{'id': 1, 'name': env.company.name, 'vat': env.company.vat or None}],
                'ab_costcenter': [{'id': 1, 'code': supplier.code, 'name': supplier.name, 'active': True}],
                'groups': [{'name': 'supplier_claim_group_' + role, 'uid': 1} for role in ('user', 'inventory', 'purchasing', 'supplier_accounts', 'bank_accounts')],
                'ab_supplier_claim_cycle': [],
                'ab_supplier_claim_cycle_history': [{'id': 1, 'claim_id': 2, 'event': 'decision',
                    'from_state': 'purchasing', 'to_state': 'returned_secretarial', 'department': 'purchasing',
                    'decision': 'rejected', 'reason': 'Correct invoice', 'review_round': 1, 'user_id': 1,
                    'occurred_at': '2026-01-01 10:00:00.123456', 'create_date': '2026-01-01 10:00:00.123456', 'create_uid': 1,
                    'write_date': '2026-01-01 10:00:00', 'write_uid': 1}],
                'mail_message': [{'id': 10, 'model': 'ab_supplier_claim_cycle', 'res_id': 1,
                    'body': '<p>Original <a href="/web/content/20">file</a></p>', 'message_type': 'comment',
                    'author_id': 1, 'date': '2026-01-01 10:00:00', 'parent_id': None,
                    'create_uid': 1, 'write_uid': 1, 'create_date': '2026-01-01 10:00:00', 'write_date': '2026-01-01 10:00:00'}],
                'ir_attachment': [{'id': 20, 'name': 'original.txt', 'res_model': 'ab_supplier_claim_cycle',
                    'res_id': 1, 'type': 'binary', 'mimetype': 'text/plain', 'company_id': 1,
                    '_raw': {'blob': attachment_sha, 'size': len(attachment)},
                    'create_uid': 1, 'write_uid': 1, 'create_date': '2026-01-01 10:00:00', 'write_date': '2026-01-01 10:00:00'}],
                'message_attachment_rel': [{'message_id': 10, 'attachment_id': 20}],
                'mail_tracking_value': [],
            }
            states = [('inventory', 'check'), ('returned_secretarial', 'check'), ('ready_to_close', 'cash'), ('closed', 'check'), ('draft', None)]
            for source_id, (state, payment) in enumerate(states, 1):
                row = {'id': source_id, 'supplier_id': 1, 'user_id': 1, 'claim_reference': 'MIG-%s' % source_id,
                    'state': state, 'payment_nature': payment, 'area': 'north', 'type_of_invoice': 'original',
                    'num_of_invoice': 1, 'amount_of_check': '7,156.', 'active': source_id != 5,
                    'review_round': 1, 'rejection_department': 'purchasing' if source_id == 2 else None,
                    'resume_stage': 'purchasing' if source_id == 2 else None,
                    'rejection_reason': 'Correct invoice' if source_id == 2 else None,
                    'attachment': {'blob': sha, 'size': len(encoded)} if source_id == 1 else None,
                    'create_date': '2026-01-01 09:00:00', 'write_date': '2026-01-01 10:00:00',
                    'create_uid': 1, 'write_uid': 1}
                tables['ab_supplier_claim_cycle'].append(row)
            tables['ab_supplier_claim_cycle'][0]['amount_of_check'] = '68588.855'
            save_json(root / 'data.json', {'meta': {'uuid': 'fixture', 'database': 'fixture', 'module_version': '19.0.4.2.1', 'snapshot': '2026-11-16 10:00:00'}, 'tables': tables})
            save_json(root / 'manifest.json', {'format': 1, 'data_sha256': digest((root / 'data.json').read_bytes()), 'counts': {k: len(v) for k, v in tables.items()}})
            bundle = Bundle(root)
            runner = Transfer(env, bundle, SimpleNamespace(mappings=None, replace_claims=True, amount_policy='round'))
            self.assertEqual(runner.preflight()['errors'], [])
            self.assertEqual(runner.run()['claims'], 5)
            self.assertTrue(runner.run()['unchanged'])
            claim = env['ab_supplier_claim_cycle'].browse(runner.reference('ab_supplier_claim_cycle', 1))
            self.assertEqual(claim.attachment, encoded)
            self.assertEqual(claim.claim_amount, 68588.86)
            note = env['ab_supplier_claim_cycle.history'].browse(runner.reference('migration_amount_note', 1))
            self.assertIn('68588.855', note.reason)
            with self.assertRaises(AccessError):
                claim.with_user(outsider).read(['state'])
            claim.with_user(user).write({'inventory_notes': 'Current stage evidence reviewed'})
            with self.assertRaises(AccessError):
                claim.with_user(user).write({'supplier_accounts_notes': 'Not the active stage'})
            rejected = env['ab_supplier_claim_cycle'].browse(runner.reference('ab_supplier_claim_cycle', 2))
            self.assertEqual(rejected.rejection_stage_state_id.status, 'rejected')
            rejected.with_user(user).action_resubmit()
            self.assertEqual(rejected.current_stage_names, 'Purchasing')
            ready = env['ab_supplier_claim_cycle'].browse(runner.reference('ab_supplier_claim_cycle', 3))
            ready.stage_state_ids.filtered(lambda stage: stage.status == 'pending').with_user(user).action_approve()
            self.assertEqual(ready.state, 'closed')
            # Repeat import must detect target drift rather than silently overwrite it.
            with self.assertRaises(ValueError):
                runner.run()
            cr.rollback()
