"""Real receipt-detail cron + file generation while newer invoices stay pending."""
import json
from datetime import datetime, timedelta
from unittest.mock import patch

import requests
from odoo.addons.ab_tax_eta_archive.models.eta_policy import CAIRO, api_stamp, day_bounds

assert env.cr.dbname == 'eta_review_20261125'
today = datetime.now(CAIRO).date()
day = today - timedelta(days=3)
config = env['ab_tax_eta_archive_config'].create({
    'name': 'Receipt detail cron fairness fixture', 'start_date': day, 'safety_delay_hours': 0,
    'invoice_client_id': 'qa-detail-stream-only'})
exports = env['ab_tax_eta_archive_export']
try:
    env['ab_tax_eta_archive_sync'].create([
        {'config_id': config.id, 'report_date': day, 'kind': kind, 'direction': direction, 'state': 'done'}
        for kind in ('invoice', 'receipt') for direction in ('sent', 'received')])
    documents = {}
    for kind, age in (('invoice', 1), ('receipt', 3)):
        stamp = api_stamp(day_bounds(today - timedelta(days=age))[0] + timedelta(hours=1))
        model = env['ab_tax_eta_archive_' + kind]
        documents[kind] = model.create(model._eta_values({
            'uuid': 'qa-cron-' + kind, 'dateTimeIssued': stamp, 'dateTimeReceived': stamp}, 'sent', config))
    exports._ensure_files(config, day)
    env.cr.commit()

    def response(method, url, **kwargs):
        if url.endswith('/api/v1/receipts/qa-cron-limited/raw'):
            result = requests.Response()
            result.status_code = 429
            result._content_consumed = True
            result.url = url
            result._content = b'{}'
            result.headers['Retry-After'] = '120'
            return result
        assert url.endswith('/api/v1/receipts/qa-cron-receipt/raw'), 'Invoice backlog must not be fetched here'
        result = requests.Response()
        result.status_code = 200
        result._content_consumed = True
        result.url = url
        result._content = json.dumps({'receipt': {
            'seller': {}, 'documentType': {'receiptType': 's'}, 'itemData': [],
            'totalAmount': 10, 'currency': 'EGP', 'taxTotals': [{'taxType': 'T1', 'amount': 1.4}]}}).encode()
        return result

    with patch.object(type(config), '_eta_auth_headers', return_value=('https://eta.invalid', {})), \
         patch('requests.sessions.Session.request', side_effect=response) as http:
        env.ref('ab_tax_eta_archive.cron_eta_receipt_uuid_details').method_direct_trigger()
        env.cr.commit()
        env.invalidate_all()
        assert http.call_count == 1
        assert documents['receipt'].detail_json
        assert not documents['invoice'].detail_json
        env.ref('ab_tax_eta_archive.cron_eta_prepare_files').method_direct_trigger()
        env.cr.commit()
        env.invalidate_all()
        export = exports._latest_day_files(config, day)['sent_receipt']
        assert export.generation_state == 'ready' and export.file_data
        assert (export.archived_count, export.details_ready, export.details_pending) == (1, 1, 0)
        assert export.file_verified_rows == 1 and export.detail_fetched_rows == 1
        env.ref('ab_tax_eta_archive.cron_eta_receipt_uuid_details').method_direct_trigger()
        env.cr.commit()
        assert http.call_count == 1, 'Completed details must not be fetched again'
        stamp = api_stamp(day_bounds(day)[0] + timedelta(hours=2))
        model = env['ab_tax_eta_archive_receipt']
        limited = model.create(model._eta_values({'uuid': 'qa-cron-limited', 'dateTimeIssued': stamp,
                                                  'dateTimeReceived': stamp}, 'sent', config))
        env.cr.commit()
        retry_before = datetime.utcnow() + timedelta(seconds=119)
        cron = env.ref('ab_tax_eta_archive.cron_eta_receipt_uuid_details')
        cron.method_direct_trigger()
        env.cr.commit()
        env.invalidate_all()
        assert http.call_count == 2 and not limited.detail_json
        assert env['ir.cron.trigger'].search([
            ('cron_id', '=', cron.id), ('call_at', '>=', retry_before)], limit=1)
    print('PASS actual receipt-details cron fetched older receipts despite newer invoice backlog, '
          'generated a nonempty file, and scheduled a provider-cooldown retry')
finally:
    config.active = False
    env.cr.commit()
