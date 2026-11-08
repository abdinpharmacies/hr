import base64
import csv
import io
import json
import gc
import logging
import resource
import tempfile
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import ChromeBrowser, HttpCase, TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestLegacyActivation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref('website.default_website')
        cls.designer = new_test_user(cls.env, login='legacy_designer', groups='base.group_user,website.group_website_designer', company_id=cls.website.company_id.id)
        cls.other_designer = new_test_user(cls.env, login='legacy_other_designer', groups='base.group_user,website.group_website_designer', company_id=cls.website.company_id.id)
        cls.portal = new_test_user(cls.env, login='legacy_customer@example.test', groups='base.group_portal', company_id=cls.website.company_id.id)
        cls.other_portal = new_test_user(cls.env, login='legacy_other@example.test', groups='base.group_portal', company_id=cls.website.company_id.id)
        cls.Registry = cls.env['ab_ecommerce_legacy_customer']
        cls.Batch = cls.env['ab_ecommerce_legacy_batch']

    def _batch(self, rows=None, actor=None):
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['source_id', 'name', 'mobile_phone', 'active'])
        writer.writerows(rows or [['001', 'Legacy customer', '01012345678', 't']])
        return self.Batch.with_user(actor or self.designer).create({
            'name': 'Activation test', 'website_id': self.website.id,
            'source_file': base64.b64encode(output.getvalue().encode()),
            'expires_at': fields.Datetime.now() + timedelta(days=30),
        })

    def _generate(self, batch):
        batch.action_preview()
        while not batch.action_process_next()['done']:
            pass
        rows = list(csv.DictReader(io.StringIO(batch._export_csv())))
        return rows

    def _claim(self, row, actor=None, code=None, website=None):
        actor = actor or self.portal
        return self.Registry.with_user(actor)._claim(actor, website or self.website, row['mobile_phone'], code or row['activation_code'], '192.0.2.1')

    def test_generation_export_hashing_and_single_use_claim(self):
        batch = self._batch()
        row = self._generate(batch)[0]
        self.assertEqual(batch.created_count, 1)
        self.assertRegex(row['activation_code'], r'^\d{12}$')
        record = self.Registry.search([('batch_id', '=', batch.id)])
        self.assertNotEqual(record.code_hash, row['activation_code'])
        chunk = batch.sudo().chunk_ids
        self.assertFalse(chunk.payload)
        self.assertNotIn(row['activation_code'], chunk.encrypted_export)
        self.assertEqual(batch.export_count, 1)
        self.assertEqual(self.env['ab_ecommerce_legacy_export'].search([('batch_id', '=', batch.id)]).user_id, self.designer)
        points_before = self.env['loyalty.card'].search_count([])
        self.assertTrue(self._claim(row))
        self.assertEqual(record.partner_id, self.portal.partner_id)
        self.assertEqual(record.claimed_user_id, self.portal)
        self.assertFalse(record.code_hash)
        self.assertFalse(self._claim(row, self.other_portal))
        self.assertEqual(self.env['loyalty.card'].search_count([]), points_before)
        self.assertTrue(self.Registry.with_user(self.portal)._portal_status(self.portal, self.website)['linked'])

    def test_repeat_import_and_processing_are_idempotent(self):
        batch = self._batch()
        row = self._generate(batch)[0]
        self.assertTrue(batch.action_process_next()['done'])
        self.assertEqual(batch.created_count, 1)
        second = self._batch()
        self.assertEqual(self._generate(second), [])
        self.assertEqual(second.skipped_count, 1)
        self.assertTrue(self._claim(row))

    def test_duplicates_invalid_and_inactive_rows_excluded(self):
        batch = self._batch([
            ['1', 'A', '01012345678', 't'], ['2', 'B', '+201012345678', 't'],
            ['3', 'C', '01112345678', 't'], ['3', 'D', '01212345678', 't'],
            ['4', 'E', 'garbage', 't'], ['5', 'F', '01512345678', 'f'],
            ['6', 'G', '01012345679', 't'],
        ])
        rows = self._generate(batch)
        self.assertEqual(len(rows), 1)
        self.assertEqual(batch.rejected_count, 5)
        self.assertEqual(batch.inactive_count, 1)

    def test_import_normalizes_phone_formats(self):
        batch = self._batch([
            ['1', 'Local digits', '٠١٠١٢٣٤٥٦٧٨', 't'],
            ['2', 'International prefix', '00201112345678', 't'],
            ['3', 'Country code', '201212345678', 't'],
            ['4', 'Invalid prefix', '+0201512345678', 't'],
        ])
        rows = self._generate(batch)
        self.assertEqual({row['mobile_phone'] for row in rows}, {'+201012345678', '+201112345678', '+201212345678'})
        self.assertEqual(batch.rejected_count, 1)

    def test_malformed_csv_stops_before_writing_customers(self):
        batch = self._batch()
        batch.source_file = base64.b64encode(b'source_id,mobile_phone\n1,01012345678,extra\n')
        batch.action_preview()
        self.assertEqual(batch.state, 'review')
        self.assertEqual(batch.issue_ids.issue_code, 'column_count')
        self.assertFalse(self.Registry.search_count([('batch_id', '=', batch.id)]))
        self.assertFalse(batch.sudo().chunk_ids)

    def test_upload_uses_private_attachment(self):
        batch = self._batch()
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', batch._name), ('res_field', '=', 'source_file'), ('res_id', '=', batch.id),
        ])
        self.assertEqual(len(attachment), 1)
        self.assertTrue(attachment.store_fname)
        self.assertFalse(attachment.db_datas)
        self.assertFalse(attachment.public)
        for actor in (self.portal, self.other_designer):
            with self.assertRaises(AccessError):
                attachment.with_user(actor).read(['raw'])
            with self.assertRaises(AccessError):
                with batch.with_user(actor)._source_stream():
                    pass
        batch.action_preview()
        self.assertTrue(attachment.exists())

    def test_preview_excludes_duplicates_across_chunks(self):
        rows = [[str(i), 'Synthetic customer', f'010{i:08d}', 't'] for i in range(1, 1102)]
        rows.append(['duplicate', 'Shared phone', '01000000001', 't'])
        batch = self._batch(rows)
        batch.action_preview()
        self.assertEqual(batch.accepted_count, 1100)
        self.assertEqual(batch.rejected_count, 2)
        self.assertEqual(len(batch.sudo().chunk_ids), 2)
        staged = [row for chunk in batch.sudo().chunk_ids for row in json.loads(chunk.payload)]
        self.assertNotIn('+201000000001', {row['phone'] for row in staged})

    def test_large_upload_and_streaming_preview(self):
        with tempfile.TemporaryFile() as source:
            source.write(b'source_id,name,mobile_phone,active,description\n')
            padding = 'x' * 158
            for index in range(450000):
                source.write(f'{index},Synthetic customer,010{index:08d},t,{padding}\n'.encode())
            size = source.tell()
            self.assertGreater(size, 85 * 1024 * 1024)
            self.assertLess(size, 90 * 1024 * 1024)
            source.seek(0)
            payload = base64.b64encode(source.read()).decode('ascii')
        saved = self.Batch.with_user(self.designer).with_context(bin_size=True).web_save({
            'name': 'Large synthetic upload', 'website_id': self.website.id, 'source_file': payload,
        }, specification={'id': {}, 'name': {}, 'source_file': {}})
        batch = self.Batch.with_user(self.designer).browse(saved[0]['id'])
        del payload
        self.env.invalidate_all()
        gc.collect()
        batch.action_preview()
        self.assertEqual(batch.accepted_count, 449999)
        self.assertEqual(batch.rejected_count, 1)
        self.assertEqual(len(batch.sudo().chunk_ids), 450)
        self.assertTrue(batch.with_context(bin_size=True).source_file)
        with batch.with_context(lang='en_US')._review_csv_file() as output:
            text = io.TextIOWrapper(output, encoding='utf-8-sig', newline='')
            reader = csv.DictReader(text)
            first = next(reader)
            self.assertEqual(first['source_id'], '1')
            self.assertEqual(first['Review: status'], 'Eligible')
            self.assertEqual(1 + sum(1 for row in reader), 450001)
            text.detach()
        logging.getLogger(__name__).info('Large CSV upload, preview and report passed: bytes=%s rows=450000 peak_rss_kib=%s', size, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

    def test_reports_all_columns_and_imports_only_valid_records(self):
        batch = self._batch([
            ['bad ref!', '', 'not a phone', 'unknown'],
            ['2', 'Valid', '01012345678', 'true'],
        ])
        batch.action_preview()
        self.assertEqual(batch.state, 'ready')
        self.assertEqual(batch.accepted_count, 1)
        self.assertEqual(batch.rejected_count, 1)
        issues = batch.issue_ids.filtered(lambda line: line.source_row == 1)
        self.assertEqual(set(issues.mapped('column_name')), {'source_id', 'name', 'mobile_phone', 'active'})
        self.assertTrue(all(line.import_status == 'excluded' for line in issues))
        self.assertEqual(issues.filtered(lambda line: line.column_name == 'mobile_phone').original_value, 'not a phone')
        batch.action_process_next()
        self.assertEqual(batch.created_count, 1)

    def test_broken_quotes_report_name_column_without_swallowing_later_records(self):
        batch = self._batch()
        batch.source_file = base64.b64encode(b'source_id,name,mobile_phone\n1,"Broken"",01012345678\n2,Valid,01112345678\n3,Other,invalid\n')
        batch.action_preview()
        self.assertEqual(batch.state, 'ready')
        self.assertEqual(batch.total_rows, 3)
        self.assertFalse(batch.has_blocking_issues)
        quote = batch.issue_ids.filtered(lambda line: line.issue_code == 'quoting')
        self.assertEqual((quote.source_row, quote.line_start, quote.column_name, quote.column_number), (1, 2, 'name', 2))
        self.assertTrue(batch.issue_ids.filtered(lambda line: line.source_row == 3 and line.issue_code == 'invalid_phone'))
        self.assertEqual(len(batch.sudo().chunk_ids), 1)
        batch.action_process_next()
        self.assertEqual(batch.created_count, 1)

    def test_semicolon_headers_and_safe_phone_corrections(self):
        batch = self._batch()
        batch.source_file = base64.b64encode(b' SOURCE_ID ; Name ; MOBILE_PHONE ;active\n 1 ;Customer;1012345678.0;yes\n')
        batch.action_preview()
        self.assertEqual(batch.accepted_count, 1)
        self.assertEqual(batch.corrected_count, 1)
        codes = set(batch.issue_ids.mapped('issue_code'))
        self.assertTrue({'delimiter_detected', 'header_normalized', 'phone_normalized', 'trimmed'} <= codes)
        batch.action_process_next()
        customer = self.Registry.search([('batch_id', '=', batch.id)])
        self.assertEqual(customer.phone, '+201012345678')
        self.assertEqual(set(batch.issue_ids.filtered('source_row').mapped('import_status')), {'imported'})

    def test_valid_multiline_quotes_and_embedded_delimiters(self):
        batch = self._batch([['1', 'First line\nSecond, "quoted" line', '01012345678', 't']])
        batch.action_preview()
        self.assertEqual(batch.state, 'ready')
        self.assertFalse(batch.has_blocking_issues)
        self.assertEqual(batch.accepted_count, 1)

    def test_encoding_report_and_explicit_windows_arabic(self):
        batch = self._batch()
        text = 'source_id,name,mobile_phone\n1,عميل,01012345678\n'
        batch.source_file = base64.b64encode(text.encode('cp1256'))
        batch.action_preview()
        self.assertEqual(batch.state, 'review')
        self.assertEqual(batch.issue_ids.filtered(lambda row: row.issue_code == 'encoding').column_name, 'name')
        batch.action_reset_preview()
        batch.source_encoding = 'cp1256'
        batch.action_preview()
        self.assertEqual(batch.accepted_count, 1)
        self.assertFalse(batch.issue_ids)

    def test_utf16_bom_is_detected(self):
        batch = self._batch()
        batch.source_file = base64.b64encode('source_id,name,mobile_phone\n1,عميل,01012345678\n'.encode('utf-16'))
        batch.action_preview()
        self.assertEqual(batch.accepted_count, 1)

    def test_duplicate_headers_are_blocking_and_empty_files_are_reported(self):
        batch = self._batch()
        batch.source_file = base64.b64encode(b'source_id,mobile_phone,mobile_phone\n1,01012345678,01112345678\n')
        batch.action_preview()
        self.assertTrue(batch.has_blocking_issues)
        self.assertTrue(batch.issue_ids.filtered(lambda row: row.issue_code == 'duplicate_header'))
        self.assertFalse(batch.sudo().chunk_ids)
        batch.action_reset_preview()
        batch.source_file = base64.b64encode(b'\xef\xbb\xbf')
        batch.action_preview()
        self.assertEqual(batch.state, 'review')
        self.assertTrue(batch.issue_ids.filtered(lambda row: row.issue_code == 'empty_file'))

    def test_scientific_notation_controls_and_oversized_fields_reported(self):
        batch = self._batch([['1', 'Name\x00', '1.01234E+09', 't'], ['2', 'x' * 4097, '', 't']])
        batch.action_preview()
        self.assertEqual(batch.rejected_count, 2)
        self.assertTrue({'control_character', 'scientific_phone', 'field_limit', 'missing_phone'} <= set(batch.issue_ids.mapped('issue_code')))
        self.assertFalse(self.Registry.search([('batch_id', '=', batch.id)]))

    def test_column_count_errors_exclude_only_affected_records(self):
        batch = self._batch()
        batch.source_file = base64.b64encode(b'source_id,name,mobile_phone\n1,Wrong,01012345678,EXTRA\n2,Valid,01112345678,,\n3,Missing\n')
        batch.action_preview()
        self.assertEqual((batch.accepted_count, batch.rejected_count), (1, 2))
        self.assertFalse(batch.has_blocking_issues)
        self.assertEqual(len(batch.issue_ids.filtered(lambda row: row.issue_code == 'column_count')), 2)
        self.assertTrue(batch.issue_ids.filtered(lambda row: row.issue_code == 'trailing_empty_columns'))

    def test_review_access_and_reset_are_owner_scoped(self):
        batch = self._batch([['1', 'Invalid', 'bad', 't']])
        batch.action_preview()
        issues = batch.issue_ids
        for user in (self.other_designer, self.portal, self.env.ref('base.public_user')):
            with self.assertRaises(AccessError):
                issues.with_user(user).read(['original_value'])
            with self.assertRaises(AccessError):
                batch.with_user(user).action_review_issues()
            with self.assertRaises(AccessError):
                batch.with_user(user).action_reset_preview()
        with self.assertRaises(AccessError):
            issues.write({'import_status': 'ready'})
        batch.action_reset_preview()
        self.assertEqual(batch.state, 'draft')
        self.assertFalse(issues.exists())
        self.assertTrue(batch.with_context(bin_size=True).source_file)

    def test_existing_customer_issues_are_visible_before_generation(self):
        first = self._batch()
        self._generate(first)
        second = self._batch()
        second.action_preview()
        self.assertTrue({'existing_reference', 'existing_phone'} <= set(second.issue_ids.mapped('issue_code')))
        count = second.issue_count
        second.action_process_next()
        self.assertEqual(second.skipped_count, 1)
        self.assertEqual(second.issue_count, count)

    def test_review_csv_preserves_originals_sorts_eligible_and_explains_corrections(self):
        batch = self._batch([
            ['1', 'Invalid', 'bad', 't'],
            ['2', ' Customer ', '1012345678.0', 't'],
            ['3', 'Clean', '01112345678', 't'],
            ['4', 'Inactive', '01212345678', 'f'],
        ])
        batch.action_preview()
        self.assertEqual(batch.eligible_count, 2)
        self.assertEqual(batch.eligible_percentage, 50)
        with batch.with_context(lang='en_US')._review_csv_file() as output:
            rows = list(csv.DictReader(io.StringIO(output.read().decode('utf-8-sig'))))
        self.assertEqual([row['source_id'] for row in rows[:2]], ['2', '3'])
        self.assertEqual(rows[0]['name'], ' Customer ')
        self.assertEqual(rows[0]['mobile_phone'], '1012345678.0')
        self.assertEqual(rows[0]['Review: corrected mobile'], '+201012345678')
        self.assertEqual(rows[0]['Review: corrected name'], 'Customer')
        self.assertIn('phone_normalized', rows[0]['Review: issue codes'])
        self.assertEqual(rows[0]['Review: status'], 'Eligible after correction')
        self.assertEqual(rows[-1]['Review: status'], 'Inactive')
        self.assertFalse(self.Registry.search_count([('batch_id', '=', batch.id)]))
        for actor in (self.other_designer, self.portal, self.env.ref('base.public_user')):
            with self.assertRaises(AccessError):
                batch.with_user(actor).action_download_review()
            with self.assertRaises(AccessError):
                batch.with_user(actor)._review_csv_file()

    def test_review_damaged_rows_reserve_shared_phones_and_keep_raw_input(self):
        batch = self._batch()
        raw = '1,"Broken"name,01012345678,t\n'
        batch.source_file = base64.b64encode(('source_id,name,mobile_phone,active\n' + raw + '2,Shared,01012345678,t\n3,Good,01112345678,t\n').encode())
        batch.action_preview()
        self.assertEqual((batch.eligible_count, batch.rejected_count), (1, 2))
        with batch.with_context(lang='en_US')._review_csv_file() as output:
            rows = list(csv.DictReader(io.StringIO(output.read().decode('utf-8-sig'))))
        self.assertEqual(rows[0]['source_id'], '3')
        damaged = next(row for row in rows if row['Review: original malformed record'])
        self.assertEqual(damaged['Review: original malformed record'], raw)
        batch.action_process_next()
        self.assertEqual(self.Registry.search([('batch_id', '=', batch.id)]).phone, '+201112345678')

    def test_review_existing_counts_and_old_previews_require_recheck(self):
        first = self._batch()
        self._generate(first)
        batch = self._batch()
        batch.action_preview()
        self.assertEqual((batch.existing_count, batch.eligible_count, batch.eligible_percentage), (1, 0, 0))
        batch.sudo().review_version = 0
        for action in (batch.action_download_review, batch.action_generate_codes, batch.action_process_next):
            with self.assertRaises(UserError):
                action()
        batch.action_recheck()
        self.assertEqual(batch.review_version, 2)
        self.assertEqual(batch.eligible_count, 0)

    def test_review_zero_denominator_and_formula_escaping(self):
        batch = self._batch([['1', '=HYPERLINK("bad")', '01012345678', 't']])
        self.assertEqual(batch.eligible_percentage, 0)
        batch.action_preview()
        with batch.with_context(lang='en_US')._review_csv_file() as output:
            rows = list(csv.DictReader(io.StringIO(output.read().decode('utf-8-sig'))))
        self.assertTrue(rows[0]['name'].startswith("'="))
        self.assertEqual(batch.eligible_percentage, 100)

    def test_ambiguous_continuations_and_incomplete_scans_never_become_eligible(self):
        batch = self._batch()
        batch.source_file = base64.b64encode(b'source_id,name,mobile_phone,active\n1,"Broken"name,01012345678,t\nnot a reference,Continuation,01212345678,t\n2,Safe,01112345678,t\n')
        batch.action_preview()
        self.assertEqual((batch.accepted_count, batch.rejected_count), (1, 2))
        self.assertIn('record_boundary', batch.issue_ids.mapped('issue_code'))
        batch.action_reset_preview()
        batch.source_file = base64.b64encode(b'source_id,name,mobile_phone,active\n1,Good,01012345678,t\n2,"' + b'x' * 131073)
        batch.action_preview()
        self.assertTrue(batch.has_blocking_issues)
        self.assertEqual(batch.eligible_count, 0)
        self.assertFalse(batch.sudo().chunk_ids)

    def test_review_rejects_changed_source_and_wrong_company(self):
        batch = self._batch()
        batch.action_preview()
        other_company = self.env['res.company'].create({'name': 'Review other company'})
        with self.assertRaises(AccessError):
            batch.with_context(allowed_company_ids=[other_company.id]).action_download_review()
        batch.sudo().source_file = base64.b64encode(b'source_id,mobile_phone\n1,01112345678\n')
        with self.assertRaises(UserError):
            batch._review_csv_file()

    def test_cancel_invalidates_codes_and_export(self):
        batch = self._batch()
        row = self._generate(batch)[0]
        batch.action_cancel()
        self.assertFalse(self._claim(row))
        self.assertFalse(batch.sudo().chunk_ids.encrypted_export)
        with self.assertRaises(UserError):
            batch._export_csv()

    def test_expiry_and_attempt_budget(self):
        batch = self._batch()
        row = self._generate(batch)[0]
        record = self.Registry.search([('batch_id', '=', batch.id)])
        record.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        self.assertFalse(self._claim(row))
        record.expires_at = fields.Datetime.now() + timedelta(days=1)
        for _index in range(5):
            self.assertFalse(self._claim(row, code='bad'))
        self.assertFalse(self._claim(row))
        self.assertEqual(record.attempts, 5)

    def test_access_owner_and_protected_fields(self):
        batch = self._batch()
        self._generate(batch)
        for actor in (self.other_designer, self.portal, self.env.ref('base.public_user')):
            with self.assertRaises(AccessError):
                batch.with_user(actor)._export_csv()
            with self.assertRaises(AccessError):
                batch.with_user(actor).action_process_next()
        for model in ('ab_ecommerce_legacy_customer', 'ab_ecommerce_legacy_chunk', 'ab_ecommerce_legacy_export'):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.portal).search([])
        with self.assertRaises(AccessError):
            batch.write({'state': 'draft'})
        with self.assertRaises(AccessError):
            self.Registry.with_user(self.designer).search([]).read(['code_hash'])
        with self.assertRaises(AccessDenied):
            self.Registry.with_user(self.portal)._claim(self.other_portal, self.website, '01012345678', '123456789012', 'test')

    def test_context_cannot_forge_processing_state(self):
        batch = self.Batch.with_user(self.designer).with_context(default_state='done', default_created_count=999).create({'name': 'Context', 'website_id': self.website.id})
        self.assertEqual(batch.state, 'draft')
        self.assertEqual(batch.created_count, 0)
        with self.assertRaises(UserError):
            batch._export_csv()

    def test_company_and_website_isolation(self):
        batch = self._batch()
        row = self._generate(batch)[0]
        other_company = self.env['res.company'].create({'name': 'Legacy test company'})
        other_website = self.env['website'].create({'name': 'Other legacy site', 'company_id': other_company.id})
        with self.assertRaises(AccessDenied):
            self._claim(row, website=other_website)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self._batch().write({'website_id': other_website.id})
        website = self.env['website'].create({'name': 'Same company other site', 'company_id': self.website.company_id.id})
        self.assertFalse(self._claim(row, website=website))

    def test_prompt_only_after_verified_phone_and_claimed_badge(self):
        batch = self._batch()
        row = self._generate(batch)[0]
        registry = self.Registry.with_user(self.portal)
        self.assertFalse(registry._portal_status(self.portal, self.website)['eligible'])
        self.env['ab_storefront_auth_service']._set_identity(self.portal, 'phone', row['mobile_phone'])
        self.assertTrue(registry._portal_status(self.portal, self.website)['eligible'])
        self.assertTrue(self._claim(row))
        self.assertEqual(registry._portal_status(self.portal, self.website), {'linked': True, 'eligible': False})

    def test_processing_resumes_across_chunks(self):
        batch = self._batch()
        batch.action_preview()
        chunks = batch.sudo().chunk_ids
        payload = chunks.payload.replace('001', '002').replace('+201012345678', '+201012345679')
        self.env['ab_ecommerce_legacy_chunk'].create({'batch_id': batch.id, 'payload': payload})
        batch.sudo().accepted_count = 2
        self.assertFalse(batch.action_process_next()['done'])
        self.assertEqual(batch.created_count, 1)
        self.assertTrue(batch.action_process_next()['done'])
        self.assertEqual(batch.created_count, 2)

    def test_translated_action_and_sms_message(self):
        action = self.env.ref('ab_website_sale_product.action_activation_batches')
        self.assertNotEqual(action.with_context(lang='ar_001').name, action.with_context(lang='en_US').name)
        batch = self._batch()
        self._generate(batch)
        arabic = batch.with_context(lang='ar_001')._export_csv()
        english = batch.with_context(lang='en_US')._export_csv()
        self.assertNotEqual(arabic, english)


