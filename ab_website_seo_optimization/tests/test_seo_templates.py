import copy
import json
from unittest.mock import Mock, patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..services.providers import ProviderFailure
from ..services.seo_templates import core_product_name, deterministic, fingerprints, literal_identity, polish_generated_copy, validate


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
        cls.product.with_context(lang='ar_001').name = 'أقراص CATALOG TABLET 500 MG TAB 20 TAB'
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

    def test_personal_about_includes_grounded_form_and_package(self):
        personal = self.env.ref('ab_website_seo_optimization.seo_template_personal')
        facts = {'name': '555 SHAVING CREAM 55 GM 1 BOX', 'product_code': '64212',
                 'dosage_form': 'CREAM', 'package': '55 GM | 1 BOX'}
        contract = personal._contract()
        content = deterministic(contract, facts, 'en_US', lambda value: value)
        about = next(section for section in content['sections'] if section['key'] == 'about_product')
        self.assertEqual(about['fact_keys'], ['name', 'dosage_form', 'package'])
        self.assertEqual(about['content'], '555 SHAVING CREAM is packaged in 55 GM, 1 BOX.')
        self.assertFalse(validate(content, contract, facts, 'en_US')['errors'])

    def test_general_about_includes_package_without_generic_copy(self):
        facts = {'name': '0 SILK SUTURE WITH NEEDLE GMS 1 ONE UNIT', 'product_code': '78234', 'package': '1 ONE UNIT'}
        contract = self.general._contract()
        content = deterministic(contract, facts, 'en_US', lambda value: value)
        about = next(section for section in content['sections'] if section['key'] == 'about_product')
        self.assertEqual(about['fact_keys'], ['name', 'package'])
        self.assertEqual(about['content'], '0 SILK SUTURE WITH NEEDLE GMS is packaged in 1 ONE UNIT.')
        self.assertEqual(content['meta_description'], '0 SILK SUTURE WITH NEEDLE GMS — package: 1 ONE UNIT.')
        details = next(section for section in content['sections'] if section['key'] == 'product_information')
        self.assertEqual(details['content'], 'Product code: 78234\nPackage: 1 ONE UNIT')
        self.assertFalse(validate(content, contract, facts, 'en_US')['errors'])

    def test_gauze_dimensions_create_distinct_grounded_sections(self):
        name = '10 CM*10 CM VASELINE GAUZE 1 BOX'
        facts = {'name': name, 'product_code': '72249', **literal_identity(name)}
        self.assertEqual(facts['specifications'], '10 CM*10 CM')
        contract = self.general._contract()
        content = deterministic(contract, facts, 'en_US', lambda value: value)
        self.assertEqual([section['key'] for section in content['sections']], ['about_product', 'specifications', 'product_information'])
        self.assertEqual(content['short_description'], 'VASELINE GAUZE — size 10 CM*10 CM.')
        self.assertEqual(content['meta_description'], 'VASELINE GAUZE — size 10 CM*10 CM, package 1 BOX.')
        self.assertEqual(content['sections'][0]['content'], 'VASELINE GAUZE measures 10 CM*10 CM and comes in 1 BOX.')
        self.assertEqual(content['sections'][1]['content'], '10 CM*10 CM')
        self.assertEqual(content['seo_name'], '10 CM*10 CM VASELINE GAUZE')
        self.assertEqual(content['search_phrases'], [name, '10 CM*10 CM VASELINE GAUZE'])
        self.assertFalse(validate(content, contract, facts, 'en_US')['errors'])

    def test_english_name_suggestion_is_drafted_and_flagged_for_review(self):
        facts = {'name': '10 CM*10 CM شاش فازلين 1 BOX', 'name_en': '10 CM*10 CM Vaseline Gauze 1 BOX',
                 'product_code': '72249', 'specifications': '10 CM*10 CM', 'package': '1 BOX'}
        content = deterministic(self.general._contract(), facts, 'en_US', lambda value: value)
        self.assertEqual(content['meta_title'], facts['name_en'])
        self.assertIn('Vaseline Gauze', content['short_description'])
        report = validate(content, self.general._contract(), facts, 'en_US')
        self.assertFalse(report['errors'])
        self.assertIn('name_translation_requires_review', report['warnings'])
        content['content_kind'] = 'GENERATED_TEXT'
        content['sections'][0]['fact_keys'] = ['name_en', 'package']
        polished = polish_generated_copy(content, facts)
        self.assertEqual(polished['sections'][0]['fact_keys'], ['name', 'package'])
        self.assertFalse(validate(polished, self.general._contract(), facts, 'en_US')['errors'])
        arabic = deterministic(self.general._contract(), facts, 'ar_001', lambda value: value)
        self.assertNotIn('name_translation_requires_review', validate(arabic, self.general._contract(), facts, 'ar_001')['warnings'])

    def test_supplier_description_is_used_only_when_descriptive(self):
        job = self.job()
        item = self.env['ab_seo_work_item'].create({'job_id': job.id, 'product_id': self.product.id})
        self.product.ab_product_id.description = 'Before dispensing, verify this medicine against a similarly named item in the catalog.'
        self.assertNotIn('supplier_description', item._identity())
        description = 'Catalog tablet supplied as twenty tablets per package with the listed ingredient shown on the product label.'
        self.product.ab_seo_supplier_description = description
        identity = item._identity()
        self.assertEqual(identity['supplier_description'], description)
        facts = {key: value for key, value in identity.items() if key in ('name', 'supplier_description')}
        content = deterministic(self.medicine._contract(), facts, 'en_US', lambda value: value)
        about = next(section for section in content['sections'] if section['key'] == 'about_product')
        self.assertEqual(about['content'], description)
        self.assertIn('supplier_description', about['fact_keys'])

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
        content['keywords'] = [facts['name'], facts['active_ingredients']]
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


