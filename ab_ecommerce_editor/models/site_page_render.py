import hashlib

from lxml import etree, html

from odoo import fields, models
from odoo.http import request

from .editor_document import validate_website


def editable_headings(wrap):
    for element in wrap.xpath('.//h1[not(*)] | .//h2[not(*)] | .//h3[not(*)]'):
        if any(
            set((ancestor.get('class') or '').split()) & {
                'oe_product', 'oe_product_cart', 'o_wsale_product_information',
                'ab-storefront-product-card', 'ab-storefront-products-grid',
            } or ancestor.get('itemtype') or ancestor.tag == 'form'
            for ancestor in element.iterancestors()
        ):
            continue
        text = (element.text or '').strip()
        if not text or len(text) > 4000:
            continue
        tree = element.getroottree()
        relative_path = tree.getpath(element)[len(tree.getpath(wrap)):]
        identity = relative_path + ':' + text
        yield 'text_' + hashlib.sha256(identity.encode()).hexdigest(), element


def render_site_page(markup, snapshot, language, render_block, preview=False, section_only=False):
    tree = html.document_fromstring(markup)
    wraps = tree.xpath('//*[@id="wrap"]')
    if not wraps:
        return markup
    wrap = wraps[0]
    blocks = snapshot['blocks'][language]
    native = next(block for block in blocks if block['type'] == 'storefront_page')
    if not preview and not native.get('content') and not native.get('style') and len(blocks) == 1:
        return markup
    for key, element in editable_headings(wrap):
        if preview:
            element.set('data-ae-field', key)
            element.set('data-ae-original', element.text or '')
        if key in native.get('content', {}):
            element.text = native['content'][key]
    if not section_only:
        original = list(wrap)
        original_text = wrap.text
        for child in original:
            wrap.remove(child)
        wrap.text = None
        for block in blocks:
            if block['type'] == 'storefront_page':
                if original_text and original_text.strip():
                    span = html.Element('span')
                    span.text = original_text
                    wrap.append(span)
                wrap.extend(original)
            elif block.get('active', True):
                for fragment in html.fragments_fromstring(str(render_block(block))):
                    if isinstance(fragment, etree._Element):
                        wrap.append(fragment)
    if native.get('style'):
        from ..controllers.editor_content import block_style
        wrap.set('style', (wrap.get('style') or '') + ';' + block_style(native['style']))
    if preview:
        for image in tree.xpath('//img'):
            image.set('loading', 'eager')
        style = html.Element('style')
        style.text = 'header#top,footer#bottom,.o_frontend_to_backend_nav{display:none!important}html,body,#wrapwrap{min-height:0!important}html,body{overflow:hidden!important}#wrapwrap{padding:0!important}*,*::before,*::after{animation:none!important;transition:none!important}'
        tree.find('head').append(style)
        wrap.set('data-ae-native-page', '1')
    return '<!DOCTYPE html>' + html.tostring(tree, encoding='unicode', method='html')


class EditorSitePageHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _post_dispatch(cls, response):
        super()._post_dispatch(response)
        if not getattr(request, 'website', None) or request.httprequest.method != 'GET' or response.status_code != 200:
            return
        if response.mimetype != 'text/html':
            return
        path = request.httprequest.path.rstrip('/') or '/'
        languages = request.website.language_ids.mapped('url_code')
        parts = path.split('/', 2)
        if len(parts) > 1 and parts[1] in languages:
            path = '/' + (parts[2] if len(parts) > 2 else '')
        if path == '/shop/category' and request.httprequest.args.get('deal') == 'discount':
            path = '/shop/offers'
        preview_id = request.httprequest.args.get('ae_preview')
        model = request.env['ab_ecommerce_editor_document']
        domain = fields.Domain([
            ('website_id', '=', request.website.id), ('company_id', '=', request.website.company_id.id),
            ('native_path', '=', path), ('active', '=', True),
        ])
        if preview_id:
            model.check_access('read')
            validate_website(request.website)
            document = model.search(domain & fields.Domain('id', '=', int(preview_id) if preview_id.isdigit() else 0), limit=1)
            if not document:
                return
            snapshot = document._snapshot()
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        else:
            document = model.sudo().search(domain & fields.Domain('published_revision_id', '!=', False), limit=1)
            if not document:
                return
            snapshot = document.published_revision_id.payload
        language = 'ar_001' if (request.env.lang or '').startswith('ar') else 'en_US'
        response.flatten()
        from ..controllers.editor_content import block_style

        def render_block(block):
            return request.env['ir.ui.view']._render_template('ab_ecommerce_editor.site_page_block', {
                'block': block, 'block_style': block_style,
            })
        response.set_data(render_site_page(
            response.get_data(as_text=True), snapshot, language, render_block,
            preview=bool(preview_id), section_only=bool(preview_id and request.httprequest.args.get('section')),
        ))
