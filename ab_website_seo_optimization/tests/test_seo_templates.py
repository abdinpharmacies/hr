import copy
import json
from unittest.mock import Mock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..services.providers import ProviderFailure
from ..services.seo_templates import deterministic, fingerprints, validate


@tagged('post_install', '-at_install')
class TestSeoTemplates(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.templates = cls.env['ab_seo_template']
        cls.general = cls.env.ref('ab_website_seo_optimization.seo_template_general')
        cls.medicine = cls.env.ref('ab_website_seo_optimization.seo_template_medicine')
        card = cls.env['ab_product_card'].create({'name': 'CATALOG TABLET 500 MG TAB 20 TAB', 'is_medicine': True})
        product = cls.env['ab_product'].create({'product_card_id': card.id, 'code': 'TEMPLATE-001', 'effective_material': 'CATALOG INGREDIENT'})
        cls.product = cls.env['product.template'].create({'name': 'CATALOG TABLET 500 MG TAB 20 TAB', 'ab_product_id': product.id, 'is_published': True, 'sale_ok': True})
        cls.pipeline = cls.env['ab_seo_pipeline'].create({'name': 'Template test', 'domain': 'drug', 'ai_mode': 'off'})

    def job(self, **values):
        job = self.env['ab.product.seo.bulk.optimization'].create(dict({'name': 'Template pilot', 'pipeline_id': self.pipeline.id,
            'product_selection_ids': [(6, 0, self.product.ids)], 'batch_limit': 10, 'lang_mode': 'all', 'regeneration_mode': 'selected'}, **values))
        return job

    def run_job(self, **values):
        job = self.job(**values)
        job._enqueue_bulk_optimization()
        job._run_bulk_optimization_chunk()
        return job

    def content(self):
        facts = {'name': 'CATALOG TABLET 500 MG TAB 20 TAB', 'product_code': 'TEMPLATE-001', 'active_ingredients': 'CATALOG INGREDIENT', 'strength': '500 MG', 'dosage_form': 'TABLET', 'package': '20 TAB'}
        contract = self.medicine._contract()
        content = deterministic(contract, facts, 'en_US', lambda text: text)
        return content, contract, facts

    def test_selection_specific_parent_explicit(self):
        parent = self.env['product.public.category'].create({'name': 'Template Parent'})
        child = self.env['product.public.category'].create({'name': 'Template Child', 'parent_id': parent.id})
        self.general.category_ids = parent
        self.medicine.category_ids = child
        self.product.public_categ_ids = child
        self.assertEqual(self.templates._select(self.product)[0], self.medicine)
        self.medicine.category_ids = False
        self.assertEqual(self.templates._select(self.product)[0], self.general)
        self.product.ab_seo_template_id = self.medicine
        self.assertEqual(self.templates._select(self.product)[0], self.medicine)

    def test_real_category_conflict_requires_review(self):
        category = self.env['product.public.category'].create({'name': 'Medicines'})
        self.product.write({'name': 'CLEAR TISSUES 550 BOX', 'public_categ_ids': [(6, 0, category.ids)]})
        self.product.ab_product_id.is_medicine = False
        template, context = self.templates._select(self.product)
        self.assertEqual(template, self.medicine)
        self.assertIn('category_product_signal_conflict', context['conflicts'])
        self.assertIn('medicine_category_flag_conflict', context['conflicts'])

    def test_required_missing_and_optional_omitted(self):
        content, contract, facts = self.content()
        facts.pop('active_ingredients')
        content = deterministic(contract, facts, 'en_US', lambda value: value)
        self.assertNotIn('active_ingredients', [s['key'] for s in content['sections']])
        self.assertNotIn('warnings', [s['key'] for s in content['sections']])
        report = validate(content, contract, facts, 'en_US')
        self.assertIn('missing_fact:active_ingredients', report['warnings'])
        self.assertFalse(report['errors'])

    def test_forbidden_section_and_invented_fact_rejected(self):
        content, contract, facts = self.content()
        content['sections'].append({'key': 'medical_claims', 'content': '100% safe', 'fact_keys': ['name']})
        report = validate(content, contract, facts, 'en_US')
        self.assertEqual(report['status'], 'rejected')
        self.assertIn('forbidden_or_duplicate_section', report['errors'])
        content, contract, facts = self.content()
        content['sections'][1]['content'] = 'INVENTED INGREDIENT'
        self.assertIn('unsupported_section_text:active_ingredients', validate(content, contract, facts, 'en_US')['errors'])

    def test_unsupported_medical_claims_both_languages(self):
        for claim in ('cures diabetes', 'clinically proven', 'doctor recommended', '100% safe', 'يعالج السكري', 'يشفي المرض', 'آمن 100%'):
            content, contract, facts = self.content()
            content['meta_description'] += ' ' + claim
            self.assertEqual(validate(content, contract, facts, 'en_US')['status'], 'rejected', claim)

    def test_seo_identity_lengths_stuffing(self):
        content, contract, facts = self.content()
        content['meta_title'] = 'Wrong Product'
        self.assertIn('product_identity:meta_title', validate(content, contract, facts, 'en_US')['errors'])
        content['meta_title'] = facts['name'] + ' buy' * 8
        self.assertIn('keyword_stuffing:meta_title', validate(content, contract, facts, 'en_US')['errors'])

    def test_section_order_and_extra_numbers(self):
        content, contract, facts = self.content()
        content['sections'].reverse()
        content['meta_description'] += ' 900 MG'
        report = validate(content, contract, facts, 'en_US')
        self.assertIn('section_order', report['errors'])
        self.assertIn('unsupported_number', report['errors'])

    def test_deterministic_bilingual_pipeline_no_ai(self):
        with patch('requests.request') as network:
            job = self.run_job()
        network.assert_not_called()
        item = job.work_item_ids
        self.assertEqual(item.state, 'review_required')
        self.assertEqual(item.template_id, self.medicine)
        self.assertEqual(set(item.result), {'en_US', 'ar_001'})
        self.assertEqual([s['key'] for s in item.result['en_US']['sections']], [s['key'] for s in item.result['ar_001']['sections']])
        self.assertFalse(self.product.website_meta_title)
        self.assertEqual(item.seo_id.translation_ids.mapped('generation_model'), ['deterministic', 'deterministic'])

    def test_version_outdated_and_snapshot_immutable(self):
        job = self.run_job()
        translation = job.work_item_ids.seo_id.translation_ids[:1]
        snapshot = copy.deepcopy(translation.template_snapshot)
        self.medicine.generation_instructions = 'Revised instructions'
        self.assertTrue(translation.template_outdated)
        self.assertEqual(translation.template_snapshot, snapshot)
        section = self.medicine.section_ids[:1]
        old = self.medicine.version
        section.title = 'Revised heading'
        self.assertGreater(self.medicine.version, old)

    def test_exact_duplicate_and_similar_content(self):
        job = self.run_job()
        translation = job.work_item_ids.seo_id.translation_ids.filtered(lambda r: r.lang_code == 'en_US')
        other = self.env['product.template'].create({'name': 'Another website product'})
        content = translation._validation_content()
        messages = translation._duplicate_report(content, 'en_US', other, self.medicine, translation.trusted_facts)
        self.assertIn('duplicate:title_hash', messages)
        self.assertIn('duplicate:meta_hash', messages)
        self.assertIn('similar_description', messages)

    def test_dry_run_no_work_items_or_network(self):
        job = self.job(dry_run=True)
        with patch('requests.request') as network:
            job.action_template_dry_run()
        network.assert_not_called()
        self.assertFalse(job.work_item_ids)
        self.assertEqual(job.dry_run_report['products_analyzed'], 1)
        self.assertEqual(job.dry_run_report['products'][0]['template'], 'medicine')

    def test_pilot_required_for_large_run(self):
        job = self.job(batch_limit=100000)
        with self.assertRaises(UserError):
            job._enqueue_bulk_optimization()
        self.assertFalse(job.work_item_ids)
        job.batch_limit = 100
        job._enqueue_bulk_optimization()
        self.assertFalse(job.work_item_ids)
        job._discover_chunk(limit=1)
        self.assertEqual(len(job.work_item_ids), 1)
        self.assertEqual(job.discovery_cursor, self.product.id)

    def test_approved_regeneration_preserves_until_applied(self):
        first = self.run_job()
        seo = first.work_item_ids.seo_id
        for translation in seo.translation_ids:
            translation.review_notes = 'Checked literal catalog facts, omissions and metadata.'
            translation.action_review_evidence()
        seo.action_submit_review()
        seo.action_approve()
        versions = seo.version_ids
        original = seo.translation_ids.mapped('meta_title')
        second = self.run_job()
        self.assertEqual(seo.state, 'approved')
        self.assertEqual(seo.translation_ids.mapped('meta_title'), original)
        self.assertEqual(second.work_item_ids.last_error, 'existing_review_preserved')
        second.work_item_ids.action_apply_proposal()
        self.assertEqual(seo.state, 'generated')
        self.assertEqual(seo.version_ids, versions)
        self.assertTrue(all(seo.translation_ids.mapped('review_required')))

    def test_review_blocks_manual_unsupported_claim(self):
        job = self.run_job()
        translation = job.work_item_ids.seo_id.translation_ids[:1]
        translation.meta_description += ' cures diabetes'
        translation.review_notes = 'Attempted review'
        with self.assertRaises(ValidationError):
            translation.action_review_evidence()

    def test_template_access_denied_for_reader(self):
        group = self.env.ref('ab_website_seo_optimization.group_ab_website_seo_optimization_user')
        user = self.env['res.users'].create({'name': 'Template reader', 'login': 'template_reader_test', 'group_ids': [(6, 0, group.ids)]})
        self.assertEqual(self.general.with_user(user).code, 'general')
        with self.assertRaises(AccessError):
            self.general.with_user(user).write({'priority': 999})
        job = self.run_job()
        with self.assertRaises(AccessError):
            job.work_item_ids.seo_id.translation_ids[:1].with_user(user).write({'trusted_facts': {'name': 'Invented'}})
        with self.assertRaises(AccessError):
            self.env['ab.product.seo.translation'].with_user(user).create({'seo_id': job.work_item_ids.seo_id.id, 'lang_code': 'en_US', 'trusted_facts': {'name': 'Invented'}})
        with self.assertRaises(AccessError):
            job.work_item_ids.with_user(user).write({'result': {'en_US': {'meta_title': 'Invented'}}})

    def test_missing_key_falls_through_to_next_provider(self):
        missing = self.env['ab.seo.assistant'].create({'name': 'Missing credentials', 'provider': 'openrouter', 'allow_remote': True, 'model_name': 'test', 'license_reviewed': True, 'license_review_note': 'Fixture'})
        local = self.env['ab.seo.assistant'].create({'name': 'Local fixture', 'provider': 'local_ai', 'model_name': 'test', 'base_url': 'http://localhost:8000/v1', 'license_reviewed': True, 'license_review_note': 'Fixture'})
        self.pipeline.write({'ai_mode': 'always', 'line_ids': [(0, 0, {'provider_id': missing.id, 'sequence': 1}), (0, 0, {'provider_id': local.id, 'sequence': 2})]})
        content, contract, facts = self.content()
        content = {k: v for k, v in content.items() if k in ('meta_title', 'meta_description', 'short_description', 'sections')}
        content['keywords'] = [facts['name']]
        response = Mock(status_code=200, headers={})
        payload = {'choices': [{'message': {'content': json.dumps(content)}}]}
        response.json.return_value = payload
        response.content = json.dumps(payload).encode()
        response.iter_content.side_effect = lambda size: iter([response.content])
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch('requests.request', return_value=response) as network:
            job = self.run_job(generation_mode='ai', lang_mode='en_US')
        self.assertEqual(job.work_item_ids.state, 'review_required')
        self.assertEqual(network.call_count, 1)
        self.assertEqual(job.work_item_ids.seo_id.translation_ids.filtered('enrichment_item_id').generation_provider_id, local)
        self.assertIn(missing.health, ('auth', 'unavailable'))
        self.assertEqual(job.work_item_ids.result['en_US']['prompt_version'], self.medicine.prompt_version)

    def test_concentration_denominator_is_not_package(self):
        from ..services.seo_templates import literal_identity
        facts = literal_identity('EXAMPLE 500 MG/5 ML SYRUP 120 ML 1 BOTTLE')
        self.assertEqual(facts['strength'], '500 MG/5 ML')
        self.assertEqual(facts['package'], '120 ML | 1 BOTTLE')
        self.assertNotIn('5 ML', facts['package'])

    def test_malformed_section_key_is_rejected(self):
        content, contract, facts = self.content()
        content['sections'][0]['key'] = ['invalid']
        self.assertEqual(validate(content, contract, facts, 'en_US')['status'], 'rejected')

    def test_explicit_general_does_not_select_devices(self):
        self.product.ab_enrichment_domain = 'general'
        self.assertEqual(self.templates._select(self.product)[0], self.general)

    def test_local_exact_source_and_conflicting_evidence(self):
        from ..services.providers import adapter
        self.product.ab_seo_template_id = self.general
        self.product.ab_enrichment_identity = {'source_ids': {'egypt_a': 'exact-1'}}
        provider = self.env['ab.seo.assistant'].create({'name': 'Local trusted fixture', 'provider': 'egypt_a', 'license_reviewed': True, 'license_review_note': 'Fixture', 'allow_remote': False})
        dataset = self.env['ab_seo_dataset'].create({'provider_id': provider.id, 'filename': 'fixture.csv', 'source_version': 'fixture', 'state': 'done'})
        payload = adapter('egypt_a').normalize({'source_id': 'exact-1', 'name': self.product.name, 'brand': 'Catalog Brand'})
        self.env['ab_seo_source_record']._upsert(dataset, [payload])
        self.pipeline.line_ids = [(0, 0, {'provider_id': provider.id})]
        with patch('requests.request') as network:
            first = self.run_job()
        network.assert_not_called()
        self.assertEqual(first.work_item_ids.data_confidence, 'high')
        self.assertEqual(first.work_item_ids.trusted_facts['brand'], 'Catalog Brand')
        self.assertTrue(first.work_item_ids.fact_ids.filtered(lambda f: f.accepted and f.matched_by == 'source_id'))
        payload['facts']['strength'] = '999 MG'
        self.env['ab_seo_source_record']._upsert(dataset, [payload])
        second = self.run_job()
        self.assertEqual(second.work_item_ids.data_confidence, 'review_required')
        self.assertIn('source_identity_conflict:strength', second.work_item_ids.category_context['conflicts'])
        self.assertNotEqual(second.work_item_ids.trusted_facts.get('strength'), '999 MG')

    def test_generate_missing_preserves_complete_draft_language(self):
        first = self.run_job(lang_mode='en_US')
        seo = first.work_item_ids.seo_id
        english = seo.translation_ids.filtered(lambda t: t.lang_code == 'en_US')
        item = english.enrichment_item_id
        second = self.run_job(regeneration_mode='missing', lang_mode='all')
        self.assertEqual(set(second.work_item_ids.result), {'ar_001'})
        self.assertEqual(english.enrichment_item_id, item)

    def test_outdated_and_failed_regeneration_filters(self):
        first = self.run_job()
        outdated = self.job(regeneration_mode='outdated')
        self.assertEqual(outdated._template_should_skip(self.product), 'template_current')
        self.medicine.generation_instructions = 'Changed generation rules'
        self.assertFalse(outdated._template_should_skip(self.product))
        failed = self.job(regeneration_mode='failed')
        self.assertEqual(failed._template_should_skip(self.product), 'no_failed_generation')
        first.work_item_ids.state = 'failed'
        self.assertFalse(failed._template_should_skip(self.product))

    def test_100k_enqueue_after_reviewed_template_pilot_is_lazy(self):
        pilot = self.run_job()
        for translation in pilot.work_item_ids.seo_id.translation_ids:
            translation.review_notes = 'Checked source values and template omissions.'
            translation.action_review_evidence()
        pilot.pilot_review_notes = 'Representative medicine template reviewed.'
        pilot.action_validate_pilot()
        job = self.job(batch_limit=100000, pilot_job_id=pilot.id, template_filter_id=self.medicine.id)
        with patch('requests.request') as network:
            job._enqueue_bulk_optimization()
        network.assert_not_called()
        self.assertFalse(job.work_item_ids)
        job._discover_chunk(limit=1)
        self.assertEqual(len(job.work_item_ids), 1)
        self.medicine.generation_instructions = 'New rules require a new pilot'
        with self.assertRaises(UserError):
            job._run_bulk_optimization_chunk()

    def test_single_record_generation_uses_selected_mode(self):
        seo = self.env['ab.product.seo'].create({'product_template_id': self.product.id, 'ab_product_id': self.product.ab_product_id.id, 'template_generation_mode': 'deterministic', 'only_missing_seo': False})
        job = seo._optimize_single_published_product()
        self.assertEqual(job.regeneration_mode, 'selected')
        self.assertEqual(job.generation_mode, 'deterministic')

    def test_legacy_bulk_cannot_overwrite_template_draft(self):
        self.run_job()
        legacy = self.job(enrichment_enabled=False)
        with self.assertRaises(UserError):
            legacy._optimize_template(self.product)
        self.assertFalse(self.product.website_meta_title)
