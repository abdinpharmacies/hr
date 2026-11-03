import base64
import binascii
import hashlib
import io
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytz

import requests
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CATEGORIES = (
    ('received_invoice', 'Invoices received', 'invoice', 'received'),
    ('sent_invoice', 'Invoices sent', 'invoice', 'sent'),
    ('sent_receipt', 'Receipts sent', 'receipt', 'sent'),
    ('received_receipt', 'Receipts received', 'receipt', 'received'),
)
EXPORT_FORMAT_VERSION = 2

INVOICE_HEADERS = ('مسلسل', 'تفاصيل', 'نوع المستند', 'نسخة المستند', 'الحالة',
                   'تاريخ الإصدار', 'تاريخ التقديم', 'عملة الفاتورة', 'إجمالى المبيعات',
                   'قيمة الفاتورة', 'ضريبة القيمة المضافة', 'T1%', 'خصم الفاتورة',
                   'إجمالى الفاتورة', 'الرقم الداخلى', 'الرقم الإلكترونى',
                   'الرقم الضريبى للبائع', 'إسم البائع', 'عنوان البائع',
                   'الرقم الضريبى للمشترى', 'إسم المشترى', 'عنوان المشترى',
                   'مرجع طلب الشراء', 'وصف طلب الشراء', 'مرجع طلب المبيعات',
                   'وصف طلب المبيعات', 'التوقيع الإلكترونى', 'الرابط الخارجى')
PURCHASE_HEADERS = INVOICE_HEADERS[:11] + (
    'T1%', 'ضريبة الجدول النسبية', 'T2%', 'الخصم تحت حساب الضريبة', 'T4%',
    'رسوم أخرى', 'T12%', 'خصم الفاتورة', 'خصم إضافى', 'إجمالى الفاتورة',
    'الرقم الداخلى', 'الرقم الإلكترونى', 'الرقم الضريبى للبائع', 'إسم البائع',
    'عنوان البائع', 'الرقم الضريبى للمشترى', 'إسم المشترى', 'عنوان المشترى',
    'مرجع طلب الشراء', 'وصف طلب الشراء', 'مرجع طلب المبيعات',
    'وصف طلب المبيعات', 'التوقيع الإلكترونى', 'الرابط الخارجى', 'خدمة التوصيل')
RECEIPT_HEADERS = ('مسلسل', 'تفاصيل', 'نوع الإيصال', 'الحالة', 'تاريخ الإصدار',
                   'تاريخ الإستلام', 'عملة الإيصال', 'سعر الصرف', 'المبيعات',
                   'خصم تجارى', 'قيمة الإيصال', 'ضريبة القيمة المضافة',
                   'خصم الأصناف', 'إجمالى الإيصال', 'رقم الإيصال',
                   'الرقم الإلكترونى', 'سيريال نقطة البيع', 'إسم نقطة البيع',
                   'الرقم الضريبى للبائع', 'إسم البائع', 'عنوان البائع',
                   'الرقم الضريبى للمشترى', 'إسم المشترى', 'رقم المشترى')


def _address(value):
    if not isinstance(value, dict):
        return ''
    return ' '.join(str(value[key]).strip() for key in (
        'buildingNumber', 'street', 'regionCity', 'governate', 'country') if value.get(key))


def _taxes(value):
    totals = value if isinstance(value, list) else []
    return {code: sum(float(item.get('amount') or 0) for item in totals
                      if isinstance(item, dict) and item.get('taxType') == code)
            for code in ('T1', 'T2', 'T4', 'T12')}


def _tax_rates(lines):
    result = {}
    for line in lines if isinstance(lines, list) else []:
        for tax in (line.get('taxableItems') or []) if isinstance(line, dict) else []:
            if isinstance(tax, dict) and tax.get('taxType') in ('T1', 'T2', 'T4', 'T12'):
                result.setdefault(tax['taxType'], tax.get('rate'))
    return result


def _signature_name(signatures, fallback):
    for item in signatures if isinstance(signatures, list) else []:
        if not isinstance(item, dict):
            continue
        if item.get('signerName') or item.get('name'):
            return item.get('signerName') or item.get('name')
        if not item.get('value'):
            continue
        try:
            from cryptography.hazmat.primitives.serialization import pkcs7
            from cryptography.x509.oid import NameOID
            certificates = pkcs7.load_der_pkcs7_certificates(
                base64.b64decode(item['value']))
            for certificate in certificates:
                names = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                if names and certificate.subject != certificate.issuer:
                    return names[0].value
        except (ImportError, ValueError, TypeError, binascii.Error):
            continue
    return fallback


