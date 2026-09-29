import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.providers import digest, normalized
from ..services.seo_templates import FACT_KEYS
from .enrichment_provider import MANAGER


class SeoTemplate(models.Model):
    _name = 'ab_seo_template'
    _description = 'SEO Template'
    _order = 'priority desc, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    version = fields.Integer(default=1, required=True, readonly=True)
    product_type = fields.Char(required=True, index=True)
    source_domain = fields.Selection([('drug', 'Drug'), ('supplement', 'Supplement'), ('cosmetic', 'Cosmetic'), ('food', 'Food'), ('general', 'General')], default='general', required=True)
    priority = fields.Integer(default=10)
    category_ids = fields.Many2many('product.public.category', string='Applicable Categories')
    category_names = fields.Json(default=list, string='Semantic Category Names')
    name_signals = fields.Json(default=list, string='Product Name Signals')
    section_ids = fields.One2many('ab_seo_template_section', 'template_id', string='Sections')
    required_facts = fields.Json(default=lambda self: ['name', 'product_code'])
    optional_facts = fields.Json(default=lambda self: ['brand', 'manufacturer', 'package'])
    validation_rules = fields.Json(default=lambda self: {'title_min': 15, 'title_max': 70, 'meta_min': 80, 'meta_max': 170, 'keyword_max': 5, 'similarity_threshold': .85})
    generation_instructions = fields.Text(translate=True)
    language_rules = fields.Text(translate=True, default='Preserve product names, scientific names and identifiers. Use the same facts and section order in Arabic and English.')
    rationale = fields.Text(translate=True)
    prompt_version = fields.Char(default='template_seo_v1', required=True)

    _unique_code = models.Constraint('UNIQUE(code)', 'Template codes must be unique.')

    @api.constrains('code', 'product_type', 'required_facts', 'optional_facts', 'validation_rules', 'category_names', 'name_signals')
    def _check_configuration(self):
        for template in self:
            if not re.fullmatch('[a-z][a-z0-9_]*', template.code or ''):
                raise ValidationError(_('Use a lowercase template code with underscores.'))
            for values in (template.required_facts or [], template.optional_facts or []):
                if not isinstance(values, list) or any(not isinstance(k, str) or k not in FACT_KEYS for k in values):
                    raise ValidationError(_('Template fact keys must use the supported normalized facts.'))
            for values in (template.category_names or [], template.name_signals or []):
                if not isinstance(values, list) or any(not isinstance(k, str) or not k.strip() for k in values):
                    raise ValidationError(_('Category names and product signals must be lists of nonempty text.'))
            rules = template.validation_rules
            if not isinstance(rules, dict) or any(not isinstance(rules.get(k), (float, int)) for k in ('title_min', 'title_max', 'meta_min', 'meta_max', 'keyword_max', 'similarity_threshold')):
                raise ValidationError(_('Complete all numeric SEO validation rules.'))
            if not (1 <= rules['title_min'] <= rules['title_max'] <= 255 and 1 <= rules['meta_min'] <= rules['meta_max'] <= 500 and 1 <= rules['keyword_max'] <= 10 and .5 <= rules['similarity_threshold'] <= 1):
                raise ValidationError(_('SEO validation rule limits are invalid.'))

    def write(self, vals):
        if 'version' in vals and not self.env.su:
            raise AccessError(_('Template versions are maintained automatically.'))
        if set(vals) - {'version', 'active'}:
            for record in self:
                super(SeoTemplate, record).write(dict(vals, version=record.version + 1))
            return True
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Archive SEO templates instead of deleting them.'))

    def _contract(self, language='en_US'):
        self.ensure_one()
        localized = self.with_context(lang=language)
        return {'id': self.id, 'code': self.code, 'version': self.version, 'product_type': self.product_type,
                'source_domain': self.source_domain, 'prompt_version': self.prompt_version,
                'required_facts': self.required_facts, 'optional_facts': self.optional_facts,
                'rules': self.validation_rules, 'instructions': localized.generation_instructions,
                'language_rules': localized.language_rules,
                'sections': [{'key': s.key, 'title': s.title, 'policy': s.policy, 'fact_keys': s.fact_keys or []}
                             for s in localized.section_ids.sorted(lambda s: (s.sequence, s.id))]}

    @api.model
    def _select(self, product):
        templates = self.search([])
        if not templates:
            raise ValidationError(_('Configure an active SEO template before generation.'))
        categories = product.public_categ_ids.with_context(lang='en_US')
        ancestry = {}
        for category in categories:
            node = category
            distance = 0
            visited = set()
            while node and node.id not in visited:
                visited.add(node.id)
                if node.id not in ancestry or distance < ancestry[node.id][0]:
                    ancestry[node.id] = (distance, node)
                node, distance = node.parent_id, distance + 1
        candidates = []
        explicit = product.ab_seo_template_id
        if explicit and explicit.active:
            candidates = [(0, 0, -explicit.priority, explicit.id, explicit, 'explicit_template')]
        elif product.ab_enrichment_domain and product.ab_enrichment_domain != 'auto':
            preferred = {'drug': 'medicine', 'cosmetic': 'beauty', 'supplement': 'supplement', 'general': 'general'}.get(product.ab_enrichment_domain)
            candidates = [(1, 0, -t.priority, t.id, t, 'explicit_product_type') for t in templates if t.code == preferred]
            if not candidates:
                candidates = [(1, 0, -t.priority, t.id, t, 'explicit_product_type_unmapped') for t in templates if t.code == 'general']
        if not candidates:
            for template in templates:
                for category in template.category_ids:
                    if category.id in ancestry:
                        distance = ancestry[category.id][0]
                        candidates.append((2, distance, -template.priority, template.id, template, 'category_mapping'))
        if not candidates:
            for template in templates:
                names = {normalized(n) for n in template.category_names or []}
                for distance, category in ancestry.values():
                    parts = [normalized(n) for n in category.name.split('/')]
                    if names.intersection(parts):
                        candidates.append((3, distance, -template.priority, template.id, template, 'semantic_category'))
        attribute_values = product.with_context(lang='en_US').attribute_line_ids.value_ids.mapped('name')
        name = ' ' + normalized(' '.join([product.with_context(lang='en_US').name or ''] + attribute_values)) + ' '
        signals = templates.filtered(lambda t: any(' ' + normalized(s) + ' ' in name for s in t.name_signals or []))
        if not candidates:
            if product.ab_product_id.is_medicine:
                candidates = [(4, 0, -t.priority, t.id, t, 'catalog_medicine_flag') for t in templates if t.code == 'medicine']
            elif signals:
                candidates = [(5, 0, -t.priority, t.id, t, 'product_attributes' if attribute_values else 'product_name_signal') for t in signals]
        if not candidates:
            candidates = [(6, 0, -t.priority, t.id, t, 'general_fallback') for t in templates if t.code == 'general']
        if not candidates:
            raise ValidationError(_('An active General Product SEO template is required.'))
        candidates.sort(key=lambda row: row[:4])
        winner = candidates[0]
        conflicts = ['explicit_product_type_unmapped'] if winner[5] == 'explicit_product_type_unmapped' else []
        if len({row[4].code for row in candidates if row[:2] == winner[:2]}) > 1:
            conflicts.append('ambiguous_categories')
        if winner[5] != 'explicit_template':
            if signals and winner[4] not in signals and winner[4].code != 'general':
                conflicts.append('category_product_signal_conflict')
            if winner[4].code == 'medicine' and not product.ab_product_id.is_medicine:
                conflicts.append('medicine_category_flag_conflict')
            if product.ab_product_id.is_medicine and winner[4].source_domain not in ('drug', 'supplement'):
                conflicts.append('medicine_flag_category_conflict')
        return winner[4], {'method': winner[5], 'conflicts': conflicts,
                           'categories': [{'id': c.id, 'name': c.name, 'path': c.parent_path} for c in categories],
                           'signals': signals.mapped('code')}


