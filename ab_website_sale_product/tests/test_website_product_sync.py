from unittest.mock import patch

from psycopg2.errors import SerializationFailure

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user


class TestWebsiteProductSync(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('ir_attachment.location', 'db')
        cls.Product = cls.env['ab_product'].sudo()
        cls.Job = cls.env['ab_website_product_sync_job'].sudo()
        cls.Job.search([]).write({'state': 'done', 'background_requested': False})
        cls.group = cls.env['ab_product_group'].create({'name': 'Body Care L3'})
        cls.tag = cls.env['ab_product_tag'].create({'name': 'Sync Test Tag', 'priority': 7})

    def product(self, code='SYNC-TEST'):
        return self.Product.create({
            'name': code, 'product_card_name': code, 'code': code,
            'description': 'Description <safe>\nSecond line', 'default_price': 23.5,
            'default_cost': 10.0, 'website_sale_available': True,
            'groups_ids': [Command.set(self.group.ids)], 'tag_ids': [Command.set(self.tag.ids)],
        })

    def job(self, products):
        job = self.Job.create({'state': 'running', 'total_count': len(products)})
        job._add_product_lines(products)
        return job

    def test_create_update_and_noop(self):
        products = self.product('SYNC-A') | self.product('SYNC-B')
        outcomes = {}
        templates = products._sync_website_products(outcomes=outcomes)
        self.assertEqual(len(templates), 2)
        self.assertEqual(set(outcomes.values()), {'created'})
        self.assertTrue(all(templates.mapped('is_published')))
        self.assertTrue(all(templates.mapped('image_1920')))
        self.assertEqual(set(templates.mapped('list_price')), {23.5})
        self.assertEqual(set(templates.product_tag_ids.mapped('name')), {self.tag.name})
        self.assertFalse(any(products.mapped('website_sync_pending')))
        Template = type(self.env['product.template'])
        original = Template.write
        writes = []

        def count_write(records, values):
            if records & templates:
                writes.append(list(values))
            return original(records, values)

        with patch.object(Template, 'write', count_write):
            products._sync_website_products(outcomes=outcomes)
        self.assertEqual(writes, [])
        self.assertEqual(set(outcomes.values()), {'unchanged'})
        products.write({'default_price': 30.0})
        products._sync_website_products(outcomes=outcomes)
        self.assertEqual(set(outcomes.values()), {'updated'})
        self.assertEqual(set(templates.mapped('list_price')), {30.0})

    def test_category_translation_and_tag_changes(self):
        product = self.product()
        template = product._sync_website_products()
        category = template.public_categ_ids
        self.assertEqual(category.with_context(lang=False).name, 'Body Care')
        if self.env['res.lang'].search([('code', '=', 'ar_001')]):
            self.assertNotEqual(category.with_context(lang='ar_001').name, category.with_context(lang='en_US').name)
        self.tag.write({'priority': 9})
        self.assertTrue(product.website_sync_pending)
        product._sync_website_products()
        self.assertEqual(template.product_tag_ids.sequence, 9)
        self.assertEqual(template.public_categ_ids, category)
        product.write({'tag_ids': [Command.clear()]})
        product._sync_website_products()
        self.assertFalse(template.product_tag_ids)

    def test_missing_category_created_once(self):
        Category = self.env['product.public.category'].with_context(lang=False)
        existing = Category.search([('name', '=', 'Body Care')])
        existing.write({'name': 'Archived Test Category Name'})
        products = self.product('SYNC-A') | self.product('SYNC-B')
        templates = products._sync_website_products()
        self.assertEqual(len(templates.public_categ_ids), 1)
        self.assertEqual(templates.public_categ_ids.name, 'Body Care')

    def test_dirty_card_ancestor_barcode_and_membership(self):
        product = self.product()
        product._sync_website_products()
        ancestor = self.env['ab_product_group'].create({'name': 'Beauty'})
        self.group.parent_id = ancestor
        product._sync_website_products()
        ancestor.name = 'Medicine'
        self.env.flush_all()
        self.assertTrue(product.website_sync_pending)
        product._sync_website_products()
        product.product_card_id.description = 'Updated delegated description'
        self.assertTrue(product.website_sync_pending)
        product._sync_website_products()
        barcode = self.env['ab_product_barcode'].create({'name': '99880011'})
        product.barcode_ids = barcode
        product._sync_website_products()
        barcode.name = '99880012'
        self.assertTrue(product.website_sync_pending)
        template = product._sync_website_products()
        self.assertEqual(template.product_variant_id.barcode, '99880012')
        product.groups_ids = False
        self.assertTrue(product.website_sync_pending)

    def test_database_failure_isolated_and_retry(self):
        good = self.product('SYNC-GOOD')
        bad = self.product('SYNC-BAD')
        job = self.job(good | bad)
        original = type(self.Product)._prepare_website_product_template_vals

        def fail_one(product, sync_cache=None):
            if product == bad:
                product.env.cr.execute('SELECT 1 / 0')
            return original(product, sync_cache=sync_cache)

        with patch.object(type(self.Product), '_prepare_website_product_template_vals', fail_one):
            job._process_next_batch()
        self.assertEqual(job.created_count, 1)
        self.assertEqual(job.failed_count, 1)
        self.assertEqual(job.state, 'failed')
        failed = job.line_ids.filtered(lambda line: line.state == 'failed')
        self.assertTrue(failed.message)
        job.action_retry_failed()
        job._process_next_batch()
        self.assertEqual(job.created_count, 2)
        self.assertEqual(job.failed_count, 0)
        self.assertEqual(job.state, 'done')
        self.assertEqual(failed.attempts, 2)
        self.assertFalse(failed.message)

    def test_barcode_conflict_keeps_existing_and_transaction_usable(self):
        barcode = self.env['ab_product_barcode'].create({'name': '99887766'})
        products = self.product('SYNC-A') | self.product('SYNC-B')
        products.barcode_ids = barcode
        templates = products._sync_website_products()
        self.assertEqual(len(templates), 2)
        self.assertEqual(len(templates.product_variant_id.filtered(lambda p: p.barcode == barcode.name)), 1)
        self.env.cr.execute('SELECT 1')
        self.assertEqual(self.env.cr.fetchone(), (1,))

    def test_serialization_failure_propagates(self):
        product = self.product()
        job = self.job(product)
        with patch.object(type(self.Product), '_sync_website_products', side_effect=SerializationFailure):
            with self.assertRaises(SerializationFailure):
                job._process_next_batch()
        self.assertEqual(job.line_ids.state, 'pending')

    def test_duplicate_execution_and_resume(self):
        products = self.product('SYNC-A') | self.product('SYNC-B')
        job = self.job(products)
        with patch.object(type(job), '_get_batch_size', return_value=1):
            self.assertTrue(job._process_next_batch())
            self.assertEqual(job.processed_count, 1)
            self.env.flush_all()
            self.env.invalidate_all()
            self.assertFalse(job._process_next_batch())
        self.assertEqual(job.processed_count, 2)
        self.assertFalse(job._process_next_batch())
        self.assertEqual(job.processed_count, 2)
        self.assertEqual(self.env['product.template'].search_count([('ab_product_id', 'in', products.ids)]), 2)

    def test_cron_checkpoint_budget(self):
        job = self.job(self.product('SYNC-A') | self.product('SYNC-B'))
        commits = []

        def checkpoint(cron, processed=0, **kwargs):
            commits.append((processed, kwargs['remaining']))
            return 0

        with patch.object(type(job), '_get_batch_size', return_value=1), patch.object(type(self.env['ir.cron']), '_commit_progress', checkpoint):
            self.Job.cron_process_website_product_sync_jobs()
        self.assertEqual(commits, [(1, 1)])
        self.assertEqual(job.state, 'running')

    def test_manual_batch_honors_selection_in_bounded_chunks(self):
        job = self.Job.create({'state': 'running', 'total_count': 20000})
        chunks = []

        def process_chunk(record, limit=None):
            count = min(limit, 250, record.total_count - record.processed_count)
            chunks.append(count)
            record.processed_count += count
            if record.processed_count == record.total_count:
                record._mark_done()
                return False
            return True

        with patch.object(type(job), '_process_next_batch', process_chunk):
            for option in ('250', '500', '1000', '5000', '10000', '15000'):
                with self.subTest(option=option):
                    job.write({'batch_size_option': option, 'processed_count': 0})
                    chunks.clear()
                    job.action_process_next_batch()
                    self.assertEqual(job.processed_count, int(option))
                    self.assertEqual(job.batch_size, int(option))
                    self.assertEqual(chunks, [250] * (int(option) // 250))

    def test_manual_batch_stops_at_remaining_products(self):
        job = self.job(self.product('SYNC-A') | self.product('SYNC-B'))
        job.batch_size_option = '1000'
        job.action_process_next_batch()
        self.assertEqual(job.processed_count, 2)
        self.assertEqual(job.state, 'done')

    def test_manual_batch_respects_queue_boundary_and_changed_selection(self):
        job = self.Job.create({'state': 'running', 'total_count': 501, 'batch_size_option': '500'})
        lines = self.env['ab_website_product_sync_job_line'].create([
            {'job_id': job.id} for _index in range(501)
        ])
        job.action_process_next_batch()
        self.assertEqual(job.processed_count, 500)
        self.assertEqual(job.skipped_count, 500)
        self.assertEqual(len(lines.filtered(lambda line: line.state == 'pending')), 1)
        self.assertEqual(job.state, 'running')
        job.batch_size_option = '1000'
        job.action_process_next_batch()
        self.assertEqual(job.processed_count, 501)
        self.assertEqual(job.state, 'done')

    def test_manual_batch_stops_when_locked(self):
        job = self.Job.create({'state': 'running', 'batch_size_option': '1000'})
        with patch.object(type(self.Product), '_lock_website_sync', return_value=False) as lock:
            job.action_process_next_batch()
        self.assertEqual(lock.call_count, 1)
        self.assertEqual(job.processed_count, 0)

    def test_large_selection_keeps_cron_checkpoint_bounded(self):
        job = self.Job.create({'state': 'running', 'batch_size_option': '15000'})
        Line = type(self.env['ab_website_product_sync_job_line'])
        original = Line.search
        limits = []

        def search_lines(records, domain, *args, **kwargs):
            limits.append(kwargs.get('limit'))
            return original(records, domain, *args, **kwargs)

        with patch.object(Line, 'search', search_lines), patch.object(type(self.env['ir.cron']), '_commit_progress', return_value=0):
            self.Job.cron_process_website_product_sync_jobs()
        self.assertEqual(limits, [250])
        self.assertEqual(job.state, 'done')

    def test_process_all_returns_without_processing_or_triggering_cron(self):
        job = self.job(self.product())
        with patch.object(type(job), '_background_worker_online', return_value=True), \
             patch.object(type(job), '_process_next_batch') as process, \
             patch.object(type(self.env['ir.cron']), '_trigger') as trigger:
            result = job.action_process_to_completion()
            job.action_process_to_completion()
        process.assert_not_called()
        trigger.assert_not_called()
        self.assertEqual(result['tag'], 'reload')
        self.assertTrue(job.background_requested)
        self.assertEqual(job.background_user_id, self.env.user)
        self.assertEqual(job.processed_count, 0)

    def test_process_all_draft_preparation_is_deferred(self):
        job = self.Job.create({})
        with patch.object(type(job), '_background_worker_online', return_value=True), \
             patch.object(type(job), '_prepare_full_sync') as prepare:
            job.action_process_to_completion()
        prepare.assert_not_called()
        self.assertEqual(job.state, 'draft')
        self.assertTrue(job.background_requested)

    def test_process_all_requires_online_worker(self):
        job = self.job(self.product())
        with patch.object(type(job), '_background_worker_online', return_value=False):
            with self.assertRaises(UserError):
                job.action_process_to_completion()
        self.assertFalse(job.background_requested)

    def test_background_ignores_manual_size_and_finishes_all(self):
        job = self.Job.create({'state': 'running', 'total_count': 501, 'batch_size_option': '15000'})
        self.env['ab_website_product_sync_job_line'].create([{'job_id': job.id} for _index in range(501)])
        with patch.object(type(job), '_background_worker_online', return_value=True):
            job.action_process_to_completion()
        for expected in (250, 500, 501):
            with patch.object(type(job), '_get_batch_size', side_effect=AssertionError('Manual size read')):
                job._process_background_checkpoint()
            self.assertEqual(job.processed_count, expected)
        self.assertEqual(job.state, 'done')
        self.assertFalse(job.background_requested)

    def test_cancel_background_stops_and_manual_cannot_interleave(self):
        job = self.job(self.product())
        with patch.object(type(job), '_background_worker_online', return_value=True):
            job.action_process_to_completion()
        with self.assertRaises(UserError):
            job.action_process_next_batch()
        job.action_cancel()
        self.assertEqual(job._process_background_checkpoint(), 0)
        self.assertEqual(job.state, 'cancelled')
        self.assertFalse(job.background_requested)
        self.assertEqual(job.processed_count, 0)

    def test_background_rechecks_requester_permissions(self):
        job = self.job(self.product())
        user = new_test_user(self.env, login='website_sync_background_reader', groups='base.group_user')
        job.write({'background_requested': True, 'background_user_id': user.id,
                   'background_company_id': user.company_id.id})
        with self.assertRaises(AccessError):
            job._process_background_checkpoint()
        self.assertEqual(job.processed_count, 0)
        with self.assertRaises(AccessError):
            job.with_user(user).action_process_to_completion()

    def test_background_checkpoint_creates_real_products(self):
        products = self.product('SYNC-BG-A') | self.product('SYNC-BG-B')
        job = self.job(products)
        with patch.object(type(job), '_background_worker_online', return_value=True):
            job.action_process_to_completion()
        self.assertEqual(job._process_background_checkpoint(), 2)
        self.assertEqual(job.created_count, 2)
        self.assertEqual(job.state, 'done')
        self.assertFalse(job.background_requested)
        self.assertEqual(len(job.line_ids.product_template_id), 2)

    def test_global_cron_does_not_claim_background_jobs(self):
        job = self.job(self.product())
        with patch.object(type(job), '_background_worker_online', return_value=True):
            job.action_process_to_completion()
        with patch.object(type(job), '_process_next_batch') as process:
            self.Job.cron_process_website_product_sync_jobs()
        process.assert_not_called()

    def test_remaining_preview_skips_clean_and_counts_missing_and_review(self):
        clean = self.product('SYNC-CLEAN')
        changed = self.product('SYNC-CHANGED')
        missing = self.product('SYNC-MISSING')
        (clean | changed)._sync_website_products()
        changed.default_price = 29.0
        self.env.flush_all()
        job = self.Job.create({})
        with patch.object(type(job), '_full_sync_product_domain', return_value=fields.Domain('id', 'in', (clean | changed | missing).ids)):
            job.action_start_full_sync()
        self.assertEqual(job.already_synced_count, 1)
        self.assertEqual(job.total_count, 2)
        self.assertEqual(job.catalog_count, 3)
        self.assertEqual(job.completed_count, 1)
        self.assertAlmostEqual(job.progress, 100 / 3)
        self.assertEqual(job.missing_count, 1)
        self.assertEqual(job.review_count, 1)
        self.assertEqual(job.line_ids.ab_product_id, changed | missing)
        self.assertFalse(missing.website_product_tmpl_id)
        self.assertFalse(job.background_requested)

    def test_remaining_preview_all_clean_stays_complete(self):
        products = self.product('SYNC-CLEAN-A') | self.product('SYNC-CLEAN-B')
        products._sync_website_products()
        job = self.Job.create({})
        with patch.object(type(job), '_full_sync_product_domain', return_value=fields.Domain('id', 'in', products.ids)), \
             patch.object(type(self.Product), '_sync_website_products') as sync:
            job.action_start_full_sync()
        sync.assert_not_called()
        self.assertEqual(job.progress, 100)
        self.assertEqual(job.state, 'done')
        self.assertEqual(job.already_synced_count, 2)
        self.assertEqual(job.remaining_count, 0)
        self.assertFalse(job.line_ids)

    def test_cancelled_all_resumes_same_job_without_repeating_success(self):
        products = self.product('SYNC-A') | self.product('SYNC-B')
        job = self.job(products)
        job._process_next_batch(limit=1)
        first = job.line_ids[:1]
        job.action_cancel()
        with patch.object(type(job), '_background_worker_online', return_value=True):
            job.action_process_to_completion()
        self.assertEqual(job.processed_count, 1)
        self.assertEqual(job.state, 'running')
        job._process_background_checkpoint()
        self.assertEqual(job.created_count, 2)
        self.assertEqual(job.processed_count, 2)
        self.assertEqual(first.attempts, 1)
        self.assertEqual(job.state, 'done')

    def test_old_full_queue_skips_clean_products_before_sync(self):
        clean = self.product('SYNC-CLEAN')
        missing = self.product('SYNC-MISSING')
        clean._sync_website_products()
        job = self.job(clean | missing)
        job.action_start_full_sync()
        self.assertEqual(job.processed_count, 1)
        self.assertEqual(job.unchanged_count, 1)
        self.assertEqual(job.progress, 50)
        self.assertEqual(job.remaining_count, 1)
        self.assertEqual(job.line_ids[:1].attempts, 0)

    def test_completed_console_redirects_to_unfinished_job(self):
        completed = self.Job.create({'state': 'done'})
        running = self.job(self.product())
        with patch.object(type(running), '_background_worker_online', return_value=True):
            action = completed.action_process_to_completion()
        self.assertEqual(action['res_id'], running.id)
        self.assertTrue(running.background_requested)
        self.assertEqual(completed.state, 'done')

    def test_destination_changes_require_review(self):
        product = self.product()
        template = product._sync_website_products()
        self.env.flush_all()
        self.assertFalse(product.website_sync_pending)
        template.list_price = 100.0
        self.assertTrue(product.website_sync_pending)
        product._sync_website_products()
        self.env.flush_all()
        self.assertFalse(product.website_sync_pending)
        self.assertEqual(template.list_price, product.default_price)
        template.product_variant_id.barcode = '9988774411'
        self.assertTrue(product.website_sync_pending)

    def test_remaining_list_is_scoped_and_failures_are_not_complete(self):
        job = self.job(self.product())
        job.write({'already_synced_count': 99, 'processed_count': 1, 'failed_count': 1, 'state': 'failed'})
        job.line_ids.state = 'failed'
        action = job.action_show_remaining()
        self.assertEqual(self.env[action['res_model']].search(action['domain']), job.line_ids)
        self.assertEqual(job.progress, 99)
        self.assertEqual(job.remaining_count, 1)
        self.assertEqual(job.missing_count, 1)

    def test_internal_user_cannot_process_job(self):
        job = self.job(self.product())
        user = new_test_user(self.env, login='website_sync_reader', groups='base.group_user')
        with self.assertRaises(AccessError):
            job.with_user(user).action_process_next_batch()

    def test_delta_handles_unpublishing(self):
        product = self.product()
        template = product._sync_website_products()
        product.website_sale_available = False
        job = self.job(product)
        job.sync_mode = 'delta'
        job._process_next_batch()
        self.assertFalse(template.is_published)
        self.assertFalse(product.website_sync_pending)

    def test_archived_template_reused(self):
        product = self.product()
        template = product._sync_website_products()
        template.active = False
        synced = product._sync_website_products()
        self.assertEqual(synced.id, template.id)
        self.assertTrue(synced.active)

    def test_delta_queue_selects_only_dirty(self):
        products = self.product('SYNC-A') | self.product('SYNC-B')
        products._sync_website_products()
        products[0].default_price = 31.0
        original = type(self.Product).search

        def local_search(records, domain, *args, **kwargs):
            if records._name == 'ab_product':
                from odoo import fields
                domain = fields.Domain(domain) & fields.Domain('id', 'in', products.ids)
            return original(records, domain, *args, **kwargs)

        with patch.object(type(self.Product), 'search', local_search):
            job = self.Job._queue_delta_sync()
        self.assertEqual(job.line_ids.ab_product_id, products[0])
        job._process_next_batch()
        self.assertEqual(job.updated_count, 1)
