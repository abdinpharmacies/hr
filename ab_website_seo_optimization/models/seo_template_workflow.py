from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.providers import digest, normalized
from ..services.seo_templates import deterministic, fingerprints, literal_identity, render_sections, similarity, validate
from .enrichment_provider import MANAGER


class TemplateWorkItem(models.Model):
    _inherit = 'ab_seo_work_item'

    template_id = fields.Many2one('ab_seo_template', readonly=True, ondelete='restrict', index=True)
    template_version = fields.Integer(readonly=True)
    template_snapshot = fields.Json(readonly=True)
    trusted_facts = fields.Json(readonly=True)
    category_context = fields.Json(readonly=True)
    data_confidence = fields.Selection([('high', 'High'), ('medium', 'Medium'), ('low', 'Low'), ('review_required', 'Review Required')], readonly=True)
    validation_status = fields.Selection([('pending', 'Pending'), ('passed', 'Passed'), ('review', 'Review Required'), ('rejected', 'Rejected')], default='pending', readonly=True, index=True)
    validation_report = fields.Json(readonly=True)
    generated_at = fields.Datetime(readonly=True)
    proposal_applied = fields.Boolean(readonly=True)

    def write(self, vals):
        protected = {'template_id', 'template_version', 'template_snapshot', 'trusted_facts', 'category_context',
                     'data_confidence', 'validation_status', 'validation_report', 'generated_at', 'proposal_applied', 'result', 'normalized_input_hash'}
        if not self.env.su and protected.intersection(vals):
            raise AccessError(_('Template generation metadata is maintained by the enrichment pipeline.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any({'template_snapshot', 'trusted_facts', 'validation_status', 'validation_report', 'proposal_applied', 'result', 'normalized_input_hash'}.intersection(vals) for vals in vals_list):
            raise AccessError(_('Template generation metadata is maintained by the enrichment pipeline.'))
        return super().create(vals_list)

    def _identity(self):
        identity = super()._identity()
        product = self.product_id.with_context(lang='en_US')
        identity['name'] = product.name or identity['name']
        identity.pop('strength', None)
        identity.update(literal_identity(identity['name']))
        identity['product_code'] = product.ab_product_id.code or product.default_code or ''
        arabic = product.with_context(lang='ar_001').name
        if arabic and arabic != identity['name']:
            identity['name_ar'] = arabic
        attribute_keys = {'dosage form': 'dosage_form', 'strength': 'strength', 'package size': 'package', 'brand': 'brand'}
        for line in product.attribute_line_ids:
            key = attribute_keys.get(normalized(line.attribute_id.name))
            if key and len(line.value_ids) == 1:
                identity[key] = line.value_ids.name
        explicit = product.ab_enrichment_identity or {}
        for key in ('strength', 'dosage_form', 'package', 'brand'):
            if isinstance(explicit.get(key), str) and explicit[key].strip():
                identity[key] = explicit[key].strip()
        return identity

    def _evidence(self, field, value, provider=None, record=None, matching=None, accepted=False, kind="SOURCE_FACT", lang=None, generation=None):
        if not provider:
            product = self.product_id.ab_product_id
            if field in ('name', 'name_ar', 'strength', 'dosage_form', 'package'):
                record = {'source_id': 'product.template:%s' % self.product_id.id, 'source_version': str(self.product_id.write_date)}
                if field in literal_identity(self.product_id.with_context(lang='en_US').name or ''):
                    matching = {'matched_by': 'catalog_name_literal', 'matched_identifier': self.product_id.with_context(lang='en_US').name, 'match_score': 1.0}
            elif field in ('active_ingredients', 'manufacturer'):
                record = {'source_id': 'ab_product_card:%s' % product.product_card_id.id, 'source_version': str(product.product_card_id.write_date)}
        return super()._evidence(field, value, provider=provider, record=record, matching=matching, accepted=accepted, kind=kind, lang=lang, generation=generation)

    def _select_pipeline(self):
        if self.job_id.pipeline_id or self.product_id.ab_enrichment_domain not in (False, 'auto'):
            return super()._select_pipeline()
        template, context = self.env['ab_seo_template']._select(self.product_id)
        categories = self.product_id.public_categ_ids
        mapped = self.env['ab_seo_pipeline'].search(fields.Domain('category_ids', 'parent_of', categories.ids), limit=1) if categories else self.env['ab_seo_pipeline']
        if mapped and self.product_id.ab_enrichment_domain == 'auto':
            return mapped
        return self.env['ab_seo_pipeline'].search(fields.Domain('domain', '=', template.source_domain), limit=1)

    def _prepare_template(self, facts, provenance, pipeline):
        template, context = self.env['ab_seo_template']._select(self.product_id)
        if self.job_id.template_filter_id and self.job_id.regeneration_mode == 'template':
            template = self.job_id.template_filter_id
        snapshots = {language: template._contract(language) for language in self.job_id._get_selected_lang_codes()}
        conflicts = list(context['conflicts'])
        for evidence in self.fact_ids.filtered(lambda f: f.content_kind in ('SOURCE_FACT', 'UNVERIFIED_TEXT') and f.provider_id and not f.accepted):
            if evidence.match_score >= .95 and evidence.field_name in facts and normalized(evidence.value) != normalized(facts[evidence.field_name]):
                conflicts.append('source_conflict:' + evidence.field_name)
            elif evidence.matched_by == 'conflict':
                conflicts.append('source_identity_conflict:' + (evidence.matched_identifier or evidence.field_name))
        context['conflicts'] = sorted(set(conflicts))
        source_facts = self.fact_ids.filtered(lambda f: f.accepted and f.provider_id)
        critical = [key for key in template.required_facts if not facts.get(key)]
        confidence = 'review_required' if conflicts else 'low' if critical or len([k for k in facts if k not in ('name', 'name_ar', 'product_code')]) < 2 else 'high' if source_facts.filtered(lambda f: f.matched_by in ('gtin', 'source_id')) else 'medium'
        self.sudo().write({'template_id': template.id, 'template_version': template.version, 'template_snapshot': snapshots,
                          'trusted_facts': facts, 'category_context': context, 'data_confidence': confidence})
        return digest([snapshots, context, facts, pipeline.prompt_version])

    def _template_content(self, facts, language):
        localized = self.with_context(lang=language)
        labels = {'Product information for %s.': localized.env._('Product information for %s.'),
                  'Product reference: %s.': localized.env._('Product reference: %s.')}
        return deterministic(self.template_snapshot[language], facts, language, lambda text: labels[text])

    def _validate_template_output(self, content, language):
        contract = self.template_snapshot[language]
        report = validate(content, contract, self.trusted_facts, language)
        report['warnings'] += self.category_context.get('conflicts', [])
        if not report['errors'] and report['warnings']:
            report['status'] = 'review'
        sections = content.get('sections', [])
        titles = {s['key']: s['title'] for s in contract['sections']}
        if report['status'] != 'rejected':
            for section in sections:
                section['title'] = titles[section['key']]
            content['public_description'] = render_sections(sections)
            duplicate = self.env['ab.product.seo.translation']._duplicate_report(content, language, self.product_id, self.template_id, self.trusted_facts)
            report['warnings'] += duplicate
            if duplicate:
                report['status'] = 'review'
        content['validation'] = report
        return report

    def _save_template_metadata(self, seo, outputs):
        structures = {tuple(section['key'] for section in content.get('sections', [])) for content in outputs.values()}
        if len(structures) > 1:
            for content in outputs.values():
                content['validation']['errors'].append('language_section_mismatch')
                content['validation']['status'] = 'rejected'
        reports = {lang: content['validation'] for lang, content in outputs.items() if 'validation' in content}
        status = 'rejected' if any(r['errors'] for r in reports.values()) else 'review' if any(r['warnings'] for r in reports.values()) else 'passed'
        self.sudo().write({'validation_report': reports, 'validation_status': status, 'generated_at': fields.Datetime.now()})
        for translation in seo.translation_ids:
            if translation.lang_code not in outputs or translation.enrichment_item_id != self:
                continue
            content = outputs[translation.lang_code]
            translation.sudo().write({'seo_template_id': self.template_id.id, 'template_version': self.template_version,
                                     'template_snapshot': self.template_snapshot[translation.lang_code], 'trusted_facts': self.trusted_facts,
                                     'structured_sections': content.get('sections', []),
                                     'validation_status': content['validation']['status'], 'validation_report': content['validation'],
                                     'generation_provider_id': content.get('provider_id') or False,
                                     'generation_model': content.get('model') or 'deterministic', 'generated_at': self.generated_at})

    def action_apply_proposal(self):
        self.job_id._require_manager()
        for item in self:
            if item.proposal_applied or not item.result or not item.seo_id or not item.template_snapshot:
                raise UserError(_('There is no unapplied template proposal.'))
            if not item.try_lock_for_update() or not item.seo_id.try_lock_for_update():
                raise UserError(_('This SEO proposal is being processed. Try again shortly.'))
            for lang, content in item.result.items():
                report = item._validate_template_output(content, lang)
                if report['errors']:
                    raise ValidationError(_('Rejected content cannot replace an SEO draft. Correct the facts or template and regenerate.'))
            item.seo_id.write({'state': 'generated'})
            item._save_outputs(item.seo_id, item.result)
            item.sudo().write({'proposal_applied': True})
        return True


class TemplateTranslation(models.Model):
    _inherit = 'ab.product.seo.translation'

    seo_template_id = fields.Many2one('ab_seo_template', readonly=True, ondelete='restrict', index=True)
    template_version = fields.Integer(readonly=True, index=True)
    template_snapshot = fields.Json(readonly=True)
    trusted_facts = fields.Json(readonly=True)
    structured_sections = fields.Json(readonly=True)
    data_confidence = fields.Selection(related='enrichment_item_id.data_confidence')
    validation_status = fields.Selection([('pending', 'Pending'), ('passed', 'Passed'), ('review', 'Review Required'), ('rejected', 'Rejected')], default='pending', readonly=True, index=True)
    validation_report = fields.Json(readonly=True)
    generation_provider_id = fields.Many2one('ab.seo.assistant', readonly=True, ondelete='restrict')
    generation_model = fields.Char(readonly=True)
    generated_at = fields.Datetime(readonly=True)
    template_outdated = fields.Boolean(compute='_compute_template_outdated', store=True, index=True)
    title_hash = fields.Char(compute='_compute_fingerprints', store=True, index=True)
    meta_hash = fields.Char(compute='_compute_fingerprints', store=True, index=True)
    body_hash = fields.Char(compute='_compute_fingerprints', store=True, index=True)
    boilerplate_hash = fields.Char(compute='_compute_fingerprints', store=True, index=True)
    similarity_0 = fields.Char(compute='_compute_fingerprints', store=True, index=True)
    similarity_1 = fields.Char(compute='_compute_fingerprints', store=True, index=True)
    similarity_2 = fields.Char(compute='_compute_fingerprints', store=True, index=True)
    similarity_3 = fields.Char(compute='_compute_fingerprints', store=True, index=True)

    @api.depends('seo_template_id.version', 'template_version')
    def _compute_template_outdated(self):
        for row in self:
            row.template_outdated = bool(row.seo_template_id and row.template_version != row.seo_template_id.version)

    @api.depends('meta_title', 'meta_description', 'public_description', 'trusted_facts')
    def _compute_fingerprints(self):
        for row in self:
            for key, value in fingerprints(row._validation_content(), row.trusted_facts or {}).items():
                row[key] = value

    def _validation_content(self):
        return {'meta_title': self.meta_title or '', 'meta_description': self.meta_description or '',
                'short_description': self.short_description or '', 'public_description': self.public_description or '',
                'sections': self.structured_sections or [], 'search_phrases': self.search_phrases or [],
                'content_kind': 'GENERATED_TEXT' if self.generation_model and self.generation_model != 'deterministic' else 'SOURCE_FACT'}

    @api.model
    def _duplicate_report(self, content, language, product, template, facts):
        hashes = fingerprints(content, facts)
        base = fields.Domain('lang_code', '=', language) & fields.Domain('seo_id.product_template_id', '!=', product.id)
        duplicates = []
        for key in ('title_hash', 'meta_hash', 'body_hash'):
            if self.search_count(base & fields.Domain(key, '=', hashes[key]), limit=1):
                duplicates.append('duplicate:' + key)
        candidates = self.search(base & fields.Domain.OR([fields.Domain('similarity_%s' % i, '=', hashes['similarity_%s' % i]) for i in range(4) if hashes['similarity_%s' % i]]), limit=101)
        threshold = template.validation_rules['similarity_threshold']
        if any(similarity(content.get('public_description'), row.public_description) >= threshold for row in candidates[:100]):
            duplicates.append('similar_description')
        if len(candidates) > 100:
            duplicates.append('similarity_candidate_limit')
        if template and self.search_count(base & fields.Domain('seo_template_id', '=', template.id) & fields.Domain('boilerplate_hash', '=', hashes['boilerplate_hash']), limit=4) >= 3:
            if len([k for k in facts if k not in ('name', 'name_ar', 'product_code')]) < 2:
                duplicates.append('template_boilerplate')
        native = self.env['product.template'].with_context(lang=language)
        scope = fields.Domain('id', '!=', product.id) & fields.Domain('website_id', 'in', [False, product.website_id.id]) & fields.Domain('company_id', 'in', [False, product.company_id.id or self.env.company.id])
        for key, value in [('website_meta_title', content.get('meta_title')), ('website_meta_description', content.get('meta_description'))]:
            if value and native.search_count(scope & fields.Domain(key, '=', value), limit=1):
                duplicates.append('native_duplicate:' + key)
        return duplicates

    def _validate_current(self):
        self.ensure_one()
        content = self._validation_content()
        report = validate(content, self.template_snapshot, self.trusted_facts, self.lang_code)
        from ..services.seo_templates import plain
        if normalized(plain(self.public_description)) != normalized(plain(render_sections(self.structured_sections or []))):
            report['errors'].append('section_body_changed')
        report['warnings'] += self._duplicate_report(content, self.lang_code, self.seo_id.product_template_id, self.seo_template_id, self.trusted_facts)
        report['warnings'] += (self.enrichment_item_id.category_context or {}).get('conflicts', [])
        report['status'] = 'rejected' if report['errors'] else 'review' if report['warnings'] else 'passed'
        self.sudo().write({'validation_report': report, 'validation_status': report['status']})
        return report

    def action_review_evidence(self):
        for row in self.filtered('seo_template_id'):
            report = row._validate_current()
            if report['errors']:
                raise ValidationError(_('Resolve validation errors before confirming evidence: %s') % ', '.join(report['errors']))
        return super().action_review_evidence()

    @api.model_create_multi
    def create(self, vals_list):
        protected = {'seo_template_id', 'template_version', 'template_snapshot', 'trusted_facts', 'structured_sections',
                     'validation_status', 'validation_report', 'generation_provider_id', 'generation_model', 'generated_at'}
        if not self.env.su and any(protected.intersection(vals) for vals in vals_list):
            raise AccessError(_('Template generation metadata is maintained by the enrichment pipeline.'))
        return super().create(vals_list)

    def write(self, vals):
        protected = {'seo_template_id', 'template_version', 'template_snapshot', 'trusted_facts', 'structured_sections', 'validation_status', 'validation_report', 'generation_provider_id', 'generation_model', 'generated_at'}
        if not self.env.su and protected.intersection(vals):
            raise AccessError(_('Template generation metadata is maintained by the enrichment pipeline.'))
        if self.filtered('seo_template_id') and set(vals).intersection({'meta_title', 'meta_description', 'short_description', 'public_description', 'keyword_text', 'search_phrases'}):
            vals = dict(vals, validation_status='pending')
        return super().write(vals)

    def _create_version(self):
        if self.seo_template_id and self._validate_current()['errors']:
            raise ValidationError(_('Rejected content cannot be approved or published.'))
        version = super()._create_version()
        if self.seo_template_id:
            version.sudo().write({'seo_template_snapshot': {'template_id': self.seo_template_id.id, 'version': self.template_version,
                'contract': self.template_snapshot, 'facts': self.trusted_facts, 'sections': self.structured_sections,
                'validation': self.validation_report, 'confidence': self.data_confidence, 'provider_id': self.generation_provider_id.id, 'model': self.generation_model,
                'generated_at': str(self.generated_at)}})
        return version


class TemplateVersion(models.Model):
    _inherit = 'ab.product.seo.version'

    seo_template_snapshot = fields.Json(readonly=True)

    def write(self, vals):
        if 'seo_template_snapshot' in vals and (not self.env.su or self.filtered('seo_template_snapshot')):
            raise UserError(_('SEO versions are immutable. Create a new version instead.'))
        return super().write(vals)


class TemplateSeo(models.Model):
    _inherit = 'ab.product.seo'

    template_outdated = fields.Boolean(compute='_compute_template_outdated', store=True, index=True)
    template_generation_mode = fields.Selection([('deterministic', 'Deterministic'), ('ai', 'AI Wording')], default='deterministic', required=True)

    @api.depends('translation_ids.template_outdated')
    def _compute_template_outdated(self):
        for seo in self:
            seo.template_outdated = any(seo.translation_ids.mapped('template_outdated'))

    def _publish_versions(self, force=False, publish_description=True):
        for seo in self:
            for translation in seo.translation_ids.filtered('seo_template_id'):
                if translation._validate_current()['errors'] or translation.review_required:
                    raise ValidationError(_('Rejected or unreviewed template content cannot be published.'))
        return super()._publish_versions(force, publish_description)


class TemplateBulk(models.Model):
    _inherit = 'ab.product.seo.bulk.optimization'

    product_selection_ids = fields.Many2many('product.template', string='Selected Products')
    category_filter_id = fields.Many2one('product.public.category', string='Selected Category')
    template_filter_id = fields.Many2one('ab_seo_template', string='Selected Template', ondelete='restrict')
    regeneration_mode = fields.Selection([('missing', 'Generate Missing'), ('selected', 'Regenerate Selected'), ('failed', 'Regenerate Failed'), ('outdated', 'Regenerate Outdated Templates'), ('template', 'Regenerate Using Selected Template')], default='missing', required=True)
    generation_mode = fields.Selection([('deterministic', 'Deterministic'), ('ai', 'AI Wording')], default='deterministic', required=True)
    dry_run = fields.Boolean(default=False)
    dry_run_report = fields.Json(readonly=True)
    pilot_job_id = fields.Many2one('ab.product.seo.bulk.optimization', string='Validated Pilot', ondelete='restrict')
    pilot_validated_by = fields.Many2one('res.users', readonly=True)
    pilot_validated_at = fields.Datetime(readonly=True)
    pilot_review_notes = fields.Text()
    pilot_configuration_hash = fields.Char(readonly=True)

    def _template_configuration_hash(self):
        return digest([t._contract(lang) for t in self.env['ab_seo_template'].search([]) for lang in self._get_selected_lang_codes()])

    def _check_pilot_gate(self):
        if self.batch_limit <= 100:
            return
        pilot = self.pilot_job_id
        required_templates = self.template_filter_id or self.env['ab_seo_template'].search([])
        covered = self.env['ab_seo_work_item'].search(fields.Domain('job_id', '=', pilot.id) & fields.Domain('validation_status', 'in', ('passed', 'review')), limit=101).template_id if pilot.pilot_validated_at else self.env['ab_seo_template']
        if not (pilot.pilot_validated_at and pilot.company_id == self.company_id and pilot.generation_mode == self.generation_mode
                and pilot.lang_mode == self.lang_mode and pilot.pilot_configuration_hash == self._template_configuration_hash()
                and not (required_templates - covered)):
            raise UserError(_('Validate a representative pilot of at most 100 products before a larger run.'))

    def _optimize_template(self, template):
        seo = self.env['ab.product.seo'].search(fields.Domain('product_template_id', '=', template.id), limit=1)
        if seo.state in ('under_review', 'approved', 'published') or seo.translation_ids.filtered('seo_template_id'):
            raise UserError(_('Use template regeneration proposals for reviewed product SEO.'))
        return super()._optimize_template(template)

    def _enrichment_domain(self):
        domain = super()._enrichment_domain()
        if self.product_selection_ids:
            domain &= fields.Domain('id', 'in', self.product_selection_ids.ids)
        if self.category_filter_id:
            domain &= fields.Domain('public_categ_ids', 'child_of', self.category_filter_id.id)
        return domain

    def _template_language_missing(self, product, language):
        if self._has_complete_native_seo(product, language):
            return False
        translation = self.env['ab.product.seo.translation'].search(fields.Domain('seo_id.product_template_id', '=', product.id) & fields.Domain('lang_code', '=', language), limit=1)
        return not (translation.meta_title and translation.meta_description and translation.keyword_text and (not self.publish_description or translation.public_description))

    def _template_should_skip(self, product):
        seo = self.env['ab.product.seo'].search(fields.Domain('product_template_id', '=', product.id), limit=1)
        if self.regeneration_mode == 'missing':
            if seo and seo.state in ('approved', 'published', 'under_review'):
                return 'existing_seo_preserved'
            if not any(self._template_language_missing(product, lang) for lang in self._get_selected_lang_codes()):
                return 'seo_complete'
        if self.regeneration_mode == 'outdated' and not seo.template_outdated:
            return 'template_current'
        if self.regeneration_mode == 'failed' and not self.env['ab_seo_work_item'].search_count(fields.Domain('product_id', '=', product.id) & fields.Domain('state', '=', 'failed'), limit=1):
            return 'no_failed_generation'
        if self.template_filter_id:
            selected, _context = self.env['ab_seo_template']._select(product)
            if selected != self.template_filter_id:
                return 'different_template'
        return False

    def _run_bulk_optimization_chunk(self):
        if self.enrichment_enabled:
            self._check_pilot_gate()
        return super()._run_bulk_optimization_chunk()

    def _enqueue_bulk_optimization(self):
        if self.enrichment_enabled:
            self._check_pilot_gate()
            if self.regeneration_mode == 'template' and not self.template_filter_id:
                raise UserError(_('Select a template for this regeneration mode.'))
            if self.dry_run:
                return self.action_template_dry_run()
        return super()._enqueue_bulk_optimization()

    def action_template_dry_run(self):
        self._require_manager()
        self.ensure_one()
        products = self.env['product.template'].search(self._enrichment_domain(), order='id', limit=min(self.batch_limit, 100))
        rows = []
        source = self.env['ab_seo_source_record']
        for product in products:
            item = self.env['ab_seo_work_item'].new({'product_id': product.id, 'job_id': self.id})
            identity = item._identity()
            template, context = self.env['ab_seo_template']._select(product)
            matches = []
            for provider in item._select_pipeline()._providers():
                if provider._allowed_for_commercial():
                    from ..services.providers import match
                    matches += [{'provider': provider.provider, **match(identity, row)} for row in source._lookup(provider, identity)]
            missing = [k for k in template.required_facts if not identity.get(k)]
            skip = self._template_should_skip(product)
            rows.append({'product_id': product.id, 'name': identity['name'], 'template': template.code, 'version': template.version,
                         'classification': context, 'source_matches': matches, 'missing_facts': missing,
                         'confidence': 'review_required' if context['conflicts'] else 'low' if missing else 'medium',
                         'would_generate': not bool(skip), 'would_skip': skip or False, 'would_require_review': not bool(skip),
                         'sources_not_checked': 'remote_sources_not_called'})
        category_coverage = []
        for category, count in self.env['product.template']._read_group(self._enrichment_domain(), ['public_categ_ids'], ['__count']):
            probe = self.env['product.template'].new({'name': '', 'public_categ_ids': [(6, 0, category.ids)], 'ab_enrichment_domain': 'auto'})
            selected, classification = self.env['ab_seo_template']._select(probe)
            category_coverage.append({'category_id': category.id, 'category': category.display_name, 'assignments': count,
                                      'template': selected.code, 'unmapped': classification['method'] == 'general_fallback'})
        self.dry_run_report = {'category_coverage': category_coverage, 'eligible_products': self.env['product.template'].search_count(self._enrichment_domain()),
                               'run_limit': self.batch_limit, 'maximum_records_to_generate': min(self.batch_limit, self.env['product.template'].search_count(self._enrichment_domain())) * len(self._get_selected_lang_codes()), 'products_analyzed': len(rows), 'sample_limit': 100,
                               'would_generate_sample': sum(r['would_generate'] for r in rows),
                               'unmapped_sample': sum(r['classification']['method'] == 'general_fallback' for r in rows),
                               'without_source_matches_sample': sum(not r['source_matches'] for r in rows), 'products': rows}
        return True

    def action_validate_pilot(self):
        self._require_manager()
        for job in self:
            items = self.env['ab_seo_work_item'].search(fields.Domain('job_id', '=', job.id), limit=101)
            if job.state != 'done' or not 1 <= len(items) <= 100 or not job.pilot_review_notes or items.filtered(lambda i: i.validation_status in ('pending', 'rejected') or i.state in ('waiting', 'failed') or (i.last_error == 'existing_review_preserved' and not i.proposal_applied)):
                raise ValidationError(_('Complete a pilot of 1–100 products, resolve rejected items and record the pilot review.'))
            if items.seo_id.translation_ids.filtered(lambda t: t.enrichment_item_id in items and t.review_required):
                raise ValidationError(_('Review every pilot translation before validating the pilot.'))
            job.sudo().write({'pilot_validated_by': self.env.user.id, 'pilot_validated_at': fields.Datetime.now(), 'pilot_configuration_hash': job._template_configuration_hash()})
        return True

    def write(self, vals):
        if not self.env.su and {'pilot_validated_by', 'pilot_validated_at', 'pilot_configuration_hash'}.intersection(vals):
            raise AccessError(_('Use the pilot validation action.'))
        settings = {'product_selection_ids', 'category_filter_id', 'template_filter_id', 'regeneration_mode', 'generation_mode', 'batch_limit', 'pipeline_id', 'lang_mode', 'company_id', 'website_id'}
        if settings.intersection(vals) and self.filtered(lambda j: j.state != 'draft'):
            raise UserError(_('Create a new run to change the scope or generation settings of a started job.'))
        return super().write(vals)
