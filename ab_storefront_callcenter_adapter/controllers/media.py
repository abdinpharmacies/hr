import json
from uuid import UUID

from odoo import http
from odoo.http import request
from werkzeug.exceptions import BadRequest, Forbidden, RequestEntityTooLarge
from ..media_protocol import LIMIT, check_bytes, validate_attachments


class Media(http.Controller):
    @http.route('/storefront-callcenter/v4/media/<string:source>/<string:event_uuid>/<string:media_id>',
                type='http', auth='bearer', methods=['GET'], csrf=False, save_session=False)
    def download(self, source, event_uuid, media_id):
        self._secure()
        endpoint = request.env['ab_storefront_callcenter_api']._endpoint(source)
        if not endpoint.media_enabled:
            raise Forbidden()
        event = request.env['ab_storefront_callcenter_chat_event'].sudo().search([
            ('endpoint_id', '=', endpoint.id), ('event_uuid', '=', event_uuid),
        ], limit=1)
        item = next((item for item in (event.envelope or {}).get('attachments', []) if item['id'] == media_id), None)
        attachment = event.message_id.attachment_ids.filtered(lambda file: str(file.id) == media_id)
        if not item or not attachment or event.message_id.subtype_id.internal:
            raise Forbidden()
        return request.make_response(check_bytes(item, attachment.raw), headers=[
            ('Content-Type', 'application/octet-stream'), ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')])

    def _secure(self):
        if request.httprequest.scheme != 'https' or not request.httprequest.headers.get('Authorization', '').startswith('Bearer '):
            raise Forbidden()

    @http.route('/storefront-callcenter/v4/media', type='http', auth='bearer', methods=['POST'], csrf=False, save_session=False)
    def upload(self, **kwargs):
        self._secure()
        if not request.httprequest.content_length or request.httprequest.content_length > LIMIT:
            raise RequestEntityTooLarge()
        try:
            values = json.loads(request.httprequest.headers.get('X-Website-Media', ''))
            if set(values) != {'source', 'kind', 'destination', 'token', 'attachment'} or values['kind'] not in ('order', 'livechat'):
                raise ValueError()
            if str(UUID(values['destination'])) != values['destination'] or not 1 <= len(values['token']) <= 128:
                raise ValueError()
            item = values['attachment']
            validate_attachments([item])
            raw = check_bytes(item, request.httprequest.get_data())
        except (ValueError, KeyError, TypeError, AttributeError):
            raise BadRequest() from None
        endpoint = request.env['ab_storefront_callcenter_api']._endpoint(values['source'])
        if not endpoint.media_enabled or not endpoint.outgoing_enabled or not endpoint.chat_enabled:
            raise Forbidden()
        endpoint.lock_for_update()
        model, uuid_field = ('sale.order', 'ab_callcenter_uuid') if values['kind'] == 'order' else ('discuss.channel', 'ab_callcenter_session_uuid')
        target = request.env[model].sudo().search([
            ('ab_callcenter_endpoint_id', '=', endpoint.id), (uuid_field, '=', values['destination']),
        ], limit=1)
        if not target or (model == 'sale.order' and (target.website_id != endpoint.website_id or target.company_id != endpoint.company_id)):
            raise Forbidden()
        target.lock_for_update()
        target.invalidate_recordset()
        if model == 'sale.order':
            target._ab_callcenter_require_chat()
            target._ab_callcenter_require_open()
        elif target.livechat_end_dt:
            raise Forbidden()
        attachments = request.env['ir.attachment']
        key = attachments._ab_exchange_key(endpoint, values['kind'], values['destination'], values['token'], item)
        if not attachments.sudo().search_count([('res_model', '=', endpoint._name), ('res_id', '=', endpoint.id), ('description', '=', key)], limit=1):
            attachments.sudo().create({'name': item['name'], 'mimetype': item['mimetype'], 'raw': raw,
                'res_model': endpoint._name, 'res_id': endpoint.id, 'company_id': endpoint.company_id.id, 'description': key, 'public': False,
                'ab_website_media': item})
        return request.make_json_response({'digest': item['digest']}, headers=[('Cache-Control', 'no-store')])


from odoo.addons.mail.controllers.attachment import AttachmentController
from odoo.addons.mail.tools.discuss import add_guest_to_context
from .chat import NativeChat, Chat


class WebsiteUpload(AttachmentController):
    @http.route()
    @add_guest_to_context
    def mail_attachment_upload(self, ufile, thread_id, thread_model, is_pending=False, **kwargs):
        target = False
        if thread_model == 'discuss.channel':
            candidate = request.env['discuss.channel'].sudo().browse(int(thread_id)).exists()
            if candidate.ab_callcenter_endpoint_id:
                target = NativeChat()._native_session(int(thread_id))
                endpoint = target.ab_callcenter_endpoint_id
        elif thread_model == 'sale.order':
            candidate = request.env['sale.order'].sudo().browse(int(thread_id)).exists()
            if candidate.ab_callcenter_uuid:
                target = Chat()._order(candidate.ab_callcenter_uuid)
                target._ab_callcenter_require_chat()
                target._ab_callcenter_require_open()
                endpoint = target.ab_callcenter_endpoint_id
        if target:
            target.lock_for_update()
            target.invalidate_recordset()
            if thread_model == 'discuss.channel' and target.livechat_end_dt:
                raise Forbidden()
            if not endpoint.media_enabled:
                raise Forbidden()
            raw = ufile.read(LIMIT + 1)
            if not raw or len(raw) > LIMIT:
                raise RequestEntityTooLarge()
            ufile.seek(0)
        return super().mail_attachment_upload(ufile, thread_id, thread_model, is_pending=is_pending, **kwargs)
