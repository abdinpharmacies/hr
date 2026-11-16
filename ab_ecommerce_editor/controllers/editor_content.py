import hashlib
from copy import deepcopy
from urllib.parse import urlencode

from odoo import fields, http
from odoo.http import request


FONT_FAMILIES = {
    'system': 'system-ui, sans-serif',
    'arabic': 'Abdin Editor Arabic, sans-serif',
    'monospace': 'monospace',
    'georgia': 'Georgia, serif',
}


def block_style(style):
    declarations = []
    for key, css in (('color', 'color'), ('background', 'background-color')):
        if key in style:
            declarations.append(f'{css}:{style[key]}')
    if 'weight' in style:
        declarations.append(f"font-weight:{style['weight']};--ae-font-weight:{style['weight']}")
    if style.get('italic'):
        declarations.append('font-style:italic')
    if 'border_color' in style:
        declarations.append(f"border-color:{style['border_color']};border-style:solid")
    if 'border_width' in style:
        declarations.append(f"border-width:{style['border_width']}px;border-style:solid")
    if 'mobile_size' in style:
        declarations.append(f"--ae-mobile-size:{style['mobile_size']}px")
    if 'font' in style:
        declarations.append(f"font-family:{FONT_FAMILIES[style['font']]}")
    for key, css in (('size', 'font-size'), ('padding', 'padding'), ('radius', 'border-radius')):
        if key in style:
            declarations.append(f"{css}:{style[key]}px")
    if 'align' in style:
        declarations.append(f"text-align:{style['align']}")
    return ';'.join(declarations)


