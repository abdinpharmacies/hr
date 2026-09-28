import importlib.util
from pathlib import Path

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


def load_migration(stage):
    path = Path(__file__).resolve().parents[1] / 'migrations' / '19.0.2.1.0' / f'{stage}-migrate.py'
    spec = importlib.util.spec_from_file_location(f'supplier_claim_{stage}_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged('post_install', '-at_install')
class TestLegacySupplierMigration(TransactionCase):
    def test_pre_migration_preserves_raw_reference_and_is_idempotent(self):
        self.cr.execute('CREATE TEMP TABLE ab_costcenter (id integer PRIMARY KEY) ON COMMIT DROP')
        self.cr.execute('''CREATE TEMP TABLE ab_supplier_claim_cycle (
            id integer PRIMARY KEY, supplier_id integer NOT NULL REFERENCES ab_costcenter(id),
            status varchar NOT NULL) ON COMMIT DROP''')
        self.cr.execute('INSERT INTO ab_costcenter VALUES (5)')
        self.cr.execute("INSERT INTO ab_supplier_claim_cycle VALUES (3, 5, 'sign_check')")
        migrate = load_migration('pre').migrate
        migrate(self.cr, '19.0.1.0.0')
        self.cr.execute('SELECT legacy_supplier_reference_id,status,legacy_claim_recovered FROM ab_supplier_claim_cycle')
        self.assertEqual(self.cr.fetchall(), [(5, 'sign_check', False)])
        migrate(self.cr, '19.0.1.0.0')
        # Historical columns are optional on future claims.
        self.cr.execute('INSERT INTO ab_supplier_claim_cycle (id) VALUES (4)')


@tagged('post_install', '-at_install')
class TestLegacyClaimAudit(TransactionCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.env['ab_supplier'].create({'name': 'Original supplier', 'code': 'SCC-ORIGINAL'})
        self.claim = self.env['ab_supplier_claim_cycle'].create({
            'supplier_id': self.supplier.id, 'num_of_invoice': 2, 'area': 'north',
            'amount_of_check': '123', 'type_of_invoice': 'original',
        })
        # Explicit fixtures for the old release, which logged creation/submission.
        self.claim._log('created')
        self.env.flush_all()
        self.cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS legacy_supplier_reference_id integer')
        self.cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS legacy_supplier_reference_model varchar')
        self.cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS legacy_claim_recovered boolean DEFAULT false')
        self.cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS status varchar')
        self.migrate = load_migration('post')._migrate_legacy_inventory_claims

    def mark_legacy(self, reference, status='inventory'):
        self.env.flush_all()
        self.cr.execute('UPDATE ab_supplier_claim_cycle SET legacy_supplier_reference_id=%s,status=%s WHERE id=%s',
                        [reference, status, self.claim.id])

    def test_native_history_restores_supplier_and_decisions_despite_id_collision(self):
        self.claim.action_submit()
        self.claim._log('submitted', 'draft')
        self.claim.action_decide('inventory', 'approved')
        self.claim.action_decide('purchasing', 'approved')
        self.env['ab_supplier'].create({'name': 'Other supplier', 'code': 'SCC-OTHER'})
        self.mark_legacy(self.supplier.id)
        self.claim._workflow_write({'state': 'draft', 'inventory_decision': 'not_required', 'purchasing_decision': 'not_required'})
        self.migrate(self.env)
        self.assertEqual(self.claim.supplier_id, self.supplier)
        self.assertEqual(self.claim.state, 'supplier_accounts')
        self.assertEqual(self.claim.inventory_decision, 'approved')
        self.assertEqual(self.claim.purchasing_decision, 'approved')
        self.assertEqual(self.claim.amount_of_check, '123')
        count = len(self.claim.history_ids)
        self.migrate(self.env)
        self.assertEqual(len(self.claim.history_ids), count)

    def test_prior_migration_event_does_not_skip_recovery(self):
        self.claim.action_submit()
        self.claim._log('submitted', 'draft')
        self.claim._log('migrated', reason='Earlier workflow migration')
        self.mark_legacy(self.supplier.id)
        self.claim._workflow_write({'state': 'draft'})
        self.migrate(self.env)
        self.assertEqual(self.claim.state, 'inventory')
        self.assertEqual(len(self.claim.history_ids.filtered(lambda h: h.event == 'migrated')), 2)

    def test_recovered_cash_closed_claim_is_not_reopened(self):
        self.claim.write({'payment_nature': 'cash'})
        self.claim.action_submit()
        self.claim._log('submitted', 'draft')
        self.claim.action_decide('supplier_accounts', 'approved')
        self.claim.action_close()
        self.mark_legacy(self.supplier.id)
        self.claim._workflow_write({'state': 'draft'})
        self.migrate(self.env)
        self.assertEqual(self.claim.state, 'closed')
        self.assertEqual(self.claim.payment_nature, 'cash')
        self.assertEqual(self.claim.supplier_accounts_decision, 'approved')

    def test_genuine_legacy_claim_creates_source_supplier_and_holds_progress(self):
        source = self.env['ab_costcenter'].with_context(install_mode=True).create({'name': 'Legacy source supplier', 'code': 'SCC-SOURCE'})
        # A legacy claim has no new-workflow creation event. Make an SQL fixture
        # rather than deleting immutable audit records from the ORM-created claim.
        self.env.flush_all()
        self.cr.execute("""INSERT INTO ab_supplier_claim_cycle
            (supplier_id,num_of_invoice,user_id,area,amount_of_check,type_of_invoice,state,active,
             legacy_supplier_reference_id,status,create_date)
            VALUES (%s,2,%s,'north','123','original','draft',true,%s,'sign_check',now()) RETURNING id
        """, [self.supplier.id,self.env.uid,source.id])
        legacy = self.env['ab_supplier_claim_cycle'].browse(self.cr.fetchone()[0])
        self.migrate(self.env)
        self.assertEqual(legacy.supplier_id.name, source.name)
        self.assertEqual(legacy.supplier_id.code, source.code)
        self.assertEqual(legacy.supplier_id.costcenter_id, source)
        self.assertEqual(legacy.state, 'legacy_review')
        self.assertEqual(legacy.legacy_status, 'sign_check')
        self.assertNotEqual(legacy.inventory_decision, 'approved')
        with self.assertRaises(UserError):
            legacy.action_close()
        user = new_test_user(self.env, login='scc_legacy_regular', groups='ab_supplier_claim_cycle.supplier_claim_group_user')
        with self.assertRaises(AccessError):
            legacy.with_user(user).action_restart_legacy_review()
        legacy.action_restart_legacy_review()
        self.assertEqual(legacy.state, 'draft')
        self.assertEqual(legacy.legacy_status, 'sign_check')
        legacy.action_submit()
        self.assertEqual(legacy.state, 'inventory')

    def test_missing_original_supplier_never_falls_back_to_costcenter(self):
        self.mark_legacy(2147483647)
        with self.assertRaisesRegex(ValidationError, 'missing original supplier'):
            self.migrate(self.env)
