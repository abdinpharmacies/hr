import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from odoo import fields, http
from odoo.http import request
from werkzeug.exceptions import BadRequest, Forbidden, RequestEntityTooLarge
from ..models.adapter import _CAPTURE


class Exchange(http.Controller):
    @http.route(
        '/storefront-callcenter/v1/<string:operation>',
        type='http',
        auth='bearer',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def exchange(self, operation, **kwargs):
        if request.httprequest.scheme != 'https' or not request.httprequest.headers.get(
            'Authorization', ''
        ).startswith('Bearer '):
            raise Forbidden()
        operations = {
            'fetch': ('fetch_v1', {'source'}),
            'acknowledge': ('acknowledge_v1', {'source', 'event_uuid', 'fingerprint'}),
            'receive': ('receive_v1', {'source', 'order_uuid', 'token', 'body'}),
        }
        if operation not in operations:
            raise BadRequest()
        if (
            not request.httprequest.content_length
            or request.httprequest.content_length > 16384
        ):
            raise RequestEntityTooLarge()
        try:
            values = json.loads(request.httprequest.get_data())
            if (
                not isinstance(values, dict)
                or set(values) != operations[operation][1]
                or any(not isinstance(value, str) for value in values.values())
            ):
                raise ValueError()
        except (ValueError, TypeError):
            raise BadRequest() from None
        result = getattr(
            request.env['ab_storefront_callcenter_api'], operations[operation][0]
        )(**values)
        return request.make_json_response(
            result, headers=[('Cache-Control', 'no-store')]
        )


class Chat(http.Controller):
    def _order(self, order_uuid, capability=True):
        order = (
            request.env['sale.order']
            .sudo()
            .search(
                [
                    ('ab_callcenter_uuid', '=', order_uuid),
                    ('website_id', '=', request.website.id),
                    ('company_id', '=', request.website.company_id.id),
                ],
                limit=1,
            )
        )
        if (
            not order
            or not order.ab_callcenter_endpoint_id.enabled
            or order.ab_callcenter_endpoint_id.website_id != request.website
        ):
            raise Forbidden()
        if not request.env.user._is_public():
            if (
                order.partner_id.commercial_partner_id
                != request.env.user.partner_id.commercial_partner_id
            ):
                raise Forbidden()
            return order
        owner = request.session.get('ab_submission_owner')
        expected = (
            hashlib.sha256(('guest:' + owner).encode()).hexdigest() if owner else ''
        )
        if not expected or not hmac.compare_digest(
            expected, order.ab_callcenter_owner_hash or ''
        ):
            raise Forbidden()
        if capability:
            cookie = request.httprequest.cookies.get(
                'ab_website_chat_' + order_uuid, ''
            )
            digest = hashlib.sha256(cookie.encode()).hexdigest()
            if (
                not cookie
                or not order.ab_callcenter_capability_expires
                or order.ab_callcenter_capability_expires <= fields.Datetime.now()
                or not hmac.compare_digest(
                    digest, order.ab_callcenter_capability_hash or ''
                )
            ):
                raise Forbidden()
        return order

    @http.route(
        '/my/website-chat/<string:order_uuid>',
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
        sitemap=False,
    )
    def page(self, order_uuid, **kwargs):
        order = self._order(order_uuid, capability=False)
        response = request.render(
            'ab_storefront_callcenter_adapter.chat', {'order': order}
        )
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if request.env.user._is_public():
            if request.httprequest.scheme != 'https':
                raise Forbidden()
            token = secrets.token_urlsafe(32)
            guard = _CAPTURE.set(True)
            try:
                order.write(
                    {
                        'ab_callcenter_capability_hash': hashlib.sha256(
                            token.encode()
                        ).hexdigest(),
                        'ab_callcenter_capability_expires': fields.Datetime.now()
                        + timedelta(hours=24),
                    }
                )
            finally:
                _CAPTURE.reset(guard)
            response.set_cookie(
                'ab_website_chat_' + order_uuid,
                token,
                max_age=86400,
                secure=True,
                httponly=True,
                samesite='Strict',
                path='/storefront-callcenter/chat/' + order_uuid,
            )
        return response

    @http.route(
        '/storefront-callcenter/chat/<string:order_uuid>',
        type='http',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=True,
    )
    def messages(self, order_uuid, body='', event_uuid='', **kwargs):
        order = self._order(order_uuid)
        if not isinstance(body, str) or len(body) > 4096:
            raise BadRequest()
        if body.strip():
            if not event_uuid:
                raise BadRequest()
            guard = _CAPTURE.set(True)
            try:
                order._ab_callcenter_event(
                    'message', {'body': body.strip()}, event_uuid=event_uuid
                )
            finally:
                _CAPTURE.reset(guard)
        incoming = (
            request.env['ab_storefront_callcenter_event']
            .sudo()
            .search(
                [
                    ('order_id', '=', order.id),
                ],
                order='id desc',
                limit=100,
            )
        )
        replies = (
            request.env['ab_storefront_callcenter_reply']
            .sudo()
            .search(
                [
                    ('order_id', '=', order.id),
                ],
                order='id desc',
                limit=100,
            )
        )
        history = [
            {
                'key': event.event_uuid,
                'body': event.envelope['payload']['body'],
                'direction': 'customer',
                'at': event.create_date.isoformat(),
            }
            for event in incoming
            if event.envelope['kind'] == 'message'
        ]
        history += [
            {
                'key': reply.token,
                'body': reply.body,
                'direction': 'agent',
                'at': reply.create_date.isoformat(),
            }
            for reply in replies
        ]
        return request.make_json_response(
            {'messages': sorted(history, key=lambda row: (row['at'], row['key']))},
            headers=[('Cache-Control', 'private, no-store')],
        )