@tagged('post_install', '-at_install')
class TestLegacyActivationHTTP(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.attachment'].search([('url', '=like', '/web/assets/%')]).unlink()
        cls.website = cls.env.ref('website.default_website')
        cls.website.write({'language_ids': [(6, 0, cls.env['res.lang'].search([('code', 'in', ['en_US', 'ar_001'])]).ids)], 'default_lang_id': cls.env.ref('base.lang_en').id})
        params = cls.env['ir.config_parameter'].sudo()
        params.set_param('ab_storefront_auth.development', 'True')
        params.set_param('ab_website_sale_product.development', 'True')
        params.set_param('ab_storefront_auth.base_url', cls.base_url())
        cls.customer = new_test_user(cls.env, login='legacy_http@example.test', groups='base.group_portal', lang='en_US', company_id=cls.website.company_id.id)
        cls.designer = new_test_user(cls.env, login='legacy_http_designer', groups='base.group_user,website.group_website_designer,ab_store.ab_login_from_anywhere', lang='en_US', company_id=cls.website.company_id.id)

    def _batch(self):
        return self.env['ab_ecommerce_legacy_batch'].with_user(self.designer).create({
            'name': 'HTTP legacy test', 'website_id': self.website.id,
            'source_file': base64.b64encode(b'source_id,name,mobile_phone\n1,Legacy customer,01012345678\n'),
        })

    def _browser_with_capture(self, *args, **kwargs):
        original_ready = ChromeBrowser._wait_ready

        def capture(browser, condition):
            result = original_ready(browser, condition)
            if result:
                browser.take_screenshot().result(timeout=10)
            return result

        with patch.object(ChromeBrowser, '_wait_ready', capture):
            self.browser_js(*args, **kwargs)

    def test_http_activation_and_export_access(self):
        from lxml import html
        batch = self._batch()
        batch.action_preview()
        batch.action_process_next()
        row = next(csv.DictReader(io.StringIO(batch._export_csv())))
        self.authenticate(self.customer.login, self.customer.login)
        page = self.url_open('/my/legacy-activation')
        self.assertEqual(page.status_code, 200)
        self.assertIn('legacy_code', page.text)
        csrf = html.fromstring(page.text).xpath('//input[@name="csrf_token"]/@value')[0]
        self.assertEqual(self.url_open(f'/ab_legacy/exports/{batch.id}').status_code, 403)
        self.assertEqual(self.url_open('/my/legacy-activation', data={'phone': row['mobile_phone'], 'code': row['activation_code']}).status_code, 400)
        response = self.url_open('/my/legacy-activation', data={'csrf_token': csrf, 'phone': row['mobile_phone'], 'code': row['activation_code']})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(html.fromstring(response.text).xpath('//*[contains(concat(" ", normalize-space(@class), " "), " ab-legacy-welcome ")]'))
        self.authenticate(self.designer.login, self.designer.login)
        exported = self.url_open(f'/ab_legacy/exports/{batch.id}')
        self.assertEqual(exported.status_code, 200)
        self.assertIn('no-store', exported.headers['Cache-Control'])
        self.assertIn('message', exported.text)

    def test_backend_generation_button(self):
        batch = self._batch()
        batch.action_preview()
        self._browser_with_capture(
            f'/odoo/action-ab_website_sale_product.action_activation_batches/{batch.id}',
            """
            (async () => {
                document.querySelector('button[name="action_generate_codes"]').click();
                const deadline = Date.now() + 20000;
                while (!document.querySelector('button[name="action_download"]') && Date.now() < deadline) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                if (!document.querySelector('button[name="action_download"]')) {
                    throw new Error('Code generation did not reach the download state');
                }
                console.log('test successful');
            })();
            """,
            login=self.designer.login,
            ready="!!document.querySelector('button[name=action_generate_codes]')",
            timeout=60,
        )
        batch.invalidate_recordset()
        self.assertEqual(batch.state, 'done')
        self.assertEqual(batch.created_count, 1)

    def test_review_csv_http_permissions_and_translated_content(self):
        batch = self._batch()
        batch.action_preview()
        self.authenticate(self.customer.login, self.customer.login)
        self.assertEqual(self.url_open(f'/ab_legacy/review/{batch.id}').status_code, 403)
        self.designer.lang = 'ar_001'
        self.authenticate(self.designer.login, self.designer.login)
        response = self.url_open(f'/ab_legacy/review/{batch.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertIn('legacy-customer-review-', response.headers['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0]['المراجعة: الحالة'], 'صالح')
        self.assertNotIn('activation_code', rows[0])
        self.assertEqual(batch.created_count, 0)

    def test_arabic_column_review_table(self):
        batch = self._batch()
        batch.source_file = base64.b64encode(b'source_id,name,mobile_phone\n1,Invalid,not a phone\n2,Valid,01012345678\n')
        batch.action_preview()
        self.designer.lang = 'ar_001'
        self._browser_with_capture(
            f'/odoo/action-ab_website_sale_product.action_activation_batches/{batch.id}',
            """
            (async () => {
                const button = document.querySelector('button[name="action_review_issues"]');
                if (!button.textContent.includes('مراجعة جميع المشكلات')) {
                    throw new Error('Review button is not translated');
                }
                button.click();
                const deadline = Date.now() + 20000;
                while (!document.querySelector('th[data-name="issue_code"]') && Date.now() < deadline) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                for (const field of ['source_row', 'line_start', 'column_name', 'original_value', 'import_status', 'issue_code']) {
                    if (!document.querySelector(`th[data-name="${field}"]`)) {
                        throw new Error(`Missing review column ${field}`);
                    }
                }
                if (!document.body.textContent.includes('not a phone') || !document.body.textContent.includes('رقم محمول مصري')) {
                    throw new Error('The value and translated column-level reason are missing');
                }
                if (document.querySelector('.o_list_button_add')) {
                    throw new Error('Diagnostics must be read only');
                }
                console.log('test successful');
            })();
            """,
            login=self.designer.login,
            ready="!!document.querySelector('button[name=action_review_issues]')",
            timeout=60,
        )
        self._browser_with_capture(
            '/odoo/action-ab_website_sale_product.action_legacy_import_issues',
            "console.log('test successful');",
            login=self.designer.login,
            ready="!!document.querySelector('th[data-name=issue_code]')",
            timeout=60,
        )

    def test_stock_toolbar_opens_legacy_customers(self):
        action = self.env.ref('ab_website_sale_product.action_activation_batches')
        self.designer.lang = 'ar_001'
        label = action.with_context(lang='ar_001').name
        self.assertNotEqual(label, action.with_context(lang='en_US').name)
        self._browser_with_capture(
            '/odoo/ecommerce-eplus-stock',
            f"""
            (async () => {{
                const button = document.querySelector('button[name="{action.id}"]');
                if (button.textContent.trim() !== {json.dumps(label)}) {{
                    throw new Error('Legacy customer button is not translated');
                }}
                const sync = document.querySelector('button[name="action_start_full_inventory_sync"]');
                if (button.previousElementSibling !== sync) {{
                    throw new Error('Legacy customer button must follow the three stock buttons');
                }}
                button.click();
                const deadline = Date.now() + 20000;
                while (!document.querySelector('th[data-name="accepted_count"]') && Date.now() < deadline) {{
                    await new Promise(resolve => setTimeout(resolve, 100));
                }}
                if (!document.querySelector('th[data-name="accepted_count"]')) {{
                    throw new Error('Legacy customer batches did not open');
                }}
                console.log('test successful');
            }})();
            """,
            login=self.designer.login,
            ready=f'!!document.querySelector(\'button[name="{action.id}"]\')',
            timeout=60,
        )

    def test_arabic_mobile_activation_page(self):
        self.customer.lang = 'ar_001'
        self.browser_size = '390x844'
        self._browser_with_capture(
            '/ar/my/legacy-activation',
            """
            const page = document.querySelector('.ab-legacy-activation');
            if (document.documentElement.dir !== 'rtl') {
                throw new Error('Arabic activation page must be RTL');
            }
            if (document.documentElement.scrollWidth > window.innerWidth + 2) {
                throw new Error('Activation page overflows mobile width');
            }
            if (page.querySelector('#legacy_code').dir !== 'ltr') {
                throw new Error('Activation code must remain LTR');
            }
            console.log('test successful');
            """,
            login=self.customer.login,
            ready="!!document.querySelector('.ab-legacy-activation #legacy_code')",
            timeout=60,
        )
