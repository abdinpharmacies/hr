import json
from uuid import UUID

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from werkzeug.exceptions import BadRequest, Unauthorized, RequestEntityTooLarge

OPERATIONS = {
    'get_provider_credentials': set(),
    'receive_event': {'event'},
    'receive_media': {'event_id', 'data', 'failed'},
    'receive_status': {'reference', 'status', 'destination'},
    'lease_outgoing': set(),
    'acknowledge_receipt': {'token', 'attempt', 'lease', 'receipt'},
    'authorize_send': {'token', 'attempt', 'receipt'},
    'report_delivery': {'token', 'attempt', 'receipt', 'status', 'reference', 'error'},
}


class MessagingGateway(http.Controller):
    @http.route(
        '/crm/messaging/v1/<string:operation>',
        type='http',
        auth='bearer',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def dispatch(self, operation, **kwargs):
        if (
            not request.httprequest.headers.get('Authorization', '')
            .lower()
            .startswith('bearer ')
        ):
            raise Unauthorized()
        if operation not in OPERATIONS or not hasattr(
            request.env['ab_crm_messaging_api'], operation
        ):
            raise BadRequest('Unsupported operation')
        limit = 29 * 1024 * 1024 if operation == 'receive_media' else 1048576
        if (
            not request.httprequest.content_length
            or request.httprequest.content_length > limit
        ):
            raise RequestEntityTooLarge()
        raw = request.httprequest.get_data()
        if len(raw) > limit:
            raise RequestEntityTooLarge()
        try:
            envelope = json.loads(raw)
            if not isinstance(envelope, dict) or set(envelope) != {
                'correlation_id',
                'payload',
            }:
                raise ValueError()
            correlation = str(UUID(envelope['correlation_id']))
            payload = envelope['payload']
            if not isinstance(payload, dict) or set(payload) != OPERATIONS[
                operation
            ] | {'account_code', 'provider_account'}:
                raise ValueError()
            if 'event' in payload and not isinstance(payload['event'], dict):
                raise ValueError()
            if 'attempt' in payload and (
                type(payload['attempt']) is not int or payload['attempt'] < 1
            ):
                raise ValueError()
            if any(
                not isinstance(value, str)
                for key, value in payload.items()
                if key not in ('event', 'attempt')
            ):
                raise ValueError()
            if any(
                not isinstance(payload[key], str) or not 1 <= len(payload[key]) <= 256
                for key in ('account_code', 'provider_account')
            ):
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError):
            raise BadRequest('Invalid messaging envelope') from None
        try:
            with request.env.cr.savepoint():
                result = getattr(request.env['ab_crm_messaging_api'], operation)(
                    **payload
                )
        except AccessError:
            return request.make_json_response(
                {'correlation_id': correlation, 'error': 'forbidden'}, status=403
            )
        except (UserError, ValidationError):
            return request.make_json_response(
                {'correlation_id': correlation, 'error': 'rejected'}, status=409
            )
        return request.make_json_response(
            {'correlation_id': correlation, 'result': result},
            headers={'Cache-Control': 'no-store'},
        )
