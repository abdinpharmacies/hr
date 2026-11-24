from odoo import fields, http
from odoo.http import request
from uuid import UUID
from odoo.exceptions import AccessError
from werkzeug.exceptions import Forbidden, NotFound
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


class BackendOrder(http.Controller):
    @http.route(['/odoo/storefront-callcenter/backend-order/<string:source_uuid>/<string:order_uuid>',
                 '/storefront-callcenter/backend-order/<string:source_uuid>/<string:order_uuid>'],
                type='http', auth='user', methods=['GET'])
    def open_backend_order(self, source_uuid, order_uuid):
        if not request.env.user.has_group('base.group_user'):
            raise Forbidden()
        try:
            if any(str(UUID(value)) != value for value in (source_uuid, order_uuid)):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise NotFound() from None
        try:
            domain = (fields.Domain('ab_callcenter_uuid', '=', order_uuid)
                & fields.Domain('ab_callcenter_endpoint_id', 'any!', fields.Domain('source', '=', source_uuid))
                & fields.Domain('website_id', '!=', False))
            orders = request.env['sale.order'].search(domain, limit=2)
        except AccessError:
            raise NotFound() from None
        if len(orders) != 1:
            raise NotFound()
        response = request.redirect('/odoo/ecommerce-orders/' + str(orders.id))
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
