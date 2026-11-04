import hashlib
from copy import deepcopy

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
    def _document(self, kind, slug):
        return request.env['ab_ecommerce_editor_document'].sudo().search(fields.Domain([
            ('website_id', '=', request.website.id),
            ('kind', '=', kind), ('slug', '=', slug),
            ('active', '=', True), ('published_revision_id', '!=', False),
        ]), limit=1)

    def _localized(self, document, platform='web', capabilities=None, snapshot=None, language=None, revision=None):
        revision = revision if revision is not None else document.published_revision_id
        payload = deepcopy(snapshot if snapshot is not None else revision.payload)
        language = language or ('ar_001' if (request.env.lang or '').startswith('ar') else 'en_US')
        blocks = payload['blocks'][language]
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
