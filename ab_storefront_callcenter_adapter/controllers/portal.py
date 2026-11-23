from odoo import http
from odoo.http import request
from werkzeug.exceptions import Forbidden
from odoo.addons.ab_ecommerce_storefront.controllers.portal import AbStorefrontCustomerPortal
from .chat import Chat


class OrderPortal(AbStorefrontCustomerPortal):
    @http.route()
    def portal_order_page(self, order_id, **kwargs):
        response = super().portal_order_page(order_id, **kwargs)
        values = getattr(response, 'qcontext', None) or {}
        order = values.get('sale_order')
        if not order or not order.sudo().ab_callcenter_uuid:
            return response
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        try:
            allowed = Chat()._order(order.sudo().ab_callcenter_uuid, capability=False)
        except Forbidden:
            values['disable_composer'] = True
            return response
        if request.env.user._is_public():
            if request.httprequest.scheme != 'https':
                values['disable_composer'] = True
            else:
                Chat()._issue_capability(response, allowed)
        return response
