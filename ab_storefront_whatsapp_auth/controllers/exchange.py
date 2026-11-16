import json

from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from werkzeug.exceptions import BadRequest, Forbidden, NotFound


class WhatsAppExchange(http.Controller):
    @http.route('/ab_storefront/auth/exchange/v1/<operation>', type='http', auth='bearer', methods=['POST'], csrf=False, save_session=False)
    def exchange(self, operation, **kwargs):
        if (not request.httprequest.is_secure
                or not request.httprequest.headers.get('Authorization', '').startswith('Bearer ')):
            raise Forbidden()
        if operation not in ('lease', 'dispatch', 'report', 'status'):
            raise NotFound()
        if not request.httprequest.content_length or request.httprequest.content_length > 4096:
            raise BadRequest()
        if not request.env.user.has_group('ab_storefront_whatsapp_auth.group_auth_transport'):
            raise Forbidden()
        try:
            data = json.loads(request.httprequest.get_data())
            if not isinstance(data, dict) or not isinstance(data.get('source'), str):
                raise ValueError
            transport_id = request.env['ab_storefront_whatsapp_transport'].sudo().search([
                ('source', '=', data['source']), ('service_user_id', '=', request.env.uid),
                ('company_id', 'in', request.env.user.company_ids.ids), ('enabled', '=', True),
            ], limit=1).id
            if not transport_id:
                raise Forbidden()
            result = request.env['ab_storefront_whatsapp_transport'].browse(transport_id)._exchange(operation, data)
        except AccessError:
            raise Forbidden() from None
        except (ValueError, TypeError, ValidationError):
            raise BadRequest() from None
        return request.make_json_response(result, headers={'Cache-Control': 'no-store'})