def _detail_values(payload, kind):
    body = payload.get('document' if kind == 'invoice' else 'receipt') or {}
    if not isinstance(body, dict) or not body:
        raise ValueError('ETA detail response has no document object')
    issuer = body.get('issuer' if kind == 'invoice' else 'seller') or {}
    receiver = body.get('receiver' if kind == 'invoice' else 'buyer') or {}
    if not isinstance(issuer, dict) or not isinstance(receiver, dict):
        raise ValueError('ETA detail response has invalid parties')
    if kind == 'invoice':
        lines = body.get('invoiceLines') or []
        first_unit = next((line.get('unitValue') for line in lines
                           if isinstance(line, dict) and isinstance(line.get('unitValue'), dict)), {})
        signatures = body.get('signatures') or []
        signature = _signature_name(signatures, payload.get('issuerName') or issuer.get('name'))
        return {
            'version': payload.get('typeVersionName') or body.get('documentTypeVersion'),
            'currency': first_unit.get('currencySold') or 'EGP',
            'sales': body.get('totalSalesAmount', payload.get('totalSales')),
            'net': body.get('netAmount', payload.get('netAmount')),
            'taxes': _taxes(body.get('taxTotals')),
            'rates': _tax_rates(lines),
            'discount': body.get('totalDiscountAmount', payload.get('totalDiscount')),
            'extra_discount': body.get('extraDiscountAmount'),
            'total': body.get('totalAmount', payload.get('total')),
            'issuer_address': _address(issuer.get('address')),
            'receiver_address': _address(receiver.get('address')),
            'purchase_ref': body.get('purchaseOrderReference'),
            'purchase_description': body.get('purchaseOrderDescription'),
            'sales_ref': body.get('salesOrderReference'),
            'sales_description': body.get('salesOrderDescription'),
            'signature': signature,
            'long_id': payload.get('longId'),
            'delivery': (body.get('delivery') or {}).get('approach')
                        if isinstance(body.get('delivery'), dict) else None,
        }
    document_type = body.get('documentType') or {}
    seller_address = issuer.get('branchAddress') or {}
    return {
        'type': document_type.get('receiptTypeNameAr') or document_type.get('receiptTypeName')
                if isinstance(document_type, dict) else None,
        'type_code': document_type.get('receiptType') if isinstance(document_type, dict) else None,
        'currency': body.get('currency'),
        'exchange_rate': body.get('exchangeRate'),
        'sales': body.get('totalSales'),
        'commercial_discount': body.get('totalCommercialDiscount'),
        'net': body.get('netAmount'),
        'taxes': _taxes(body.get('taxTotals')),
        'items_discount': body.get('totalItemsDiscount'),
        'total': body.get('totalAmount'),
        'seller_name': issuer.get('sellerName'),
        'seller_id': issuer.get('sellerId'),
        'seller_address': _address(seller_address),
        'pos_name': payload.get('submitterName') or issuer.get('branchNameAr') or issuer.get('branchName'),
        'pos_serial': issuer.get('deviceSerialNumber'),
        'buyer_name': receiver.get('buyerName'),
        'buyer_id': receiver.get('buyerId'),
        'buyer_number': receiver.get('mobileNumber'),
        'long_id': body.get('longId') or payload.get('longId'),
    }


def _excel_cell(value):
    text = '' if value is None or value is False else str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