class EditorContent(http.Controller):
    @http.route('/editor/site-map/preview/<int:website_id>', type='http', auth='user', website=True, methods=['GET'], sitemap=False)
    def site_map_preview(self, website_id, path='/', **kwargs):
        catalog = request.env['ab_ecommerce_editor_document'].get_site_map(website_id)
        node = next((node for node in catalog['nodes'] if node['url'] == path), None)
        if not node or request.website.id != website_id:
            return request.not_found()
        target = f"/editor/preview/{node['document_id']}" if node['document_id'] else node['url']
        return request.redirect(target, code=303)

    def _document(self, kind, slug):
        return request.env['ab_ecommerce_editor_document'].sudo().search(fields.Domain([
            ('website_id', '=', request.website.id),
            ('kind', '=', kind), ('slug', '=', slug), ('native_path', '=', False),
            ('active', '=', True), ('published_revision_id', '!=', False),
        ]), limit=1)

    def _localized(self, document, platform='web', capabilities=None, snapshot=None, language=None, revision=None):
        revision = revision if revision is not None else document.published_revision_id
        payload = deepcopy(snapshot if snapshot is not None else revision.payload)
        language = language or ('ar_001' if (request.env.lang or '').startswith('ar') else 'en_US')
        blocks = [block for block in payload['blocks'][language] if block.get('active', True)]
        unsupported = []
        if capabilities is not None:
            for block in blocks:
                if block['type'] not in capabilities:
                    unsupported.append(block['type'])
            blocks = [block if block['type'] in capabilities else {
                'id': block['id'], 'type': 'unsupported', 'fallback': block.get('title') or block.get('body') or '',
            } for block in blocks]
        return {
            'schema_version': 1,
            'version': revision.number,
            'revision_id': revision.id,
            'kind': payload['kind'],
            'slug': payload['slug'],
            'language': language,
            'title': payload['title'][language],
            'summary': payload['summary'][language],
            'category': payload['category'],
            'image_url': payload['image_url'],
            'blocks': blocks,
            'design_tokens': {**payload['design_tokens'], **payload['platform_overrides'][platform]},
            'seo': {
                'title': payload['seo']['title'][language],
                'description': payload['seo']['description'][language],
            },
            'unsupported_components': sorted(set(unsupported)),
            'published_at': revision.released_at.isoformat() + 'Z' if revision.released_at else None,
        }

    @http.route('/editor/<string:kind>/<string:slug>', type='http', auth='public', website=True, sitemap=True)
    def content_page(self, kind, slug, **kwargs):
        if kind not in ('page', 'blog'):
            return request.not_found()
        document = self._document(kind, slug)
        if not document:
            return request.not_found()
        content = self._localized(document)
        return request.render('ab_ecommerce_editor.public_content', {
            'content': content,
            'block_style': block_style,
            'is_editor_preview': False,
        })

    @http.route('/editor/preview/<int:document_id>', type='http', auth='user', website=True, methods=['GET'], sitemap=False)
    def content_preview(self, document_id, **kwargs):
        document = request.env['ab_ecommerce_editor_document'].search(fields.Domain([
            ('id', '=', document_id), ('website_id', '=', request.website.id),
        ]), limit=1)
        if not document:
            return request.not_found()
        if document.native_path:
            target = '/shop/category' if document.native_path == '/shop/offers' else document.native_path
            query = urlencode({
                **({'deal': 'discount'} if document.native_path == '/shop/offers' else {}),
                'ae_preview': document.id, 'section': kwargs.get('section', ''),
                'lang': kwargs.get('lang', request.env.lang), 'v': kwargs.get('v', ''),
            })
            language = request.env['res.lang'].search(fields.Domain('code', '=', kwargs.get('lang', request.env.lang)), limit=1)
            prefix = '/' + language.url_code if language and language in request.website.language_ids else ''
            return request.redirect(f'{prefix}{target}?{query}', code=303)
        if document.kind == 'homepage':
            language = kwargs.get('lang')
            if language in ('en_US', 'ar_001'):
                request.update_context(lang=language)
                document = document.with_context(lang=language)
            language = 'ar_001' if (request.env.lang or '').startswith('ar') else 'en_US'
            snapshot = document._snapshot()
            blocks = snapshot['blocks'][language]
            section = kwargs.get('section')
            if section:
                blocks = [block for block in blocks if block['type'] == section]
                for block in blocks:
                    block['active'] = True
            response = request.render('ab_ecommerce_editor.homepage_preview', {
                'ae_home_style': {**snapshot['design_tokens'], **snapshot['platform_overrides']['web']},
                'ae_home_blocks': blocks, 'ae_preview_section': section, 'no_header': bool(section), 'no_footer': bool(section),
            })
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
            return response
        content = self._localized(document, snapshot=document._snapshot())
        response = request.render('ab_ecommerce_editor.public_content', {
            'content': content, 'block_style': block_style, 'is_editor_preview': True,
        })
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    @http.route('/editor/blog', type='http', auth='public', website=True, sitemap=True)
    def blog_index(self, **kwargs):
        documents = request.env['ab_ecommerce_editor_document'].sudo().search(fields.Domain([
            ('website_id', '=', request.website.id), ('kind', '=', 'blog'),
            ('active', '=', True), ('published_revision_id', '!=', False),
        ]), order='published_at desc', limit=48)
        return request.render('ab_ecommerce_editor.public_blog_index', {
            'posts': [self._localized(document) for document in documents],
        })

    @http.route([
        '/api/v1/editor/content/<string:kind>/<string:slug>',
        '/api/v1/editor/content/<string:kind>/<string:slug>/versions/<int:number>',
    ], type='http', auth='public', website=True, methods=['GET'], csrf=False, multilang=False, sitemap=False)
    def content_api(self, kind, slug, number=None, **kwargs):
        if kind not in ('page', 'blog'):
            return request.make_json_response({'error': 'not_found'}, status=404)
        document = self._document(kind, slug)
        if not document:
            return request.make_json_response({'error': 'not_found'}, status=404)
        revision = document.published_revision_id
        if number is not None:
            revision = request.env['ab_ecommerce_editor_revision'].sudo().search(fields.Domain([
                ('document_id', '=', document.id), ('number', '=', number), ('released_at', '!=', False),
            ]), limit=1)
            if not revision:
                return request.make_json_response({'error': 'not_found'}, status=404)
        requested_schema = request.httprequest.args.get('schema', '1')
        if requested_schema != '1':
            return request.make_json_response({'error': 'unsupported_schema', 'supported_schema_versions': [1]}, status=409)
        capabilities_raw = request.httprequest.args.get('components')
        capabilities = set(capabilities_raw.split(',')) if capabilities_raw is not None else None
        language = request.httprequest.args.get('lang', 'en_US')
        if language not in ('en_US', 'ar', 'ar_001'):
            return request.make_json_response({'error': 'unsupported_language'}, status=400)
        language = 'ar_001' if language.startswith('ar') else 'en_US'
        content = self._localized(document, platform='flutter', capabilities=capabilities, language=language, revision=revision)
        capability_key = 'all' if capabilities is None else 'explicit:' + ','.join(sorted(capabilities))
        capability_hash = hashlib.sha256(capability_key.encode()).hexdigest()[:12]
        headers = {
            'Cache-Control': 'public, max-age=60',
            'X-Content-Type-Options': 'nosniff',
            'ETag': f'"editor-{document.website_id.id}-{revision.id}-{language}-{capability_hash}"',
        }
        if request.httprequest.headers.get('If-None-Match') == headers['ETag']:
            return request.make_response('', headers=headers, status=304)
        return request.make_json_response({'data': content}, headers=headers)
