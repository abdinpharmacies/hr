from copy import deepcopy

from odoo import _, api, fields, models
from .homepage_content import default_home_blocks, homepage_sections


class EditorHomepage(models.Model):
    _inherit = 'ab_ecommerce_editor_document'

    @api.model
    def open_homepage(self, website_id):
        self.check_access('create')
        from .editor_document import validate_website
        website = self.env['website'].browse(website_id).exists()
        website.ensure_one()
        validate_website(website)
        document = self.with_context(active_test=False).search(fields.Domain([
            ('website_id', '=', website.id), ('kind', '=', 'homepage'), ('slug', '=', 'home'),
        ]), limit=1)
        if not document:
            document = self.create({
                'name': _('Homepage'), 'title_en': 'Homepage', 'kind': 'homepage',
                'website_id': website.id, 'slug': 'home',
                'blocks_en': default_home_blocks(), 'blocks_ar': default_home_blocks(),
            })
        return document.id

    @api.model
    def homepage_palette(self):
        self.check_access('read')
        sections = homepage_sections()
        for section in sections:
            label = section['label']
            section['label'] = self.env._(label)
            for field in section['fields']:
                label = field['label']
                field['label'] = self.env._(label)
        return sections


class EditorWebsite(models.Model):
    _inherit = 'website'

    def _ab_editor_home_payload(self):
        self.ensure_one()
        document = self.env['ab_ecommerce_editor_document'].sudo().search(fields.Domain([
            ('website_id', '=', self.id), ('company_id', '=', self.company_id.id),
            ('kind', '=', 'homepage'), ('slug', '=', 'home'),
            ('active', '=', True), ('published_revision_id', '!=', False),
        ]), limit=1)
        if not document:
            return {}
        return deepcopy(document.published_revision_id.payload)

    def _ab_editor_home_tokens(self):
        payload = self._ab_editor_home_payload()
        return {**payload.get('design_tokens', {}), **payload.get('platform_overrides', {}).get('web', {})}

    def _ab_editor_home_blocks(self):
        payload = self._ab_editor_home_payload()
        if not payload:
            return default_home_blocks()
        language = 'ar_001' if (self.env.lang or '').startswith('ar') else 'en_US'
        return payload['blocks'][language]

    def _ab_editor_block_style(self, style):
        from ..controllers.editor_content import block_style
        return block_style(style)