class EtaExport(models.Model):
    _name = 'ab_tax_eta_archive_export'
    _description = 'ETA Daily File'
    _order = 'report_date desc, category'

    config_id = fields.Many2one('ab_tax_eta_archive_config', required=True, ondelete='restrict')
    report_date = fields.Date(string='Issue Date', required=True, index=True)
    category = fields.Selection([(item[0], item[1]) for item in CATEGORIES], required=True)
    revision = fields.Integer(required=True, default=1, readonly=True)
    supersedes_id = fields.Many2one('ab_tax_eta_archive_export', readonly=True, ondelete='restrict')
    source_digest = fields.Char(readonly=True)
    export_format_version = fields.Integer(readonly=True)
    filename = fields.Char(required=True, readonly=True)
    file_data = fields.Binary(attachment=True, readonly=True)
    file_size_mb = fields.Float(string='File Size (MB)', digits=(16, 2), readonly=True)
    record_count = fields.Integer(readonly=True)
    checked_through = fields.Date(string='Submission Days Checked Through', readonly=True)
    telegram_sent_at = fields.Datetime(readonly=True)
    telegram_message_id = fields.Char(readonly=True)
    telegram_error = fields.Char(readonly=True)
    telegram_send_requested = fields.Boolean(string='Telegram Delivery Queued', readonly=True)

    _unique_file = models.Constraint(
        'UNIQUE(config_id, report_date, category, revision)',
        'Only one ETA file revision is allowed per day and category.')

    @api.model
    def _cron_export_and_send(self):
        cairo = pytz.timezone('Africa/Cairo')
        today = datetime.now(cairo).date()
        cutoff = today - timedelta(days=4)
        for config in self.env['ab_tax_eta_archive_config'].search([
            ('active', '=', True), ('start_date', '<', today),
        ]):
            yesterday_runs = self.env['ab_tax_eta_archive_sync'].search([
                ('config_id', '=', config.id),
                ('report_date', '=', today - timedelta(days=1)),
                ('state', '=', 'done'),
            ])
            if len(yesterday_runs) != 4 or any(
                    not run.last_run_at or
                    fields.Datetime.to_datetime(run.last_run_at).replace(
                        tzinfo=timezone.utc).astimezone(cairo).date() < today
                    for run in yesterday_runs):
                continue
            queued_recent = self.search([
                ('config_id', '=', config.id), ('report_date', '>', cutoff),
                ('report_date', '<', today), ('telegram_send_requested', '=', True),
                ('telegram_sent_at', '=', False),
            ])
            for queued_day in sorted(set(queued_recent.mapped('report_date')), reverse=True):
                if not self._day_complete(config, queued_day):
                    continue
                if not self._ensure_files(config, queued_day):
                    continue
                latest = self._latest_day_files(config, queued_day)
                for category, _label, _kind, _direction in CATEGORIES:
                    export = latest[category]
                    if export.telegram_send_requested and not export.telegram_sent_at:
                        export.telegram_send_requested = False
                        export._send_telegram(checked_through=today - timedelta(days=1))
                if (self.env.context.get('cron_id') and
                        not self.env['ir.cron']._commit_progress(1, remaining=1)):
                    return
            day = cutoff
            while day >= config.start_date:
                if not self._day_complete(config, day):
                    day -= timedelta(days=1)
                    continue
                latest = self._latest_day_files(config, day)
                if (all(latest.get(category) and latest[category].telegram_sent_at
                        for category, _label, _kind, _direction in CATEGORIES) and
                        not self._sent_files_need_revision(config, day, latest)):
                    day -= timedelta(days=1)
                    continue
                if not self._ensure_files(config, day):
                    if (self.env.context.get('cron_id') and
                            not self.env['ir.cron']._commit_progress(
                                0, remaining=(day - config.start_date).days + 1)):
                        return
                    day -= timedelta(days=1)
                    continue
                latest = self._latest_day_files(config, day)
                for category, _label, _kind, _direction in CATEGORIES:
                    export = latest[category]
                    if (not export.telegram_sent_at and
                            (day >= (config.telegram_start_date or cutoff) or
                             export.telegram_send_requested or
                             (export.supersedes_id and export.supersedes_id.telegram_sent_at))):
                        if export.telegram_send_requested:
                            export.telegram_send_requested = False
                        export._send_telegram(checked_through=today - timedelta(days=1))
                if self.env.context.get('cron_id') and not self.env['ir.cron']._commit_progress(
                        1, remaining=(day - config.start_date).days):
                    return
                day -= timedelta(days=1)

    @api.model
    def _latest_day_files(self, config, day):
        exports = self.search([('config_id', '=', config.id),
                               ('report_date', '=', day)], order='revision desc')
        latest = {}
        for export in exports:
            latest.setdefault(export.category, export)
        return latest

    @api.model
    def _sent_files_need_revision(self, config, day, latest):
        for category, _label, kind, direction in CATEGORIES:
            export = latest.get(category)
            if not export or not export.telegram_sent_at:
                continue
            model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice'
                             else 'ab_tax_eta_archive_receipt']
            count = model.search_count([
                ('config_id', '=', config.id), ('report_date', '=', day),
                ('direction', '=', direction),
            ])
            if count != export.record_count:
                return True
        return False

    @api.model
    def _ensure_files(self, config, report_date):
        if not self._day_complete(config, report_date):
            return False
        checked_through = datetime.now(pytz.timezone('Africa/Cairo')).date() - timedelta(days=1)
        latest = self._latest_day_files(config, report_date)
        targets = []
        for category, _label, kind, direction in CATEGORIES:
            export = latest.get(category)
            if export and export.telegram_sent_at:
                model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice'
                                 else 'ab_tax_eta_archive_receipt']
                count = model.search_count([
                    ('config_id', '=', config.id), ('report_date', '=', report_date),
                    ('direction', '=', direction),
                ])
                if count == export.record_count:
                    continue
            targets.append((category, kind, direction, export))
        for _category, kind, direction, _export in targets:
            if not self._enrich_details(config, kind, report_date, direction):
                return False
        for category, kind, direction, export in targets:
            current = self._prepare(config, report_date, category, kind, direction,
                                    export=export)
            if not current:
                return False
            if current.checked_through != checked_through:
                current.checked_through = checked_through
        return True

    @api.model
    def _day_complete(self, config, report_date):
        today = datetime.now(pytz.timezone('Africa/Cairo')).date()
        first_day = max(config.start_date, report_date)
        if first_day >= today:
            return False
        complete_days = (today - first_day).days
        return self.env['ab_tax_eta_archive_sync'].search_count([
            ('config_id', '=', config.id),
            ('report_date', '>=', first_day), ('report_date', '<', today),
            ('state', '=', 'done'),
        ]) == complete_days * 4

    def action_send_telegram(self):
        self.check_access('write')
        unsent = self.filtered(lambda export: not export.telegram_sent_at)
        for export in unsent:
            if not self._day_complete(export.config_id, export.report_date):
                raise UserError(_(
                    'All four ETA retrievals for this day must finish before sending its file.'))
        for export in unsent:
            export = export.try_lock_for_update().filtered_domain([
                ('telegram_sent_at', '=', False),
            ])
            if not export:
                continue
            latest = self.search([
                ('config_id', '=', export.config_id.id),
                ('report_date', '=', export.report_date),
                ('category', '=', export.category),
            ], order='revision desc', limit=1)
            if latest != export:
                continue
            export.write({'telegram_send_requested': True, 'telegram_error': False})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model
    def _detail_headers(self, config, kind):
        receipt_pos = kind == 'receipt' and config.receipt_auth_mode == 'pos'
        client_id = config.receipt_client_id if receipt_pos else config.invoice_client_id
        client_secret = config.receipt_client_secret if receipt_pos else config.invoice_client_secret
        if not client_id or not client_secret:
            raise UserError(_('Configure ETA credentials before retrieving export details.'))
        identity_url, api_url = config._base_urls()
        request = self.env['ab_tax_eta_archive_sync']._request
        options = {}
        data = {'grant_type': 'client_credentials'}
        if receipt_pos:
            required = (config.pos_serial, config.pos_os_version,
                        config.pos_model_framework, config.pos_preshared_key)
            if not all(required):
                raise UserError(_('Configure all ETA POS authentication headers.'))
            options['headers'] = dict(zip(
                ('posserial', 'pososversion', 'posmodelframework', 'presharedkey'), required))
            data.update({'client_id': client_id, 'client_secret': client_secret})
        else:
            options['auth'] = (client_id, client_secret)
        token = request('POST', f'{identity_url}/connect/token', data=data,
                        **options).get('access_token')
        if not token:
            raise UserError(_('ETA authentication returned no access token.'))
        return api_url, {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}

    @api.model
    def _enrich_details(self, config, kind, report_date, direction):
        model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice' else 'ab_tax_eta_archive_receipt']
        base_domain = [
            ('config_id', '=', config.id), ('report_date', '=', report_date),
            ('direction', '=', direction), ('detail_json', '=', False),
        ]
        retry_before = fields.Datetime.now() - timedelta(hours=1)
        missing = model.search(base_domain + [
            '|', ('detail_attempt_at', '=', False),
            ('detail_attempt_at', '<', retry_before),
        ], order='detail_attempt_at, issued_at, uuid', limit=81)
        if not missing:
            return not model.search_count(base_domain)
        api_url, headers = self._detail_headers(config, kind)
        request = self.env['ab_tax_eta_archive_sync']._request
        for record in self._progress_iter(missing[:80], _('Retrieving ETA export details'),
                                          total=min(len(missing), 80)):
            path = ('api/v1.0/documents' if kind == 'invoice' else 'api/v1/receipts')
            try:
                time.sleep(0.51)
                payload = request('GET', f'{api_url}/{path}/{quote(record.uuid, safe="")}/raw',
                                  headers=headers)
                if not isinstance(payload, dict):
                    raise ValueError('ETA detail response is not an object')
                values = _detail_values(payload, kind)
                record.write({'detail_json': json.dumps(values, ensure_ascii=False,
                                                        sort_keys=True), 'detail_error': False,
                              'detail_attempt_at': fields.Datetime.now()})
            except (UserError, ValueError, requests.RequestException) as exc:
                record.write({'detail_error': str(exc)[:500],
                              'detail_attempt_at': fields.Datetime.now()})
                _logger.warning('ETA export detail failed for %s: %s', record.uuid, exc)
        return not model.search_count(base_domain)

    def _progress_iter(self, data, message, total=None):
        progress_iter = getattr(self, 'web_progress_iter', None)
        if progress_iter:
            return progress_iter(data, msg=message, total=total, cancellable=False)
        return data

    @api.model
    def _prepare(self, config, report_date, category, kind, direction, export=None):
        if not self._enrich_details(config, kind, report_date, direction):
            return False
        model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice' else 'ab_tax_eta_archive_receipt']
        records = model.search([('config_id', '=', config.id), ('report_date', '=', report_date),
                                ('direction', '=', direction)],
                               order=('issued_at desc, uuid' if direction == 'sent' else
                                      'issued_at, uuid'))
        headers = (RECEIPT_HEADERS if kind == 'receipt' else
                   PURCHASE_HEADERS if direction == 'received' else INVOICE_HEADERS)
        cairo = pytz.timezone('Africa/Cairo')

        def local_time(value):
            parsed = fields.Datetime.to_datetime(value) if value else None
            return (pytz.utc.localize(parsed).astimezone(cairo).replace(tzinfo=None)
                    if parsed else None)

        def export_cells(record, serial):
            summary = json.loads(record.raw_json or '{}')
            detail = json.loads(record.detail_json)
            long_id = detail.get('long_id')
            link = (f'https://invoicing.eta.gov.eg/documents/{quote(record.uuid, safe="")}/share/{quote(str(long_id), safe="")}'
                    if long_id and kind == 'invoice' else '')
            if kind == 'receipt':
                receipt_type = {'s': 'ايصال بيع', 'r': 'ايصال مرتجع'}.get(
                    (detail.get('type_code') or '').lower(),
                    detail.get('type') or record.document_type)
                return [serial, 'عرض', receipt_type,
                        record.status, local_time(record.issued_at), local_time(record.received_at),
                        detail.get('currency') or record.currency, detail.get('exchange_rate'),
                        detail.get('sales'), detail.get('commercial_discount'),
                        detail.get('net'), detail['taxes'].get('T1'),
                        detail.get('items_discount'), detail.get('total'),
                        record.receipt_number, record.uuid,
                        detail.get('pos_serial') or record.pos_serial_number,
                        detail.get('pos_name') or summary.get('submitterName'),
                        detail.get('seller_id') or record.issuer_id,
                        detail.get('seller_name') or record.issuer_name,
                        detail.get('seller_address'), detail.get('buyer_id') or record.receiver_id,
                        detail.get('buyer_name') or record.receiver_name,
                        detail.get('buyer_number')]
            document_type = {'i': 'فاتورة', 'c': 'اشعار دائن',
                             'd': 'اشعار مدين'}.get(record.document_type,
                                                    summary.get('documentTypeNamePrimaryLanguage') or
                                                    record.document_type)
            common = [serial, 'عرض', document_type, detail.get('version'), record.status,
                      local_time(record.issued_at), local_time(record.received_at),
                      detail.get('currency') or record.currency,
                      detail.get('sales'), detail.get('net'), detail['taxes'].get('T1'),
                      detail['rates'].get('T1')]
            suffix = [detail.get('total'), record.internal_id, record.uuid,
                      record.issuer_id, record.issuer_name, detail.get('issuer_address'),
                      record.receiver_id, record.receiver_name, detail.get('receiver_address'),
                      detail.get('purchase_ref'), detail.get('purchase_description'),
                      detail.get('sales_ref'), detail.get('sales_description'),
                      detail.get('signature'), link]
            if direction == 'received':
                return common + [detail['taxes'].get('T2'), detail['rates'].get('T2'),
                                 detail['taxes'].get('T4'), detail['rates'].get('T4'),
                                 detail['taxes'].get('T12'), detail['rates'].get('T12'),
                                 detail.get('discount'), detail.get('extra_discount')] + suffix + [detail.get('delivery')]
            return common + [detail.get('discount')] + suffix

        digest = hashlib.sha256()
        for serial, record in enumerate(records, start=1):
            digest.update(json.dumps(export_cells(record, serial), ensure_ascii=False,
                                     default=str).encode('utf-8'))
            digest.update(b'\n')
        source_digest = digest.hexdigest()
        if (export and export.source_digest == source_digest and export.file_data and
                export.export_format_version == EXPORT_FORMAT_VERSION):
            return export

        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(title='الايصالات' if kind == 'receipt' else
                                     'المشتريات' if direction == 'received' else 'الفواتير')
        sheet.sheet_view.rightToLeft = True
        widths = ([6.55, 6.44, 9.33, 5.55, 11, 11.11, 10.44, 9.44,
                   7.33, 10.11, 10.11, 16.33, 11.66, 11.55, 9.33, 67.89,
                   13.55, 15.33, 14.44, 16.66, 38.11, 16.55, 10.11, 9.66]
                  if kind == 'receipt' else
                  [6.55, 6.44, 9.33, 11.33, 5.55, 11, 10.66, 10,
                   12.44, 11, 16.33, 4.55, 16.44, 4.55, 21.89, 4.55,
                   8.89, 5.55, 10.55, 9.55, 11.11, 17, 31.66, 14.44,
                   26.89, 64.66, 16.55, 21, 57.33, 18, 14.11, 16,
                   16.33, 25.89, 125, 11.33] if direction == 'received' else
                  [6.55, 6.44, 9.33, 11.33, 5.55, 11, 10.66, 10,
                   14, 11.11, 17.89, 6, 12, 12.55, 10, 32.66,
                   14.44, 16.66, 50.55, 16.55, 17.33, 42.89,
                   13.89, 14.11, 16, 16.33, 50, 125.89])
        for column, width in enumerate(widths[:len(headers)], start=1):
            sheet.column_dimensions[get_column_letter(column)].width = width
        thin = Side(style='thin', color='000000')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        header_cells = [WriteOnlyCell(sheet, value=value) for value in headers]
        for cell in header_cells:
            cell.font = Font(name='Calibri', size=11)
            cell.border = border
            cell.alignment = Alignment(horizontal='center')
        sheet.append(header_cells)
        for serial, record in enumerate(records, start=1):
            cells = export_cells(record, serial)
            cells = [_excel_cell(value) if isinstance(value, str) else value for value in cells]
            row = []
            for index, value in enumerate(cells):
                cell = WriteOnlyCell(sheet, value=value)
                cell.font = Font(name='Calibri', size=11)
                cell.border = border
                cell.alignment = Alignment(horizontal='center')
                if index in ((4, 5) if kind == 'receipt' else (5, 6)):
                    cell.number_format = 'mm-dd-yy'
                if index == 1:
                    cell.font = Font(name='Comic Sans MS', size=12, bold=True,
                                     underline='single')
                    if kind == 'invoice' and cells[-1 if direction == 'sent' else -2]:
                        cell.hyperlink = cells[-1 if direction == 'sent' else -2]
                if kind == 'invoice' and index == len(cells) - (1 if direction == 'sent' else 2) and value:
                    cell.hyperlink = value
                row.append(cell)
            sheet.append(row)
        output = io.BytesIO()
        workbook.save(output)
        revision = export.revision + 1 if export and export.telegram_sent_at else (export.revision if export else 1)
        filename = f'{category}_{report_date}_r{revision}.xlsx'
        values = {
            'config_id': config.id, 'report_date': report_date,
            'category': category, 'revision': revision, 'filename': filename,
            'file_data': base64.b64encode(output.getbuffer()),
            'file_size_mb': round(output.tell() / (1024 * 1024), 2),
            'record_count': len(records), 'source_digest': source_digest,
            'export_format_version': EXPORT_FORMAT_VERSION,
        }
        if export and not export.telegram_sent_at:
            export.write(values)
            return export
        if export:
            values['supersedes_id'] = export.id
        return self.create(values)

    def _send_telegram(self, checked_through=None):
        self.ensure_one()
        locked = self.try_lock_for_update().filtered_domain([('telegram_sent_at', '=', False)])
        if not locked:
            return
        self = locked
        config = self.config_id
        if not (config.telegram_bot_token or '').strip() or not (config.telegram_chat_id or '').strip():
            self.telegram_error = _('Configure the Telegram bot token and group chat ID.')
            return
        chat_id = config.telegram_chat_id.strip()
        if (chat_id.startswith(('+', 't.me/', 'http://t.me/', 'https://t.me/',
                                'telegram.me/', 'https://telegram.me/'))):
            self.telegram_error = _(
                'Use the numeric Telegram group chat ID or public @username, not an invite link.')
            return
        if not (chat_id.startswith('@') or
                (chat_id.startswith('-') and chat_id[1:].isdigit())):
            self.telegram_error = _(
                'Use a negative Telegram group chat ID or public @username for delivery.')
            return
        label = next(row[1] for row in CATEGORIES if row[0] == self.category)
        caption = f'{_(label)} - {self.report_date}'
        if self.revision > 1:
            caption += ' - ' + _('Revision %(number)s', number=self.revision)
        if not self.file_data:
            self.telegram_error = _('The ETA file has no content to send.')
            return
        try:
            document = base64.b64decode(self.file_data)
        except (binascii.Error, ValueError):
            self.telegram_error = _('The ETA file content is invalid.')
            return
        if len(document) > 50 * 1024 * 1024:
            self.telegram_error = _(
                'The ETA file is %(size)s MB and exceeds the Telegram upload limit of 50 MB.',
                size=f'{len(document) / (1024 * 1024):.1f}')
            return
        try:
            for attempt in range(3):
                response = requests.post(
                    f'https://api.telegram.org/bot{config.telegram_bot_token.strip()}/sendDocument',
                    data={'chat_id': chat_id, 'caption': caption},
                    files={'document': (
                        self.filename, document,
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
                    timeout=60,
                )
                try:
                    payload = response.json()
                except ValueError:
                    payload = {}
                if response.ok and isinstance(payload, dict) and payload.get('ok'):
                    break
                detail = payload.get('description') if isinstance(payload, dict) else None
                detail = ' '.join(str(detail or response.reason or response.status_code).split())[:300]
                detail = detail.replace(config.telegram_bot_token.strip(), '***')
                parameters = payload.get('parameters') if isinstance(payload, dict) else None
                retry_after = parameters.get('retry_after') if isinstance(parameters, dict) else None
                if response.status_code == 429 and attempt < 2:
                    try:
                        delay = int(retry_after)
                    except (TypeError, ValueError):
                        delay = 2 ** attempt
                    if delay <= 5:
                        time.sleep(max(delay, 1))
                        continue
                self.telegram_error = _(
                    'Telegram HTTP %(status)s: %(detail)s',
                    status=response.status_code, detail=detail)
                _logger.warning('ETA Telegram delivery failed for %s: HTTP %s: %s',
                                self.filename, response.status_code, detail)
                return
        except requests.Timeout:
            self.telegram_error = _('Telegram request timed out; check the chat before retrying.')
            _logger.warning('ETA Telegram delivery timed out for %s', self.filename)
            return
        except requests.RequestException as exc:
            self.telegram_error = _(
                'Telegram connection failed: %(reason)s', reason=type(exc).__name__)
            _logger.warning('ETA Telegram connection failed for %s: %s',
                            self.filename, type(exc).__name__)
            return
        values = {'telegram_sent_at': fields.Datetime.now(),
                  'telegram_message_id': str(payload.get('result', {}).get('message_id', '')),
                  'telegram_error': False}
        if checked_through:
            values['checked_through'] = checked_through
        self.write(values)
