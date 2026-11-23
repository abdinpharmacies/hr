import hashlib
import hmac
import json
from datetime import timedelta

from odoo import fields, http
from odoo.exceptions import ConcurrencyError, LockError
from odoo.http import request
from werkzeug.exceptions import BadRequest, Forbidden, RequestEntityTooLarge, Gone
from ..models.adapter import _CAPTURE
from ..models.chat import SessionEnded, opaque


class Exchange(http.Controller):
    @http.route(
        ['/storefront-callcenter/v1/<string:operation>', '/storefront-callcenter/v2/<string:operation>', '/storefront-callcenter/v3/<string:operation>', '/storefront-callcenter/v4/<string:operation>'],
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
        if '/v2/' in request.httprequest.path:
            operations = {
                'fetch': ('fetch_v2', {'source'}),
                'acknowledge': ('acknowledge_v2', {'source', 'event_uuid', 'fingerprint'}),
                'receive': ('receive_v2', {'source', 'destination_kind', 'destination_uuid', 'token', 'body'}),
            }
        if '/v3/' in request.httprequest.path:
            operations = {'fetch': ('fetch_v3', {'source'}),
                          'acknowledge': ('acknowledge_v3', {'source', 'event_uuid', 'fingerprint'})}
        if '/v4/' in request.httprequest.path:
            operations = {
                'capabilities': ('capabilities_v4', {'source'}),
                'fetch': ('fetch_v4', {'source'}),
                'acknowledge': ('acknowledge_v4', {'source', 'event_uuid', 'fingerprint'}),
                'receive': ('receive_v4', {'source', 'destination_kind', 'destination_uuid', 'token', 'body', 'attachments'}),
            }
        if operation not in operations:
            raise BadRequest()
        if (
            not request.httprequest.content_length
            or request.httprequest.content_length > (32768 if '/v4/' in request.httprequest.path else 16384)
        ):
            raise RequestEntityTooLarge()
        try:
            values = json.loads(request.httprequest.get_data())
            if (
                not isinstance(values, dict)
                or set(values) != operations[operation][1]
                or any(not isinstance(value, str) for key, value in values.items() if key != 'attachments')
            ):
                raise ValueError()
        except (ValueError, TypeError):
            raise BadRequest() from None
        try:
            result = getattr(request.env['ab_storefront_callcenter_api'], operations[operation][0])(**values)
        except SessionEnded:
            raise Gone() from None
        return request.make_json_response(
            result, headers=[('Cache-Control', 'no-store')]
        )


class Chat(http.Controller):
    def _order(self, order_uuid, capability=True):
        website = getattr(request, 'website', None) or request.env['website'].get_current_website()
        order = (
            request.env['sale.order']
            .sudo()
            .search(
                [
                    ('ab_callcenter_uuid', '=', order_uuid),
                    ('website_id', '=', website.id),
                    ('company_id', '=', website.company_id.id),
                ],
                limit=1,
            )
        )
        if (
            not order
            or order.ab_callcenter_endpoint_id.company_id != website.company_id
            or (order.ab_callcenter_endpoint_id.website_id
                and order.ab_callcenter_endpoint_id.website_id != website)
        ):
            raise Forbidden()
        if not request.env.user._is_public():
            identity = opaque(order.ab_callcenter_endpoint_id.source, 'account:' + str(request.env.uid))
            if order.ab_callcenter_account_uuid:
                if order.ab_callcenter_account_uuid != identity:
                    raise Forbidden()
                return order
            owner = hashlib.sha256(f'user:{request.env.uid}'.encode()).hexdigest()
            if hmac.compare_digest(owner, order.ab_callcenter_owner_hash or ''):
                return order
            guest_owner = request.session.get('ab_submission_owner')
            expected = hashlib.sha256(('guest:' + guest_owner).encode()).hexdigest() if guest_owner else ''
            cookie = request.httprequest.cookies.get('ab_website_chat_' + order_uuid, '')
            if (not order.ab_callcenter_endpoint_id.lifecycle_enabled or not expected
                    or not hmac.compare_digest(expected, order.ab_callcenter_owner_hash or '')
                    or not cookie or not order.ab_callcenter_capability_expires
                    or order.ab_callcenter_capability_expires <= fields.Datetime.now()
                    or not hmac.compare_digest(hashlib.sha256(cookie.encode()).hexdigest(), order.ab_callcenter_capability_hash or '')):
                raise Forbidden()
            order.lock_for_update()
            order.invalidate_recordset()
            if order.ab_callcenter_account_uuid and order.ab_callcenter_account_uuid != identity:
                raise Forbidden()
            guard = _CAPTURE.set(True)
            try:
                order.write({'ab_callcenter_account_uuid': identity, 'ab_callcenter_capability_hash': False,
                             'ab_callcenter_capability_expires': False})
                order._ab_callcenter_bind_order(identity)
            finally:
                _CAPTURE.reset(guard)
            return order
        if order.ab_callcenter_account_uuid:
            raise Forbidden()
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
            'ab_storefront_callcenter_adapter.chat', {'order': order,
                'chat_identity': opaque(order.ab_callcenter_endpoint_id.source, 'account:' + str(request.env.uid))
                    if not request.env.user._is_public() else 'guest'}
        )
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return self._issue_capability(response, order)

    def _issue_capability(self, response, order):
        order_uuid = order.ab_callcenter_uuid
        if request.env.user._is_public():
            if request.httprequest.scheme != 'https':
                raise Forbidden()
            token = hmac.new(request.session['ab_submission_owner'].encode(), order_uuid.encode(), hashlib.sha256).hexdigest()
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
                path='/',
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
    def messages(self, order_uuid, body='', event_uuid='', after='0', attachments='[]', **kwargs):
        order = self._order(order_uuid)
        if not isinstance(body, str) or len(body) > 4096:
            raise BadRequest()
        try:
            uploads = json.loads(attachments)
        except (ValueError, TypeError):
            raise BadRequest() from None
        files = request.env['ir.attachment']._ab_owned_files(order, uploads)
        if body.strip() or files:
            if not event_uuid:
                raise BadRequest()
            from uuid import UUID
            try:
                if str(UUID(event_uuid)) != event_uuid:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise BadRequest() from None
            try:
                order._ab_callcenter_customer_post(body.strip(), event_uuid, files.ids)
            except SessionEnded:
                raise Gone() from None
        try:
            cursor = int(after)
            if cursor < 0:
                raise ValueError()
        except (TypeError, ValueError):
            raise BadRequest() from None
        messages = request.env['mail.message'].sudo().search([
            ('model', '=', 'sale.order'), ('res_id', '=', order.id),
            ('message_type', '=', 'comment'), ('subtype_id.internal', '=', False), ('id', '>', cursor),
        ], order='id', limit=101)
        from odoo.tools import html2plaintext
        history = [{'key': str(message.id), 'body': html2plaintext(message.body or '').strip(),
                    'direction': 'agent' if message.author_id.sudo().user_ids.filtered(lambda user: not user.share) else 'customer',
                    'at': message.date.isoformat(), 'attachments': [
                        dict(item, url='/storefront-callcenter/chat/' + order_uuid + '/media/' + str(message.id) + '/' + item['id'])
                        for item in request.env['ir.attachment']._ab_media_descriptors(message.attachment_ids)]} for message in messages[:100]]
        return request.make_json_response(
            {'closed': bool(order.ab_callcenter_chat_closed), 'ready': bool(not order.ab_callcenter_chat_closed and order.ab_callcenter_chat_ready and order.ab_callcenter_endpoint_id.chat_enabled),
             'messages': history, 'cursor': history[-1]['key'] if history else str(cursor),
             'has_more': len(messages) > 100, 'acknowledged': event_uuid if body.strip() or files else False,
             'account_identity': opaque(order.ab_callcenter_endpoint_id.source, 'account:' + str(request.env.uid))
                 if not request.env.user._is_public() else 'guest'},
            headers=[('Cache-Control', 'private, no-store')],
        )

    @http.route('/storefront-callcenter/order/status', type='jsonrpc', auth='public', methods=['POST'], website=True)
    def order_status(self, order_id):
        if type(order_id) is not int:
            raise Forbidden()
        candidate = request.env['sale.order'].sudo().browse(order_id).exists()
        if not candidate or not candidate.ab_callcenter_uuid:
            raise Forbidden()
        order = self._order(candidate.ab_callcenter_uuid)
        return {'closed': bool(order.ab_callcenter_chat_closed),
                'ready': bool(order.ab_callcenter_chat_ready)}

    @http.route('/storefront-callcenter/chat/<string:order_uuid>/media/<int:message_id>/<int:attachment_id>',
                type='http', auth='public', website=True, methods=['GET'], sitemap=False)
    def order_media(self, order_uuid, message_id, attachment_id, **kwargs):
        order = self._order(order_uuid)
        message = request.env['mail.message'].sudo().search([
            ('id', '=', message_id), ('model', '=', 'sale.order'), ('res_id', '=', order.id),
            ('message_type', '=', 'comment'), ('subtype_id.internal', '=', False),
        ], limit=1)
        file = message.attachment_ids.filtered(lambda file: file.id == attachment_id)
        if not file:
            raise Forbidden()
        from odoo.http import content_disposition
        return request.make_response(file.raw, headers=[('Content-Type', file.mimetype),
            ('Content-Disposition', content_disposition(file.name)), ('Cache-Control', 'private, no-store'),
            ('X-Content-Type-Options', 'nosniff')])

    @http.route('/storefront-callcenter/chat/<string:order_uuid>/upload', type='http', auth='public',
                website=True, methods=['POST'], csrf=True)
    def order_upload(self, order_uuid, ufile, **kwargs):
        order = self._order(order_uuid)
        order._ab_callcenter_require_chat()
        order._ab_callcenter_require_open()
        if not order.ab_callcenter_endpoint_id.media_enabled:
            raise Forbidden()
        from ..media_protocol import LIMIT
        raw = ufile.read(LIMIT + 1)
        if not raw or len(raw) > LIMIT:
            raise RequestEntityTooLarge()
        file = request.env['ir.attachment'].sudo().create({'name': ufile.filename, 'raw': raw,
            'res_model': 'mail.compose.message', 'res_id': 0, 'company_id': order.company_id.id, 'public': False})
        request.env['ir.attachment']._ab_media_descriptors(file)
        return request.make_json_response({'id': file.id, 'token': file._get_ownership_token(), 'name': file.name},
            headers=[('Cache-Control', 'no-store')])


