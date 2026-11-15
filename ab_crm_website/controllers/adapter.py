import json

from odoo import http
from odoo.http import request
from werkzeug.exceptions import BadRequest, Forbidden, RequestEntityTooLarge


class WebsiteExchange(http.Controller):
    @http.route(
        '/crm/website/v1/receive',
        type='http',
        auth='bearer',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def receive(self, **kwargs):
        if request.httprequest.scheme != 'https' or not request.httprequest.headers.get(
            'Authorization', ''
        ).startswith('Bearer '):
            raise Forbidden()
        if (
            not request.httprequest.content_length
            or request.httprequest.content_length > 600000
        ):
            raise RequestEntityTooLarge()
        try:
            values = json.loads(request.httprequest.get_data())
            if not isinstance(values, dict) or set(values) != {
                'account_code',
                'provider_account',
                'event',
            }:
                raise ValueError()
        except (ValueError, TypeError):
            raise BadRequest() from None
        result = request.env['ab_crm_messaging_api'].receive_website_event(**values)
        return request.make_json_response(
            result, headers=[('Cache-Control', 'no-store')]
        )
