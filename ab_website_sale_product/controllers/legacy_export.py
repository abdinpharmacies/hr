import ipaddress
from urllib.parse import urlparse

from odoo import http
from odoo.http import request, content_disposition
from werkzeug.exceptions import Forbidden, NotFound


class LegacyCodeExport(http.Controller):
    def _local_address(self, value):
        if value == 'localhost':
            return True
        try:
            return ipaddress.ip_address(value or '').is_loopback
        except ValueError:
            return False

    @http.route('/ab_legacy/exports/<int:batch_id>', type='http', auth='user', methods=['GET'])
    def export_codes(self, batch_id):
        return self._download(batch_id, review=False)

    @http.route('/ab_legacy/review/<int:batch_id>', type='http', auth='user', methods=['GET'])
    def export_review(self, batch_id):
        return self._download(batch_id, review=True)

    def _download(self, batch_id, review):
        if not review:
            development = request.env['ir.config_parameter'].sudo().get_param('ab_website_sale_product.development', 'False') == 'True'
            hostname = urlparse(request.httprequest.host_url).hostname
            local = development and self._local_address(hostname) and self._local_address(request.httprequest.remote_addr)
            if not request.httprequest.is_secure and not local:
                raise Forbidden()
        batch = request.env['ab_ecommerce_legacy_batch'].browse(batch_id).exists()
        if not batch:
            raise NotFound()
        source = batch._review_csv_file() if review else None
        data = iter(lambda: source.read(64 * 1024), b'') if source else batch._export_csv()
        filename = f'legacy-customer-review-{batch.id}.csv' if review else f'legacy-customer-codes-{batch.id}.csv'
        response = request.make_response(data, headers=[
            ('Content-Type', 'text/csv; charset=utf-8'),
            ('Content-Disposition', content_disposition(filename)),
            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
        ])
        if source:
            response.call_on_close(source.close)
        return response