class SeoTemplateSection(models.Model):
    _name = 'ab_seo_template_section'
    _description = 'SEO Template Section'
    _order = 'sequence, id'

    template_id = fields.Many2one('ab_seo_template', required=True, ondelete='restrict', index=True)
    sequence = fields.Integer(default=10)
    key = fields.Char(required=True)
    title = fields.Char(required=True, translate=True)
    policy = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('forbidden', 'Forbidden')], default='optional', required=True)
    fact_keys = fields.Json(default=list)

    _unique_key = models.Constraint('UNIQUE(template_id, key)', 'Section keys must be unique within a template.')

    @api.constrains('key', 'fact_keys')
    def _check_section(self):
        for section in self:
            if section.policy == 'forbidden' and not section.fact_keys:
                continue
            if not re.fullmatch('[a-z][a-z0-9_]*', section.key or '') or not isinstance(section.fact_keys, list) or any(k not in FACT_KEYS for k in section.fact_keys if isinstance(k, str)) or any(not isinstance(k, str) for k in section.fact_keys):
                raise ValidationError(_('Use a valid section key and supported fact keys.'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.template_id.sudo()._bump_version()
        return records

    def write(self, vals):
        templates = self.template_id
        result = super().write(vals)
        (templates | self.template_id).sudo()._bump_version()
        return result

    def unlink(self):
        templates = self.template_id
        result = super().unlink()
        templates.sudo()._bump_version()
        return result


class SeoTemplateVersioning(models.Model):
    _inherit = 'ab_seo_template'

    def _bump_version(self):
        if not self.env.context.get('install_mode'):
            for template in self:
                template.write({'version': template.version + 1})


class SeoTemplateProduct(models.Model):
    _inherit = 'product.template'

    ab_seo_template_id = fields.Many2one('ab_seo_template', string='Explicit SEO Template', ondelete='restrict', groups=MANAGER)