from odoo.addons.im_livechat.controllers.main import LivechatController
from odoo.addons.mail.tools.discuss import add_guest_to_context, Store


class NativeChat(LivechatController):
    @http.route()
    @add_guest_to_context
    def get_session(self, channel_id, previous_operator_id=None, chatbot_script_id=None, persisted=True, **kwargs):
        channel = request.env['im_livechat.channel'].browse(channel_id).exists()
        endpoint = channel.sudo()._ab_callcenter_endpoint() if channel else False
        if endpoint:
            if endpoint.website_id != request.env['website'].get_current_website():
                raise Forbidden()
            try:
                endpoint.lock_for_update()
            except LockError as error:
                raise ConcurrencyError('Website chat session initialization is busy') from error
            guest = request.env['mail.guest']._get_guest_from_context()
            user = request.env.user
            domain = [('ab_callcenter_endpoint_id', '=', endpoint.id), ('livechat_end_dt', '=', False)]
            if user._is_public():
                domain += [('ab_callcenter_identity_kind', '=', 'visitor'), ('channel_member_ids.guest_id', '=', guest.id)]
                session = request.env['discuss.channel'].sudo().search(domain, order='id desc', limit=1) if guest else False
            else:
                domain += [('ab_callcenter_identity_uuid', '=', opaque(endpoint.source, 'account:' + str(user.id)))]
                session = request.env['discuss.channel'].sudo().search(domain, order='id desc', limit=1)
            if not user._is_public() and not session and guest and endpoint.lifecycle_enabled:
                session = request.env['discuss.channel'].sudo().search([
                    ('ab_callcenter_endpoint_id', '=', endpoint.id), ('livechat_end_dt', '=', False),
                    ('ab_callcenter_identity_kind', '=', 'visitor'), ('channel_member_ids.guest_id', '=', guest.id),
                ], order='id desc', limit=1)
                if session:
                    session._ab_callcenter_bind_account()
            if session:
                session._ab_callcenter_authorize()
                if not user._is_public() and not session.ab_callcenter_user_id:
                    guard = _CAPTURE.set(True)
                    try:
                        session.write({'ab_callcenter_user_id': user.id})
                    finally:
                        _CAPTURE.reset(guard)
                store = Store()
                request.env['res.users']._init_store_data(store)
                store.add(session, extra_fields={'isLoaded': True, 'scrollUnread': False})
                return {'store_data': store.get_result(), 'channel_id': session.id}
        return super().get_session(channel_id, previous_operator_id=previous_operator_id,
            chatbot_script_id=chatbot_script_id, persisted=persisted, **kwargs)

    @http.route('/storefront-callcenter/native/handoff', type='jsonrpc', auth='user', methods=['POST'])
    @add_guest_to_context
    def handoff(self, channel_id):
        session = self._native_session(channel_id, handoff=True)
        if session.ab_callcenter_identity_kind == 'visitor':
            session._ab_callcenter_bind_account()
        return True

    def _native_session(self, channel_id, handoff=False):
        if type(channel_id) is not int:
            raise Forbidden()
        session = request.env['discuss.channel'].sudo().browse(channel_id).exists()
        if (not session or not session.ab_callcenter_endpoint_id
                or session.ab_callcenter_endpoint_id.website_id != request.env['website'].get_current_website()):
            raise Forbidden()
        session._ab_callcenter_authorize(handoff=handoff and session.ab_callcenter_identity_kind == 'visitor')
        return session

    @http.route('/storefront-callcenter/native/send', type='jsonrpc', auth='public', methods=['POST'])
    @add_guest_to_context
    def send(self, channel_id, body, event_uuid, attachments=None):
        session = self._native_session(channel_id)
        from uuid import UUID
        try:
            if not isinstance(event_uuid, str) or str(UUID(event_uuid)) != event_uuid or not isinstance(body, str):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise BadRequest() from None
        files = request.env['ir.attachment']._ab_owned_files(session, attachments or [])
        if files and not session.ab_callcenter_endpoint_id.media_enabled:
            raise BadRequest()
        from markupsafe import Markup, escape
        from odoo.tools import html2plaintext
        message = session.with_context(ab_message_uuid=event_uuid, ab_customer_native=True).message_post(
            body=Markup('<p>%s</p>') % escape(html2plaintext(body)), attachment_ids=files.ids, message_type='comment', subtype_xmlid='mail.mt_comment')
        return {'store_data': Store().add(message).get_result(), 'message_id': message.id,
                'acknowledged': event_uuid}

    @http.route('/storefront-callcenter/native/history', type='jsonrpc', auth='public', methods=['POST'])
    @add_guest_to_context
    def history(self, channel_id, after=0):
        session = self._native_session(channel_id)
        if type(after) is not int or after < 0:
            raise BadRequest()
        sessions = request.env['discuss.channel'].sudo().search([
            ('ab_callcenter_endpoint_id', '=', session.ab_callcenter_endpoint_id.id),
            ('ab_callcenter_identity_kind', '=', session.ab_callcenter_identity_kind),
            ('ab_callcenter_identity_uuid', '=', session.ab_callcenter_identity_uuid),
        ])
        messages = request.env['mail.message'].sudo().search([
            ('model', '=', 'discuss.channel'), ('res_id', 'in', sessions.ids),
            ('message_type', '=', 'comment'), ('subtype_id.internal', '=', False), ('id', '>', after),
        ], order='id', limit=101)
        from odoo.tools import html2plaintext
        previous = [{'id': message.id, 'body': html2plaintext(message.body or '').strip()}
                    for message in messages[:100] if message.res_id != session.id]
        current = messages[:100].filtered(lambda message: message.res_id == session.id)
        store = Store().add(messages[:100])
        return {'closed': bool(session.livechat_end_dt), 'store_data': store.get_result(), 'message_ids': current.ids, 'previous': previous,
                'cursor': messages[:100][-1:].id or after, 'has_more': len(messages) > 100}
