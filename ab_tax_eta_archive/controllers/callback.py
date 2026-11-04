import hmac

from odoo import fields, http
from odoo.http import request


class EtaCallback(http.Controller):
    @http.route(['/ab_tax_eta_archive/callback/<int:config_id>/ping',
                 '/ab_tax_eta_archive/callback/<int:config_id>/notifications/receiptpackages'],
                type='http', auth='public', methods=['PUT'], csrf=False)
    def receive(self, config_id, **kwargs):
        # A connection-scoped key authorizes only notifications for that connection.
        config = request.env['ab_tax_eta_archive_config'].sudo().browse(config_id).exists()
        supplied = request.httprequest.headers.get('Authorization', '')
        if (not config or not config.active or not config.callback_key or
                not hmac.compare_digest(supplied.encode(),
                                        f'ApiKey {config.callback_key}'.encode())):
            return request.make_json_response({'error': 'Unauthorized'}, status=401)
        if request.httprequest.content_length is None or request.httprequest.content_length > 65536:
            return request.make_json_response({'error': 'Invalid request size'}, status=413)
        payload = request.httprequest.get_json(silent=True)
        if not isinstance(payload, dict):
            return request.make_json_response({'error': 'Invalid JSON'}, status=400)
        if request.httprequest.path.endswith('/ping'):
            if not config.taxpayer_rin or str(payload.get('rin', '')) != config.taxpayer_rin.strip():
                return request.make_json_response({'error': 'Taxpayer RIN mismatch'}, status=400)
            return request.make_json_response({'rin': config.taxpayer_rin.strip()})
        messages = payload.get('message')
        if (payload.get('type') != 'ReceiptPackageDownloadReady' or
                not isinstance(messages, list) or len(messages) > 100 or
                payload.get('count') != len(messages) or
                any(not isinstance(item, dict) or not isinstance(item.get('PackageId'), (str, int))
                    for item in messages)):
            return request.make_json_response({'error': 'Invalid package notification'}, status=400)
        packages = request.env['ab_tax_eta_archive_package'].sudo().search([
            ('sync_id.config_id', '=', config.id),
            ('package_id', 'in', [str(item['PackageId']) for item in messages]),
            ('notified_at', '=', False),
        ])
        packages.write({'notified_at': fields.Datetime.now()})
        # Notification data never becomes archived tax data. The cron downloads
        # the package through ETA's authenticated API and validates its contents.
        return request.make_json_response({'received': True})
