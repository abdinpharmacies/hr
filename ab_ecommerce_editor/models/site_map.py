import hashlib
from urllib.parse import quote, urlsplit

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .editor_document import validate_website


class EditorSiteMap(models.Model):
    _inherit = 'ab_ecommerce_editor_document'

    native_path = fields.Char(string='Original page address', copy=False, readonly=True)
    _unique_native_path = models.Constraint('UNIQUE(website_id, native_path)', 'This page already has an editor document.')

    @api.constrains('native_path', 'website_id', 'kind', 'blocks_en', 'blocks_ar')
    def _check_native_page(self):
        for document in self.filtered('native_path'):
            if document.kind != 'page' or document.native_path not in {
                node['url'] for node in document.get_site_map(document.website_id.id, include_documents=False)['nodes']
            } or document.native_path == '/':
                raise ValidationError(_('Choose an existing storefront page.'))
            for blocks in (document.blocks_en, document.blocks_ar):
                if sum(block['type'] == 'storefront_page' for block in (blocks or [])) != 1:
                    raise ValidationError(_('Keep the original storefront section in this page.'))

    def write(self, values):
        if 'native_path' in values and any(values['native_path'] != doc.native_path for doc in self):
            raise ValidationError(_('The original page address cannot be changed.'))
        return super().write(values)

    @api.model
    def open_site_page(self, website_id, path):
        self.check_access('create')
        catalog = self.get_site_map(website_id)
        node = next((node for node in catalog['nodes'] if node['url'] == path), None)
        if not node:
            raise ValidationError(_('Choose an existing storefront page.'))
        if path == '/':
            return self.open_homepage(website_id)
        if node['document_id']:
            return node['document_id']
        slug = 'site-' + hashlib.sha256(path.encode()).hexdigest()[:24]
        existing = self.with_context(active_test=False).search(fields.Domain([
            ('website_id', '=', website_id), ('kind', '=', 'page'), ('slug', '=', slug),
        ]), limit=1)
        if existing:
            return existing.id
        english = next(item['title'] for item in self.with_context(lang='en_US').get_site_map(website_id, False)['nodes'] if item['url'] == path)
        arabic = next(item['title'] for item in self.with_context(lang='ar_001').get_site_map(website_id, False)['nodes'] if item['url'] == path)
        block = {'id': 'storefront-original', 'type': 'storefront_page', 'content': {}}
        return self.create({
            'name': english, 'title_en': english, 'title_ar': arabic, 'website_id': website_id,
            'slug': slug, 'kind': 'page', 'native_path': path,
            'blocks_en': [block], 'blocks_ar': [block],
        }).id

    @api.model
    def get_site_map(self, website_id, include_documents=True):
        self.check_access('read')
        website = self.env['website'].browse(website_id).exists()
        website.ensure_one()
        validate_website(website)
        nodes = {}

        def add(url, title, document_id=False, kind='website'):
            parts = urlsplit(url)
            if parts.scheme or parts.netloc or not url.startswith('/') or '\\' in url:
                return
            path = parts.path.rstrip('/') or '/'
            nodes[path] = {
                'url': path, 'title': title, 'document_id': document_id, 'kind': kind,
                'preview_url': f'/editor/site-map/preview/{website.id}?path={quote(path, safe="")}',
            }

        for url, title in (
            ('/', _('Homepage')), ('/shop', _('Products')),
            ('/shop/offers', _('Offers')), ('/shop/category', _('Categories')),
            ('/prescription-order', _('Prescription order')), ('/contactus', _('Contact us')),
            ('/about-us', _('About us')), ('/branches', _('Branches')),
            ('/return-policy', _('Return policy')),
            ('/terms-and-conditions', _('Terms and conditions')),
            ('/business-partnerships', _('Business partnerships')),
            ('/track-order', _('Track order')), ('/editor/blog', _('Articles')),
        ):
            add(url, title, kind='homepage' if url == '/' else 'website')
        pages = self.env['website.page']
        if pages.has_access('read'):
            for page in pages.search(fields.Domain('website_id', 'in', [False, website.id]), order='website_id desc, id'):
                add(page.url, page.name)
        documents = self.search(fields.Domain('website_id', '=', website.id), order='kind, name, id') if include_documents else self.browse()
        arabic = (self.env.lang or '').startswith('ar')
        for document in documents:
            url = document.native_path or ('/' if document.kind == 'homepage' else f'/editor/{document.kind}/{document.slug}')
            add(url, (document.title_ar if arabic else document.title_en) or document.name, document.id, document.kind)
        nodes['/']['kind'] = 'homepage'
        return {'nodes': list(nodes.values()), 'website_id': website.id}
