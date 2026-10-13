from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.addons.integration_queue_job.exception import RetryableJobError
from odoo.addons.integration_queue_job.job import Job


@tagged('post_install', '-at_install')
class TestSeoQueue(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        card = cls.env['ab_product_card'].create({'name': 'SEO QUEUE CREAM 55 GM'})
        master = cls.env['ab_product'].create({'product_card_id': card.id, 'code': 'SEO-QUEUE-TEST'})
        cls.product = cls.env['product.template'].create({
            'name': 'SEO QUEUE CREAM 55 GM', 'ab_product_id': master.id,
            'is_published': True, 'sale_ok': True,
        })
        cls.pipeline = cls.env['ab_seo_pipeline'].create({'name': 'SEO Queue Test', 'domain': 'general', 'ai_mode': 'off'})

    def make_run(self, **values):
        return self.env['ab.product.seo.bulk.optimization'].create(dict({
            'name': 'SEO queue test', 'pipeline_id': self.pipeline.id,
            'generation_mode': 'deterministic', 'lang_mode': 'all', 'batch_limit': 10,
            'regeneration_mode': 'selected', 'product_selection_ids': [(6, 0, self.product.ids)],
        }, **values))

    def perform(self, run):
        queued = Job.load(self.env, run.queue_uuid)
        queued.set_started()
        queued.store()
        queued.perform()
        queued.set_done()
        queued.store()
        return queued

    def test_bulk_enqueues_without_cron_or_network_and_finishes_drafts(self):
        run = self.make_run()
        with patch('requests.request') as network:
            run.action_fill_with_ai_for_published_products()
            self.assertTrue(run.queue_uuid)
            self.assertFalse(run.work_item_ids)
            queued = self.perform(run)
        network.assert_not_called()
        self.assertEqual(queued.channel, 'root.seo')
        self.assertEqual(run.state, 'done')
        self.assertEqual(run.processed_count, 1)
        self.assertEqual(run.work_item_ids.state, 'review_required')
        self.assertEqual(set(run.work_item_ids.seo_id.translation_ids.mapped('lang_code')), {'en_US', 'ar_001'})
        self.assertFalse(self.product.website_meta_title)
        self.assertFalse(run.work_item_ids.seo_id.published_version_id)

    def test_single_record_enqueues_automatically(self):
        seo = self.env['ab.product.seo'].create({
            'product_template_id': self.product.id, 'ab_product_id': self.product.ab_product_id.id,
            'template_generation_mode': 'deterministic', 'only_missing_seo': False,
        })
        with patch('requests.request') as network:
            action = seo.action_fill_with_ai()
        network.assert_not_called()
        self.assertEqual(action['res_model'], 'ab.product.seo')
        self.assertEqual(action['res_id'], seo.id)
        run = seo.last_bulk_id
        self.assertTrue(run.queue_uuid)
        self.assertEqual(len(run.work_item_ids), 1)
        self.assertIn('queued or processing', seo.generation_feedback)
        with patch.object(type(run.work_item_ids), '_select_pipeline', return_value=self.pipeline):
            self.perform(run)
        self.assertEqual(seo.state, 'generated')
        self.assertTrue(all(seo.translation_ids.mapped('meta_title')))

    def test_continuation_is_durable_and_replayed_checkpoint_is_noop(self):
        other = self.product.copy({'name': 'SEO QUEUE SECOND CREAM', 'ab_product_id': False, 'is_published': True})
        card = self.env['ab_product_card'].create({'name': 'SEO QUEUE SECOND CREAM'})
        master = self.env['ab_product'].create({'product_card_id': card.id, 'code': 'SEO-QUEUE-SECOND'})
        other.ab_product_id = master
        run = self.make_run(product_selection_ids=[(6, 0, (self.product | other).ids)])
        run._enqueue_bulk_optimization()
        first = self.perform(run)
        self.assertEqual(run.processed_count, 1)
        self.assertEqual(run.state, 'queued')
        next_uuid = run.queue_uuid
        self.assertNotEqual(next_uuid, first.uuid)
        first.perform()
        self.assertEqual(run.queue_uuid, next_uuid)
        self.assertEqual(run.processed_count, 1)
        self.perform(run)
        self.assertEqual(run.state, 'done')
        self.assertEqual(run.processed_count, 2)

    def test_same_checkpoint_not_enqueued_twice(self):
        run = self.make_run()
        run._enqueue_bulk_optimization()
        uuid = run.queue_uuid
        run._enqueue_queue_checkpoint()
        self.assertEqual(run.queue_uuid, uuid)
        self.assertEqual(self.env['queue.job'].search_count([('identity_key', '=', f'seo:{run.id}:0')]), 1)
        queued = Job.load(self.env, uuid)
        queued.set_started()
        queued.store()
        run._enqueue_queue_checkpoint()
        self.assertEqual(run.queue_uuid, uuid)

    def test_provider_wait_uses_eta_and_retry_supersedes_old_callback(self):
        run = self.make_run()
        run._enqueue_bulk_optimization()
        next_attempt = fields.Datetime.now() + timedelta(minutes=5)

        def wait_for_provider(item):
            item.write({'state': 'waiting', 'attempts': 1, 'next_attempt_at': next_attempt})

        with patch.object(type(self.env['ab_seo_work_item']), '_process', wait_for_provider):
            self.perform(run)
        waiting_job = Job.load(self.env, run.queue_uuid)
        self.assertEqual(waiting_job.eta, next_attempt)
        self.assertEqual(run.work_item_ids.state, 'waiting')
        run.action_retry_failures()
        retry_uuid = run.queue_uuid
        self.assertNotEqual(retry_uuid, waiting_job.uuid)
        self.assertFalse(Job.load(self.env, retry_uuid).eta)
        waiting_job.perform()
        self.assertEqual(run.queue_uuid, retry_uuid)
        self.perform(run)
        self.assertEqual(run.state, 'done')

    def test_legacy_queued_run_can_resume(self):
        run = self.make_run()
        run.write({'state': 'queued', 'discovery_done': True, 'total_count': 1})
        self.env['ab_seo_work_item'].create({'job_id': run.id, 'product_id': self.product.id})
        self.assertFalse(run.queue_uuid)
        run.action_resume_job()
        self.assertTrue(run.queue_uuid)
        self.perform(run)
        self.assertEqual(run.state, 'done')

    def test_cancelled_or_archived_run_does_not_generate(self):
        for action in ('action_cancel_batch', 'action_archive'):
            with self.subTest(action=action):
                run = self.make_run()
                run._enqueue_bulk_optimization()
                getattr(run, action)()
                with patch.object(type(run), '_run_bulk_optimization_chunk') as process:
                    self.perform(run)
                process.assert_not_called()

    def test_failure_rolls_back_checkpoint_for_queue_retry(self):
        run = self.make_run()
        run._enqueue_bulk_optimization()
        uuid = run.queue_uuid
        with self.assertRaises(RuntimeError), self.env.cr.savepoint():
            with patch.object(type(self.env['ab_seo_work_item']), '_process', side_effect=RuntimeError('queue test')):
                self.perform(run)
        self.assertEqual(run.queue_checkpoint, 0)
        self.assertEqual(run.queue_uuid, uuid)
        self.assertEqual(run.state, 'queued')
        self.perform(run)
        self.assertEqual(run.state, 'done')

    def test_busy_run_is_retried_without_processing(self):
        run = self.make_run()
        run._enqueue_bulk_optimization()
        with patch.object(type(run), 'try_lock_for_update', return_value=run.browse()), self.assertRaises(RetryableJobError):
            self.perform(run)
        self.assertFalse(run.work_item_ids)

    def test_queue_metadata_cannot_be_forged(self):
        run = self.make_run()
        with self.assertRaises(AccessError):
            run.write({'queue_checkpoint': 4})
        with self.assertRaises(AccessError):
            self.make_run(queue_uuid='forged')

    def test_manager_identity_and_company_are_preserved(self):
        group = self.env.ref('ab_website_seo_optimization.group_ab_website_seo_optimization_manager')
        group |= self.env.ref('base.group_user')
        manager = self.env['res.users'].create({
            'name': 'SEO queue manager', 'login': 'seo_queue_manager_test',
            'group_ids': [(6, 0, group.ids)],
            'company_id': self.env.company.id, 'company_ids': [(6, 0, self.env.company.ids)],
        })
        run = self.make_run().with_user(manager)
        run._enqueue_bulk_optimization()
        queued = Job.load(self.env, run.queue_uuid)
        self.assertEqual(queued.recordset.env.uid, manager.id)
        self.assertEqual(queued.recordset.env.context['allowed_company_ids'], run.company_id.ids)
        self.perform(run)
        self.assertEqual(run.state, 'done')
        second = self.make_run().with_user(manager)
        second._enqueue_bulk_optimization()
        queued = Job.load(self.env, second.queue_uuid)
        other = self.env['res.company'].create({'name': 'SEO queue other company'})
        foreign = self.make_run(company_id=other.id)
        with self.assertRaises(AccessError):
            foreign.with_user(manager).action_resume_job()
        manager.active = False
        with self.assertRaises(AccessError):
            queued.perform()

    def test_reader_cannot_schedule_or_execute(self):
        group = self.env.ref('ab_website_seo_optimization.group_ab_website_seo_optimization_user')
        reader = self.env['res.users'].create({'name': 'SEO queue reader', 'login': 'seo_queue_reader_test', 'group_ids': [(6, 0, group.ids)]})
        run = self.make_run()
        for method in ('action_fill_with_ai_for_published_products', 'action_resume_job', 'action_retry_failures'):
            with self.subTest(method=method), self.assertRaises(UserError):
                getattr(run.with_user(reader), method)()
        with self.assertRaises(UserError):
            run.with_user(reader)._process_queue_checkpoint(0)
