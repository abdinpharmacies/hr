from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError
from werkzeug.exceptions import Forbidden

from .auth_security import StorefrontAuthSecurity


class LegacyActivation(StorefrontAuthSecurity):
    @http.route('/my/legacy-activation', type='http', auth='user', website=True, sitemap=False, methods=['GET', 'POST'], csrf=True)
    def activate(self, **post):
        self._secure()
        user = request.env.user
        if not user._is_portal() or user._is_internal():
            raise Forbidden()
        registry = request.env['ab_ecommerce_legacy_customer']
        status = registry._portal_status(user, request.website)
        values = {'linked': status['linked'], 'error': False}
        if request.httprequest.method == 'POST' and not status['linked']:
            try:
                accepted = registry._claim(user, request.website, post.get('phone', ''), post.get('code', ''), self._ip())
            except UserError:
                accepted = False
            if accepted:
                return request.redirect('/my/home', 303)
            values['error'] = _('The phone number or activation code is invalid, expired or unavailable. Please contact customer support.')
        return self._render_legacy(values)

    def _render_legacy(self, values):
        response = request.render('ab_ecommerce_storefront.portal_activation', values)
        response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY'})
        return response
