import json

from odoo import http
from odoo.http import request
from werkzeug.exceptions import BadRequest, Forbidden, RequestEntityTooLarge


class WebsiteExchange(http.Controller):
    @http.route(
        ['/crm/website/v1/receive', '/crm/website/v2/receive', '/crm/website/v3/receive', '/crm/website/v4/receive'],
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
        method = {'/crm/website/v1/receive': 'receive_website_event',
                  '/crm/website/v2/receive': 'receive_website_chat',
                  '/crm/website/v4/receive': 'receive_website_chat',
                  '/crm/website/v3/receive': 'receive_website_lifecycle'}[request.httprequest.path]
        result = getattr(request.env['ab_crm_messaging_api'], method)(**values)
        return request.make_json_response(
            result, headers=[('Cache-Control', 'no-store')]
        )


class WebsiteMedia(http.Controller):
    @http.route('/crm/website/v4/media', type='http', auth='bearer', methods=['POST'], csrf=False, save_session=False)
    def upload(self, **kwargs):
        from uuid import UUID
        from ..media_protocol import LIMIT, check_bytes
        if request.httprequest.scheme != 'https' or not request.httprequest.headers.get('Authorization', '').startswith('Bearer '):
            raise Forbidden()
        if not request.httprequest.content_length or request.httprequest.content_length > LIMIT:
            raise RequestEntityTooLarge()
        try:
            values = json.loads(request.httprequest.headers.get('X-Website-Media', ''))
            if set(values) != {'account_code', 'provider_account', 'event_uuid', 'attachment'}:
                raise ValueError()
            if str(UUID(values['event_uuid'])) != values['event_uuid']:
                raise ValueError()
            item = values['attachment']
            raw = check_bytes(item, request.httprequest.get_data())
        except (ValueError, TypeError, KeyError, AttributeError):
            raise BadRequest() from None
        api = request.env['ab_crm_messaging_api']
        account = api._account(values['account_code'], values['provider_account'])
        if account.provider != 'website' or not account.enabled or not account.active or not account.channel_id.sudo().active:
            raise Forbidden()
        account.lock_for_update()
        key = api._website_media_key(account, values['event_uuid'], item)
        files = request.env['ir.attachment'].sudo()
        if not files.search_count([('res_model', '=', account._name), ('res_id', '=', account.id), ('description', '=', key)], limit=1):
            files.create({'name': item['name'], 'mimetype': item['mimetype'], 'raw': raw,
                'res_model': account._name, 'res_id': account.id, 'company_id': account.company_id.id, 'description': key, 'public': False})
        return request.make_json_response({'digest': item['digest']}, headers=[('Cache-Control', 'no-store')])


class WebsiteComposerMedia(http.Controller):
    @http.route('/crm/website/media/upload', type='http', auth='user', methods=['POST'], csrf=True)
    def upload(self, conversation_id, token, submission_uuid, position, metadata, ufile, reply_id=False, target=None, **kwargs):
        import base64
        from uuid import UUID
        from odoo.exceptions import AccessError, ValidationError
        from ..media_protocol import LIMIT
        from ..models.media import upload_descriptor
        try:
            conversation_id, position = int(conversation_id), int(position)
            reply_id = int(reply_id) if reply_id else False
            if str(UUID(submission_uuid)) != submission_uuid or not 0 <= position < 4:
                raise ValueError()
            info = json.loads(metadata)
            if set(info) != {'name', 'mimetype', 'size', 'kind', 'duration'}:
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError):
            raise BadRequest() from None
        conversation = request.env['ab_crm_conversation'].with_context(ab_chatter_session_token=token).browse(conversation_id).exists()
        if not conversation or conversation.channel_id.provider != 'website':
            raise Forbidden()
        conversation._owned()
        if target is None:
            raise BadRequest()
        try:
            kind, selected = conversation._website_target(json.loads(target))
        except (ValueError, TypeError):
            raise BadRequest() from None
        conversation._website_selected_target(reply_id, selected.id if kind == 'order' else False,
            selected.id if kind == 'livechat' else False)
        conversation.lock_for_update()
        code, reason = conversation._reply_eligibility()
        if code:
            raise Forbidden()
        raw = ufile.read(LIMIT + 1)
        try:
            descriptor = upload_descriptor(dict(info, data=base64.b64encode(raw).decode()))
        except (ValueError, TypeError, KeyError):
            raise BadRequest() from None
        description = json.dumps(dict(info, employee_id=conversation._workspace_actor().employee_id.id, target=json.loads(target)), sort_keys=True)
        from ..protocol import fingerprint
        key = 'website-composer:' + fingerprint({'uuid': submission_uuid, 'position': position, 'descriptor': descriptor, 'actor': request.env.uid, 'employee': conversation._workspace_actor().employee_id.id, 'target': target})
        attachments = conversation.env['ir.attachment'].sudo()
        existing = attachments.search([('res_model', '=', conversation._name), ('res_id', '=', conversation.id),
            ('url', '=', key), ('create_uid', '=', request.env.uid), ('company_id', '=', conversation.company_id.id)], limit=1)
        if not existing:
            from odoo.addons.ab_crm_core.models.core import _INTERNAL
            guard = _INTERNAL.set(True)
            try:
                existing = attachments.create({'name': info['name'], 'mimetype': info['mimetype'], 'raw': raw,
                    'res_model': conversation._name, 'res_id': conversation.id, 'company_id': conversation.company_id.id,
                    'description': description, 'url': key, 'public': False})
            finally:
                _INTERNAL.reset(guard)
        return request.make_json_response({'upload_id': existing.id}, headers=[('Cache-Control', 'no-store')])


class WebsiteOutgoingMedia(http.Controller):
    @http.route('/crm/website/v4/media/<string:account_code>/<string:token>/<string:media_id>',
                type='http', auth='bearer', methods=['GET'], csrf=False, save_session=False)
    def download(self, account_code, token, media_id, provider_account, attempt, receipt, **kwargs):
        import base64
        from ..media_protocol import check_bytes
        if request.httprequest.scheme != 'https' or not request.httprequest.headers.get('Authorization', '').startswith('Bearer '):
            raise Forbidden()
        api = request.env['ab_crm_messaging_api']
        account = api._account(account_code, provider_account)
        try:
            attempt = int(attempt)
        except (TypeError, ValueError):
            raise BadRequest() from None
        operation = api._operation(account, token, attempt)
        if (account.provider != 'website' or not account.enabled or not account.active or not account.channel_id.sudo().active
                or not request.env.user.active or not api._website_operation_allowed(account, operation)
                or operation.state != 'received' or operation.receipt != receipt):
            raise Forbidden()
        descriptor = next((item for item in (operation.content or {}).get('media', []) if item['id'] == media_id), None)
        media = operation.message_id.media_ids.filtered(lambda item: str(item.id) == media_id)
        if not descriptor or not media or media.state != 'ready':
            raise Forbidden()
        raw = check_bytes(descriptor, base64.b64decode(media.data))
        return request.make_response(raw, headers=[('Content-Type', 'application/octet-stream'),
            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')])
