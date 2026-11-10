import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestLegacyStagingRows(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref('website.default_website')
        groups = 'base.group_user,website.group_website_designer'
        cls.owner = new_test_user(
            cls.env, login='staging_owner', groups=groups,
            company_id=cls.website.company_id.id,
        )
        cls.other = new_test_user(
            cls.env, login='staging_other', groups=groups,
            company_id=cls.website.company_id.id,
        )
        cls.portal = new_test_user(
            cls.env, login='staging_portal', groups='base.group_portal',
            company_id=cls.website.company_id.id,
        )

    def _batch(self):
        source = (
            'source_id,name,mobile_phone,active\n'
            '1,First,01012345678,t\n'
            '1,First copy,01012345678,t\n'
            '1,First,01012345678,t\n'
            '3,Shared,01112345678,t\n'
            '4,Other shared,01112345678,t\n'
            '5,Missing,,t\n'
            '6,Inactive,01512345678,f\n'
            '7,Valid,01212345678,t\n'
            '8,Invalid phone,0,t\n'
            '9,Same invalid phone,0,t\n'
        )
        batch = self.env['ab_ecommerce_legacy_batch'].with_user(self.owner).create({
            'name': 'All customer rows',
            'website_id': self.website.id,
            'source_file': base64.b64encode(source.encode()),
        })
        batch.action_preview()
        return batch

    def test_stores_every_row_without_creating_codes(self):
        batch = self._batch()
        batch.sudo().write({'staging_state': 'queued'})
        self.assertEqual(batch._store_all_rows_job(), 10)
        rows = self.env['ab_ecommerce_legacy_staging_row'].with_user(self.owner).search([
            ('batch_id', '=', batch.id),
        ])
        self.assertEqual(len(rows), 10)
        self.assertEqual(batch.staging_state, 'done')
        self.assertEqual(batch.created_count, 0)
        self.assertFalse(self.env['ab_ecommerce_legacy_customer'].search([('batch_id', '=', batch.id)]))
        self.assertIn('Missing', rows.filtered(lambda row: row.source_row == 6).source_data)
        row = rows.filtered(lambda item: item.source_row == 6)
        row.write({'review_state': 'reviewed', 'review_note': 'Follow up'})
        self.assertEqual(row.reviewed_by, self.owner)
        with self.assertRaises(AccessError):
            row.write({'source_data': '{}'})
        with self.assertRaises(AccessError):
            rows.create({'batch_id': batch.id, 'source_row': 7})
        with self.assertRaises(UserError):
            batch.action_reset_preview()

    def test_duplicate_scan_preserves_rows_and_flags_conflicts(self):
        batch = self._batch()
        batch.sudo().write({'staging_state': 'queued'})
        batch._store_all_rows_job()
        batch.sudo().write({'duplicate_scan_state': 'queued'})
        self.assertEqual(batch._mark_duplicate_rows_job(), {'duplicates': 1, 'conflicts': 2})
        rows = self.env['ab_ecommerce_legacy_staging_row'].search([('batch_id', '=', batch.id)])
        states = {row.source_row: row.duplicate_state for row in rows}
        self.assertEqual(states[2], 'unique')
        self.assertEqual(states[3], 'exact_duplicate')
        self.assertEqual(states[4], 'conflict')
        self.assertEqual(states[5], 'conflict')
        self.assertEqual(len(rows), 10)
        self.assertEqual(batch.review_row_count, 9)
        self.assertEqual(batch.review_duplicate_count, 1)
        self.assertTrue(batch.action_process_next()['done'])
        self.assertEqual(batch.created_count, 1)
        self.assertEqual(len(rows), 10)

    def test_other_owner_cannot_read_or_update_staging(self):
        batch = self._batch()
        batch.sudo().write({'staging_state': 'queued'})
        batch._store_all_rows_job()
        model = self.env['ab_ecommerce_legacy_staging_row'].with_user(self.other)
        self.assertFalse(model.search([('batch_id', '=', batch.id)]))
        with self.assertRaises(AccessError):
            batch.with_user(self.other).action_review_staging_rows()
        row = self.env['ab_ecommerce_legacy_staging_row'].search([('batch_id', '=', batch.id)], limit=1)
        with self.assertRaises(AccessError):
            row.with_user(self.other).write({'review_note': 'Wrong owner'})
        with self.assertRaises(AccessError):
            row.with_user(self.portal).read(['source_data'])

    def test_completed_imports_keep_one_review_master(self):
        first = self._batch()
        first.sudo().write({'state': 'done'})
        second = self._batch()
        self.assertEqual(second._review_master(), first)
        second.sudo().write({'review_master_batch_id': first.id, 'state': 'done'})
        third = self._batch()
        self.assertEqual(third._review_master(), first)