@tagged('post_install', '-at_install')
class TestSeoLanguages(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.general = cls.env.ref('ab_website_seo_optimization.seo_template_general')
        card = cls.env['ab_product_card'].create({'name': 'ABOU YOUSEF سنفره قدم خشب COD 975 1 BOX'})
        product = cls.env['ab_product'].create({'product_card_id': card.id, 'code': 'SEO-LANGUAGE-TEST'})
        cls.product = cls.env['product.template'].create({'name': card.name, 'ab_product_id': product.id, 'is_published': True, 'sale_ok': True})
        cls.seo = cls.env['ab.product.seo'].create({'product_template_id': cls.product.id})

    def test_original_mixed_name_requires_english_translation(self):
        facts = {'name': self.product.name, 'package': '1 BOX'}
        content = deterministic(self.general._contract(), facts, 'en_US', lambda value: value)
        self.assertFalse(content['meta_title'])
        report = validate(content, self.general._contract(), facts, 'en_US')
        self.assertEqual(report['status'], 'rejected')
        self.assertIn('product_name_translation_required:en_US', report['errors'])

    def test_arabic_requires_localized_identity(self):
        facts = {'name': 'Example Wooden Foot File 1 BOX', 'package': '1 BOX'}
        content = deterministic(self.general._contract(), facts, 'ar_001', lambda value: value)
        self.assertFalse(content['meta_title'])
        self.assertIn('product_name_translation_required:ar_001', validate(content, self.general._contract(), facts, 'ar_001')['errors'])

    def test_localized_names_preserve_brand_and_codes(self):
        from ..services.seo_templates import language_name
        facts = {'name': self.product.name, 'name_en': 'ABOU YOUSEF Wooden Foot File COD 975 1 BOX', 'name_ar': 'ABOU YOUSEF مبرد قدم خشبي COD 975 1 BOX'}
        self.assertEqual(language_name(facts, 'en_US'), facts['name_en'])
        self.assertEqual(language_name(facts, 'ar_001'), facts['name_ar'])

    def test_language_checks_allow_units_and_arabic_punctuation(self):
        from ..services.seo_templates import language_errors
        self.assertFalse(language_errors({'meta_description': 'Example، 20 ML.'}, 'en_US'))
        self.assertFalse(language_errors({'meta_title': 'عبوة Example 20 ML', 'seo_name': 'example-20-ml'}, 'ar_001'))

    def test_arabic_sections_cannot_hide_english_body(self):
        from ..services.seo_templates import language_errors
        content = {'meta_title': 'منتج Example', 'sections': [{'key': 'about_product', 'content': 'This product comes in one box.'}]}
        self.assertIn('language_mismatch:section:about_product', language_errors(content, 'ar_001'))

    def test_invalid_sections_return_validation_error(self):
        report = validate({'sections': 3}, self.general._contract(), {'name': 'Example'}, 'en_US')
        self.assertIn('invalid_sections', report['errors'])

    def test_manual_english_draft_cannot_be_approved_with_arabic(self):
        translation = self.seo.translation_ids.filtered(lambda row: row.lang_code == 'en_US')
        translation.write({'meta_title': self.product.name, 'meta_description': 'Example description.'})
        with self.assertRaises(UserError):
            translation._create_version()

    def test_manual_arabic_draft_cannot_be_approved_with_english(self):
        translation = self.seo.translation_ids.filtered(lambda row: row.lang_code == 'ar_001')
        translation.write({'meta_title': 'Example Product', 'meta_description': 'Example description.'})
        with self.assertRaises(UserError):
            translation._create_version()

    def test_old_invalid_version_cannot_publish(self):
        version = self.env['ab.product.seo.version'].sudo().create({'seo_id': self.seo.id, 'lang_code': 'en_US', 'version_number': 1,
            'meta_title': self.product.name, 'meta_description': 'Example description.'})
        with self.assertRaises(UserError):
            version._get_publish_field_values()

    def test_valid_bilingual_versions_keep_separate_values(self):
        values = {'en_US': ('Example Wooden Foot File', 'Wooden foot file, one box.'),
                  'ar_001': ('مبرد قدم خشبي Example', 'مبرد قدم خشبي في عبوة واحدة.')}
        for translation in self.seo.translation_ids:
            title, description = values[translation.lang_code]
            translation.write({'meta_title': title, 'meta_description': description})
            version = translation._create_version()
            self.assertEqual(version._get_publish_field_values()['website_meta_title'], title)

    def test_generation_prompt_requires_localized_descriptive_copy(self):
        from ..services.seo_templates import contract_prompt
        for language in ('en_US', 'ar_001'):
            prompt = contract_prompt(self.general._contract(), {'name': self.product.name}, [], language, {})
            self.assertIn('never copy Arabic generic product words into English output', prompt)
            self.assertIn('write natural Arabic sentences', prompt)
            self.assertIn('not a Google ranking signal', prompt)
            self.assertIn('Do not pad text to a character count', prompt)

    def test_english_supplier_text_is_rejected_for_arabic_section(self):
        facts = {'name': 'مبرد قدم خشبي Example', 'supplier_description': 'Wooden foot file supplied in one box.'}
        content = deterministic(self.general._contract(), facts, 'ar_001', lambda value: value)
        report = validate(content, self.general._contract(), facts, 'ar_001')
        self.assertIn('language_mismatch:section:about_product', report['errors'])

    def assistant(self):
        return self.env['ab.seo.assistant'].create({'name': 'Language test model', 'provider': 'local_ai',
            'model_name': 'test-model', 'assistant_type': 'ai', 'base_url': 'http://localhost:8000/v1',
            'endpoint_path': '/chat/completions', 'license_reviewed': True, 'license_review_note': 'Test fixture'})

    def test_non_groq_assistant_translates_english_product_terms(self):
        assistant = self.assistant()
        response = {'choices': [{'message': {'content': 'Wooden Foot File'}}]}
        with patch.object(type(assistant), '_request', return_value=response) as request:
            suggestion = assistant._suggest_english_product_name(self.product)
        self.assertEqual(suggestion, 'ABOU YOUSEF Wooden Foot File COD 975 1 BOX')
        self.assertIn('Do not transliterate', request.call_args.kwargs['payload']['messages'][-1]['content'])

    def test_assistant_translates_arabic_identity_preserving_numbers(self):
        assistant = self.assistant()
        self.product.with_context(lang='ar_001').name = 'Example Wooden Foot File COD 975 1 BOX'
        response = {'choices': [{'message': {'content': 'Example مبرد قدم خشبي COD 975 1 BOX'}}]}
        with patch.object(type(assistant), '_request', return_value=response):
            suggestion = assistant._suggest_arabic_product_name(self.product)
        self.assertEqual(suggestion, 'Example مبرد قدم خشبي COD 975 1 BOX')

    def test_arabic_name_suggestion_cannot_change_package_quantity(self):
        assistant = self.assistant()
        self.product.with_context(lang='ar_001').name = 'Example Wooden Foot File COD 975 1 BOX'
        response = {'choices': [{'message': {'content': 'Example مبرد قدم خشبي COD 975 2 BOX'}}]}
        with patch.object(type(assistant), '_request', return_value=response):
            self.assertFalse(assistant._suggest_arabic_product_name(self.product))

    def test_pipeline_provider_can_supply_localized_identity(self):
        assistant = self.assistant()
        pipeline = self.env['ab_seo_pipeline'].create({'name': 'Language pipeline', 'domain': 'general', 'ai_mode': 'always',
            'line_ids': [(0, 0, {'provider_id': assistant.id})]})
        job = self.env['ab.product.seo.bulk.optimization'].create({'name': 'Language run', 'generation_mode': 'ai',
            'pipeline_id': pipeline.id, 'lang_mode': 'en_US'})
        item = self.env['ab_seo_work_item'].create({'job_id': job.id, 'product_id': self.product.id})
        with patch.object(type(assistant), '_suggest_english_product_name', return_value='ABOU YOUSEF Wooden Foot File COD 975 1 BOX'):
            facts, provenance = item._collect_facts(item._identity(), pipeline)
        self.assertEqual(facts['name_en'], 'ABOU YOUSEF Wooden Foot File COD 975 1 BOX')
        evidence = self.env['ab_seo_enrichment_fact'].browse(provenance).filtered(lambda row: row.field_name == 'name_en')
        self.assertEqual(evidence.content_kind, 'UNVERIFIED_TEXT')
        self.assertEqual(evidence.lang_code, 'en_US')

    def arabic_copy(self):
        facts = {'name': 'ACCU CHEK PERFORMA جهاز قياس سكر 1 BOX', 'package': '1 BOX'}
        contract = self.general._contract('ar_001')
        content = deterministic(contract, facts, 'ar_001', lambda value: self.env['ab.product.seo'].with_context(lang='ar_001').env._(value))
        content.update(meta_title='جهاز قياس السكر ACCU CHEK PERFORMA 1 BOX',
            meta_description='جهاز ACCU CHEK PERFORMA لقياس السكر، يأتي في عبوة 1 BOX.',
            short_description='جهاز لقياس السكر من ACCU CHEK PERFORMA.',
            keywords=['جهاز قياس السكر', 'ACCU CHEK PERFORMA'], content_kind='GENERATED_TEXT')
        for section in content['sections']:
            if section['key'] == 'about_product':
                section['content'] = 'ACCU CHEK PERFORMA جهاز قياس السكر، بعبوة 1 BOX.'
        return facts, contract, content

    def test_natural_arabic_reordering_and_prefixes_pass_validation(self):
        facts, contract, content = self.arabic_copy()
        self.assertFalse(validate(content, contract, facts, 'ar_001')['errors'])

    def test_arabic_prefix_support_does_not_allow_invented_claims(self):
        facts, contract, content = self.arabic_copy()
        content['meta_description'] += ' يعالج المرض بدقة مضمونة.'
        self.assertTrue(validate(content, contract, facts, 'ar_001')['errors'])

    def test_package_variants_are_not_distinct_keywords(self):
        facts, contract, content = self.arabic_copy()
        content['keywords'] = [facts['name'], core_product_name(facts['name'], facts['package'])]
        self.assertIn('duplicate_keyword_identity', validate(content, contract, facts, 'ar_001')['errors'])

    def test_arabic_model_retries_copied_template_with_natural_wording(self):
        facts, contract, content = self.arabic_copy()
        assistant = self.assistant()
        safe = deterministic(contract, facts, 'ar_001', lambda value: assistant.with_context(lang='ar_001').env._(value))
        def response(value):
            payload = {key: value[key] for key in ('meta_title', 'meta_description', 'short_description', 'sections')}
            payload['keywords'] = value.get('keywords', value.get('search_phrases'))
            return {'choices': [{'message': {'content': json.dumps(payload)}}]}
        with patch.object(type(assistant), '_request', side_effect=[response(safe), response(content)]) as request:
            result = assistant._generate_grounded(facts['name'], 'ar_001', facts, [], contract['prompt_version'], contract=contract)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result['meta_description'], content['meta_description'])
        self.assertEqual(result['search_phrases'], content['keywords'])
        self.assertIn('Do not copy safe_reference wording', request.call_args.kwargs['payload']['messages'][-1]['content'])

    def test_arabic_wording_changes_preserve_english_prompt_and_keywords(self):
        from ..services.seo_templates import contract_prompt
        facts = {'name': 'Example glucose meter 1 BOX', 'package': '1 BOX'}
        contract = self.general._contract('en_US')
        content = deterministic(contract, facts, 'en_US', lambda value: value)
        self.assertEqual(content['search_phrases'], [facts['name'], 'Example glucose meter'])
        self.assertFalse(validate(content, contract, facts, 'en_US')['errors'])
        prompt = contract_prompt(contract, facts, [], 'en_US', {})
        self.assertIn('use safe_reference as the content ceiling', prompt)
        self.assertIn('return at least two distinct grounded keywords', prompt)
        self.assertNotIn('One useful phrase is enough', prompt)
        self.assertNotIn('not wording to copy', prompt)
        content['search_phrases'] = ['Example glucose meter']
        self.assertIn('non_descriptive:keywords', validate(content, contract, facts, 'en_US')['errors'])

    def test_repeated_arabic_copy_remains_reviewable_after_retry(self):
        facts, contract, content = self.arabic_copy()
        assistant = self.assistant()
        safe = deterministic(contract, facts, 'ar_001', lambda value: assistant.with_context(lang='ar_001').env._(value))
        content['meta_description'] = safe['meta_description']
        payload = {key: content[key] for key in ('meta_title', 'meta_description', 'short_description', 'sections', 'keywords')}
        response = {'choices': [{'message': {'content': json.dumps(payload)}}]}
        with patch.object(type(assistant), '_request', return_value=response) as request:
            result = assistant._generate_grounded(facts['name'], 'ar_001', facts, [], contract['prompt_version'], contract=contract)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result['meta_description'], safe['meta_description'])
        self.assertFalse(result['validation']['errors'])
        self.assertEqual(result['validation']['status'], 'review')
        self.assertIn('repetitive_template_copy', result['validation']['warnings'])
        self.assertTrue(result['review_required'])

    def test_malformed_rewrite_retains_only_previous_valid_arabic_copy(self):
        facts, contract, content = self.arabic_copy()
        assistant = self.assistant()
        safe = deterministic(contract, facts, 'ar_001', lambda value: assistant.with_context(lang='ar_001').env._(value))
        content['meta_description'] = safe['meta_description']
        payload = {key: content[key] for key in ('meta_title', 'meta_description', 'short_description', 'sections', 'keywords')}
        responses = [{'choices': [{'message': {'content': text}}]} for text in (json.dumps(payload), '{broken')]
        with patch.object(type(assistant), '_request', side_effect=responses):
            result = assistant._generate_grounded(facts['name'], 'ar_001', facts, [], contract['prompt_version'], contract=contract)
        self.assertEqual(result['meta_description'], safe['meta_description'])
        self.assertFalse(result['validation']['errors'])
        self.assertIn('rewrite_failed:malformed_response', result['validation']['warnings'])
        self.assertTrue(result['review_required'])

    def test_invalid_copy_then_malformed_response_does_not_reuse_old_errors(self):
        facts, contract, content = self.arabic_copy()
        assistant = self.assistant()
        content['meta_title'] += ' يعالج المرض بدقة مضمونة'
        payload = {key: content[key] for key in ('meta_title', 'meta_description', 'short_description', 'sections', 'keywords')}
        responses = [{'choices': [{'message': {'content': text}}]} for text in (json.dumps(payload), '{broken')]
        with patch.object(type(assistant), '_request', side_effect=responses):
            with self.assertRaises(ProviderFailure) as failure:
                assistant._generate_grounded(facts['name'], 'ar_001', facts, [], contract['prompt_version'], contract=contract)
        self.assertEqual(failure.exception.code, 'malformed_response')
        self.assertFalse(failure.exception.validation_report)

    def test_repeated_copy_does_not_override_unsupported_claims(self):
        facts, contract, content = self.arabic_copy()
        assistant = self.assistant()
        safe = deterministic(contract, facts, 'ar_001', lambda value: assistant.with_context(lang='ar_001').env._(value))
        content['meta_description'] = safe['meta_description']
        content['meta_title'] += ' يعالج المرض بدقة مضمونة'
        payload = {key: content[key] for key in ('meta_title', 'meta_description', 'short_description', 'sections', 'keywords')}
        response = {'choices': [{'message': {'content': json.dumps(payload)}}]}
        with patch.object(type(assistant), '_request', return_value=response):
            with self.assertRaises(ProviderFailure) as failure:
                assistant._generate_grounded(facts['name'], 'ar_001', facts, [], contract['prompt_version'], contract=contract)
        self.assertEqual(failure.exception.code, 'template_validation_failed')
        self.assertTrue(failure.exception.validation_report['errors'])
        self.assertNotIn('repetitive_template_copy', failure.exception.validation_report['errors'])

    def test_arabic_review_warnings_survive_pipeline_validation(self):
        facts, contract, content = self.arabic_copy()
        warnings = ['repetitive_template_copy', 'rewrite_failed:malformed_response']
        content['validation'] = {'warnings': warnings}
        job = self.env['ab.product.seo.bulk.optimization'].create({'name': 'Warning validation'})
        item = self.env['ab_seo_work_item'].sudo().create({'job_id': job.id, 'product_id': self.product.id,
            'template_id': self.general.id, 'template_snapshot': {'ar_001': contract},
            'trusted_facts': facts, 'category_context': {'conflicts': []}})
        report = item._validate_template_output(content, 'ar_001')
        self.assertFalse(report['errors'])
        self.assertEqual(report['status'], 'review')
        for warning in warnings:
            self.assertIn(warning, content['validation']['warnings'])

    def test_arabic_duplicate_sections_are_review_warnings(self):
        facts, contract, content = self.arabic_copy()
        content['short_description'] = content['meta_description']
        about = next(section for section in content['sections'] if section['key'] == 'about_product')
        about['content'] = content['meta_description']
        report = validate(content, contract, facts, 'ar_001')
        self.assertFalse(report['errors'])
        self.assertIn('duplicate_copy:about_product', report['warnings'])
        self.assertIn('duplicate_copy:meta_short', report['warnings'])
        self.assertEqual(report['status'], 'review')

    def test_arabic_duplicate_sections_retry_then_keep_valid_draft(self):
        facts, contract, content = self.arabic_copy()
        assistant = self.assistant()
        about = next(section for section in content['sections'] if section['key'] == 'about_product')
        about['content'] = content['meta_description']
        payload = {key: content[key] for key in ('meta_title', 'meta_description', 'short_description', 'sections', 'keywords')}
        response = {'choices': [{'message': {'content': json.dumps(payload)}}]}
        with patch.object(type(assistant), '_request', return_value=response) as request:
            result = assistant._generate_grounded(facts['name'], 'ar_001', facts, [], contract['prompt_version'], contract=contract)
        self.assertEqual(request.call_count, 2)
        self.assertFalse(result['validation']['errors'])
        self.assertIn('duplicate_copy:about_product', result['validation']['warnings'])
        self.assertTrue(result['review_required'])

    def test_english_duplicate_sections_still_fail_validation(self):
        facts = {'name': 'Example glucose meter 1 BOX', 'package': '1 BOX'}
        contract = self.general._contract('en_US')
        content = deterministic(contract, facts, 'en_US', lambda value: value)
        content['short_description'] = content['meta_description']
        about = next(section for section in content['sections'] if section['key'] == 'about_product')
        about['content'] = content['meta_description']
        report = validate(content, contract, facts, 'en_US')
        self.assertIn('duplicate_copy:about_product', report['errors'])
        self.assertIn('duplicate_copy:meta_short', report['errors'])

    def test_arabic_duplicate_sections_do_not_allow_unsupported_claims(self):
        facts, contract, content = self.arabic_copy()
        about = next(section for section in content['sections'] if section['key'] == 'about_product')
        about['content'] = content['meta_description']
        content['meta_title'] += ' يعالج المرض بدقة مضمونة'
        report = validate(content, contract, facts, 'ar_001')
        self.assertTrue(report['errors'])
        self.assertEqual(report['status'], 'rejected')
