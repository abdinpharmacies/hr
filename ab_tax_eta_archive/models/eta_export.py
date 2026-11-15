import base64
import binascii
import hashlib
import io
import json
import logging
import time
from functools import partial
from itertools import groupby
from datetime import datetime, timedelta
from urllib.parse import quote

import pytz

import requests
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .eta_sync import EtaRequestDeferred, eta_task_lock

_logger = logging.getLogger(__name__)

CATEGORIES = (
    ('received_invoice', 'Invoices received', 'invoice', 'received'),
    ('sent_invoice', 'Invoices sent', 'invoice', 'sent'),
    ('sent_receipt', 'Receipts sent', 'receipt', 'sent'),
    ('received_receipt', 'Receipts received', 'receipt', 'received'),
)
EXPORT_FORMAT_VERSION = 2
ETA_DETAIL_BATCH_SIZE = 80
ETA_DETAIL_ORDER = 'report_date desc, issued_at desc NULLS LAST, id desc'

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
    key = 'document' if kind == 'invoice' else 'receipt'
    body = payload.get(key)
    if not body and isinstance(payload.get('result'), dict):
        payload = payload['result']
        body = payload.get(key)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError as exc:
            raise ValueError(f'ETA {kind}: {key} contains invalid JSON text') from exc
    markers = (('issuer', 'receiver', 'invoiceLines') if kind == 'invoice'
               else ('seller', 'documentType', 'itemData'))
    if not body and all(marker in payload for marker in markers):
        body = payload
    if not isinstance(body, dict):
        raise ValueError(
            f'ETA {kind}: {key} object missing; body_type={type(body).__name__}; '
            f'response_keys={",".join(sorted(str(name) for name in payload)[:20])}')
    missing_fields = [marker for marker in markers if marker not in body]
    if missing_fields:
        raise ValueError(
            f'ETA {kind}: {key} missing fields={",".join(missing_fields)}; '
            f'body_keys={",".join(sorted(str(name) for name in body)[:20])}')
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
    source_updated_at = fields.Datetime(string='Source Updated At', readonly=True, copy=False)
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
    def _cron_fetch_details(self, kind='invoice'):
        if kind not in ('invoice', 'receipt'):
            raise ValueError('Unsupported ETA stream')
        with eta_task_lock(self.env, 1) as acquired:
            if not acquired:
                _logger.info('ETA detail queue already running; skipping duplicate %s task', kind)
                if self.env.context.get('cron_id'):
                    self.env['ir.cron']._commit_progress(remaining=0)
                return
            handoff = self._fetch_details_batch(kind)
        # Notify the next worker only after releasing the queue lock; an early
        # notification could make it consume the trigger while the lock is busy.
        if handoff:
            self._wake_detail_cron(handoff)
            if self.env.context.get('cron_id'):
                self.env['ir.cron']._commit_progress(remaining=0)

    @api.model
    def _detail_queue_domain(self, config_ids, today):
        retry_before = fields.Datetime.now() - timedelta(minutes=5)
        return (fields.Domain('config_id', 'in', config_ids) &
                fields.Domain('report_date', '<=', today) &
                (fields.Domain('detail_json', '=', False) |
                 fields.Domain('detail_json', '=', '')) &
                (fields.Domain('detail_attempt_at', '=', False) |
                 fields.Domain('detail_error', '=', False) |
                 fields.Domain('detail_attempt_at', '<', retry_before)))

    @api.model
    def _next_detail_work(self, domain):
        candidates = []
        for kind in ('invoice', 'receipt'):
            head = self.env['ab_tax_eta_archive_' + kind].search(
                domain, order=ETA_DETAIL_ORDER, limit=1)
            if head:
                candidates.append((head.report_date, kind == 'invoice', kind))
        if not candidates:
            return None
        day, _invoice_first, kind = max(candidates)
        return kind, day

    @api.model
    def _wake_detail_cron(self, kind):
        xmlid = ('cron_eta_uuid_details' if kind == 'invoice'
                 else 'cron_eta_receipt_uuid_details')
        self._wake_cron(xmlid)

    @api.model
    def _wake_cron(self, xmlid):
        if not self.env.context.get('cron_id'):
            return
        cron = self.env.ref('ab_tax_eta_archive.' + xmlid)
        if not self.env['ir.cron.trigger'].sudo().search([
                ('cron_id', '=', cron.id), ('call_at', '<=', fields.Datetime.now())], limit=1):
            cron._trigger()

    @api.model
    def _fetch_details_batch(self, kind):
        now = datetime.now(pytz.timezone('Africa/Cairo'))
        today = now.date()
        deadline = min(time.monotonic() + 25,
                       self.env.context.get('cron_end_time', float('inf')) - 2)
        if time.monotonic() >= deadline:
            if self.env.context.get('cron_id'):
                self.env['ir.cron']._commit_progress(remaining=1)
            return
        configs = self.env['ab_tax_eta_archive_config'].search([('active', '=', True)])
        domain = self._detail_queue_domain(configs.ids, today)
        next_work = self._next_detail_work(domain)
        if not next_work or next_work[0] != kind:
            if self.env.context.get('cron_id'):
                self.env['ir.cron']._commit_progress(remaining=0)
            return next_work[0] if next_work else None
        model = self.env['ab_tax_eta_archive_' + kind]
        selected_batch = model.search(
            domain & fields.Domain('report_date', '=', next_work[1]),
            order=ETA_DETAIL_ORDER, limit=ETA_DETAIL_BATCH_SIZE)
        progress_offset = 0
        if selected_batch:
            # Group only consecutive rows; grouping every row by direction would
            # move an older sent document ahead of a newer received document.
            groups = [(key, [record.id for record in rows]) for key, rows in groupby(
                selected_batch, key=lambda record: (
                    record.config_id.id, record.report_date, record.direction))]
            _logger.info('ETA UUID detail selection: kind=%s selected=%s groups=%s',
                         kind, len(selected_batch), len(groups))
            progress_offset = 0
            auth_cache = {}
            # One connection pool and authentication per connection for the whole slice.
            with requests.Session() as session:
                progress_message = self._detail_progress_message(
                    kind, selected_batch[0].direction, selected_batch[0].report_date)
                try:
                    for (config_id, report_date, direction), record_ids in groups:
                        if time.monotonic() >= deadline:
                            break
                        progress_message = self._detail_progress_message(kind, direction, report_date)
                        processed = self._enrich_details(
                            self.env['ab_tax_eta_archive_config'].browse(config_id),
                            kind, report_date, direction, deadline=deadline,
                            batch_size=len(record_ids), record_ids=record_ids,
                            progress_offset=progress_offset, progress_total=len(selected_batch),
                            session=session, auth_cache=auth_cache)
                        progress_offset += processed
                        if not processed:
                            break
                finally:
                    # Finish this callback's progress, not the remaining archive.
                    # Every cron slice gets a new progress code; leaving a partial
                    # slice ongoing makes the UI show stale duplicate operations.
                    progress = getattr(self, 'web_progress_percent', None)
                    if (progress and self.env.context.get('progress_code') and
                            progress_offset < len(selected_batch)):
                        try:
                            progress(100, msg=progress_message, cancellable=False)
                        except Exception:
                            _logger.exception('ETA detail batch progress could not be closed')
        next_work = self._next_detail_work(self._detail_queue_domain(configs.ids, today))
        if self.env.context.get('cron_id'):
            self.env['ir.cron']._commit_progress(
                remaining=int(bool(progress_offset) and bool(next_work) and next_work[0] == kind))
        return next_work[0] if next_work and next_work[0] != kind else None

    @api.model
    def _cron_prepare_files(self):
        with eta_task_lock(self.env, 2) as acquired:
            if not acquired:
                return
            self._prepare_files_batch()
        self._wake_cron('cron_eta_delivery')

    @api.model
    def _prepare_files_batch(self):
        cairo = pytz.timezone('Africa/Cairo')
        today = datetime.now(cairo).date()
        cutoff = today - timedelta(days=1)
        deadline = min(time.monotonic() + 25,
                       self.env.context.get('cron_end_time', float('inf')) - 2)
        for config in self.env['ab_tax_eta_archive_config'].search([
            ('active', '=', True), ('start_date', '<', today),
        ]):
            scan_date = config.file_scan_date
            day = scan_date if scan_date and config.start_date <= scan_date <= cutoff else cutoff
            while day >= config.start_date:
                if time.monotonic() >= deadline:
                    return
                config.file_scan_date = day
                self._ensure_files(config, day, deadline=deadline)
                if time.monotonic() >= deadline:
                    return
                # Advance even when a stream is blocked or has no activity. The next
                # sweep retries it, while older gaps retain a chance to be processed.
                config.file_scan_date = day - timedelta(days=1) if day > config.start_date else cutoff
                if self.env.context.get('cron_id') and not self.env['ir.cron']._commit_progress(
                        1, remaining=(day - config.start_date).days):
                    return
                day -= timedelta(days=1)

    @api.model
    def _cron_export_and_send(self):
        with eta_task_lock(self.env, 3) as acquired:
            if acquired:
                self._deliver_files_batch()

    @api.model
    def _deliver_files_batch(self):
        today = datetime.now(pytz.timezone('Africa/Cairo')).date()
        cutoff = today - timedelta(days=4)
        deadline = min(time.monotonic() + 25,
                       self.env.context.get('cron_end_time', float('inf')) - 2)
        for config in self.env['ab_tax_eta_archive_config'].search([('active', '=', True)]):
            delivery_start = max(config.start_date, config.telegram_start_date or config.start_date)
            domain = (fields.Domain('config_id', '=', config.id) &
                      fields.Domain('report_date', '<', today) &
                      ((fields.Domain('report_date', '>=', delivery_start) &
                        fields.Domain('report_date', '<=', cutoff)) |
                       fields.Domain('telegram_send_requested', '=', True)))
            seen = set()
            for export in self.search(domain, order='report_date desc, category, revision desc'):
                key = (export.report_date, export.category)
                if key in seen:
                    continue
                seen.add(key)
                if export.telegram_sent_at or not export.file_data:
                    continue
                if time.monotonic() >= deadline:
                    return
                if not export._file_source_ready():
                    self._wake_cron('cron_eta_prepare_files')
                    continue
                export._send_telegram(checked_through=export.report_date)
                if (self.env.context.get('cron_id') and
                        not self.env['ir.cron']._commit_progress(1, remaining=1)):
                    return

    def _file_source_ready(self):
        self.ensure_one()
        _category, _label, kind, direction = next(row for row in CATEGORIES if row[0] == self.category)
        if not self._day_complete(self.config_id, self.report_date, kind=kind, direction=direction):
            return False
        model = self.env['ab_tax_eta_archive_' + kind]
        domain = (fields.Domain('config_id', '=', self.config_id.id) &
                  fields.Domain('report_date', '=', self.report_date) &
                  fields.Domain('direction', '=', direction))
        [(count, updated_at)] = model._read_group(domain, [], ['__count', 'write_date:max'])
        return (count > 0 and count == self.record_count and
                self.source_updated_at == updated_at and
                self.export_format_version == EXPORT_FORMAT_VERSION and
                not model.search_count(domain & (
                    fields.Domain('detail_json', '=', False) | fields.Domain('detail_json', '=', ''))))

    @api.model
    def _latest_day_files(self, config, day):
        exports = self.search([('config_id', '=', config.id),
                               ('report_date', '=', day)], order='revision desc')
        latest = {}
        for export in exports:
            latest.setdefault(export.category, export)
        return latest

    @api.model
    def _ensure_files(self, config, report_date, deadline=None):
        checked_through = report_date
        latest = self._latest_day_files(config, report_date)
        targets = []
        prepared = set()
        for category, _label, kind, direction in CATEGORIES:
            if not self._day_complete(config, report_date, kind=kind, direction=direction):
                _logger.info('ETA file waiting for retrieval: connection=%s day=%s category=%s',
                             config.id, report_date, category)
                continue
            export = latest.get(category)
            model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice'
                             else 'ab_tax_eta_archive_receipt']
            [(count, updated_at)] = model._read_group([
                ('config_id', '=', config.id), ('report_date', '=', report_date),
                ('direction', '=', direction),
            ], [], ['__count', 'write_date:max'])
            if not count:
                continue
            if (export and export.file_data and count == export.record_count and
                    export.source_updated_at == updated_at and
                    export.export_format_version == EXPORT_FORMAT_VERSION):
                prepared.add(category)
                continue
            targets.append((category, kind, direction, export))
        for category, kind, direction, export in targets:
            model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice'
                             else 'ab_tax_eta_archive_receipt']
            pending_details = model.search_count([
                    ('config_id', '=', config.id), ('report_date', '=', report_date),
                    ('direction', '=', direction),
                    '|', ('detail_json', '=', False), ('detail_json', '=', '')])
            if pending_details:
                _logger.info('ETA file waiting for UUID details: connection=%s day=%s '
                             'category=%s pending=%s', config.id, report_date,
                             category, pending_details)
                continue
            if deadline is not None and time.monotonic() >= deadline:
                continue
            try:
                with self.env.cr.savepoint():
                    current = self._prepare(config, report_date, category, kind, direction,
                                            export=export)
            except (ValueError, TypeError, KeyError):
                _logger.exception('ETA file generation failed: connection=%s day=%s category=%s',
                                  config.id, report_date, category)
                continue
            if not current:
                continue
            if current.checked_through != checked_through:
                current.checked_through = checked_through
            prepared.add(category)
            if (self.env.context.get('cron_id') and
                    not self.env['ir.cron']._commit_progress(1, remaining=1)):
                return prepared
        return prepared

    @api.model
    def _day_complete(self, config, report_date, kind=None, direction=None):
        today = datetime.now(pytz.timezone('Africa/Cairo')).date()
        if report_date < config.start_date or report_date >= today:
            return False
        domain = [
            ('config_id', '=', config.id),
            ('report_date', '=', report_date),
            ('state', '=', 'done'),
        ]
        if kind:
            domain.append(('kind', '=', kind))
        if direction:
            domain.append(('direction', '=', direction))
        return self.env['ab_tax_eta_archive_sync'].search_count(domain) == (
            (1 if kind else 2) * (1 if direction else 2))

    def action_send_telegram(self):
        self.check_access('write')
        unsent = self.filtered(lambda export: not export.telegram_sent_at)
        for export in unsent:
            if not export.record_count:
                raise UserError(_('An empty ETA file cannot be sent. Wait for saved transactions.'))
            _category, _label, kind, direction = next(
                row for row in CATEGORIES if row[0] == export.category)
            if not self._day_complete(export.config_id, export.report_date,
                                      kind=kind, direction=direction):
                raise UserError(_(
                    'The ETA retrieval for this file must finish before sending.'))
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
    def _detail_headers(self, config, kind, session=None):
        return config._eta_auth_headers(kind, session=session)

    @api.model
    def _detail_progress_message(self, kind, direction, report_date):
        day = fields.Date.to_string(report_date)
        if kind == 'invoice':
            return (_('Retrieving ETA sent invoice details for %(date)s', date=day)
                    if direction == 'sent' else
                    _('Retrieving ETA received invoice details for %(date)s', date=day))
        return (_('Retrieving ETA sent receipt details for %(date)s', date=day)
                if direction == 'sent' else
                _('Retrieving ETA received receipt details for %(date)s', date=day))

    @api.model
    def _enrich_details(self, config, kind, report_date, direction, deadline=None,
                        batch_size=80, record_ids=None, progress_offset=0,
                        progress_total=None, session=None, auth_cache=None):
        if session is None:
            with requests.Session() as owned_session:
                return self._enrich_details(
                    config, kind, report_date, direction, deadline=deadline,
                    batch_size=batch_size, record_ids=record_ids,
                    progress_offset=progress_offset, progress_total=progress_total,
                    session=owned_session, auth_cache=auth_cache)
        auth_cache = auth_cache if auth_cache is not None else {}
        model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice' else 'ab_tax_eta_archive_receipt']
        base_domain = [
            ('config_id', '=', config.id), ('report_date', '=', report_date),
            ('direction', '=', direction),
            '|', ('detail_json', '=', False), ('detail_json', '=', ''),
        ]
        retry_before = fields.Datetime.now() - timedelta(minutes=5)
        missing_domain = base_domain + [
            '|', '|', ('detail_attempt_at', '=', False),
            ('detail_error', '=', False),
            ('detail_attempt_at', '<', retry_before),
        ]
        if record_ids is not None:
            missing_domain.append(('id', 'in', record_ids))
        missing = model.search_fetch(
            missing_domain, ['uuid', 'detail_json', 'total', 'currency'],
            order='issued_at desc NULLS LAST, id desc', limit=batch_size)
        if not missing:
            return 0
        if deadline is not None and time.monotonic() >= deadline:
            _logger.warning('ETA UUID detail batch search used the cron time budget '
                            'before fetching details for %s', report_date)
            return 0
        batch_started_at = time.monotonic()
        _logger.info('ETA UUID detail batch starting: connection=%s kind=%s direction=%s '
                     'day=%s selected=%s', config.id, kind, direction, report_date, len(missing))
        try:
            key = (config.id, kind)
            if key not in auth_cache:
                auth_cache[key] = self._detail_headers(config, kind, session=session)
            api_url, headers = auth_cache[key]
        except (UserError, ValueError, requests.RequestException) as exc:
            attempted_at = fields.Datetime.now()
            missing.write({'detail_error': str(exc)[:500],
                           'detail_attempt_at': attempted_at})
            _logger.warning('ETA UUID detail authentication failed for %s %s: %s',
                            kind, report_date, exc)
            if self.env.context.get('cron_id'):
                self.env['ir.cron']._commit_progress(len(missing), remaining=1)
            return 0
        rate_config = config._detail_rate_owner(kind)

        def refresh_auth():
            auth_cache[key] = config._eta_auth_headers(kind, session=session, force_refresh=True)
            return auth_cache[key][1]

        request = partial(self.env['ab_tax_eta_archive_sync']._request,
                          request_session=session, request_attempts=1, timeout=(5, 10),
                          rate_config=rate_config, deadline=deadline, refresh_auth=refresh_auth)
        processed = 0
        ready = 0
        shape_logged = False
        progress = getattr(self, 'web_progress_percent', None)
        progress_message = self._detail_progress_message(kind, direction, report_date)
        progress_total = progress_total or len(missing)
        if progress and not progress_offset:
            progress(0, msg=progress_message, cancellable=False)
        for record_id in missing.ids:
            # Keep each request's field prefetch bounded after progress commits.
            record = model.browse(record_id)
            if deadline is not None and time.monotonic() + 1 >= deadline:
                break
            record.fetch(['uuid', 'detail_json', 'total', 'currency'])
            if record.detail_json:
                continue
            path = ('api/v1.0/documents' if kind == 'invoice' else 'api/v1/receipts')
            payload = None
            try:
                detail_url = f'{api_url}/{path}/{quote(record.uuid, safe="")}/raw'
                payload = request('GET', detail_url, headers=headers)
                if not isinstance(payload, dict):
                    raise ValueError('ETA detail response is not an object')
                values = _detail_values(payload, kind)
                record.write({'detail_json': json.dumps(values, ensure_ascii=False,
                                                        sort_keys=True), 'detail_error': False,
                              'detail_attempt_at': fields.Datetime.now()})
                ready += 1
            except EtaRequestDeferred:
                break
            except (UserError, ValueError, requests.RequestException) as exc:
                record.write({'detail_error': str(exc)[:500],
                              'detail_attempt_at': fields.Datetime.now()})
                if isinstance(payload, dict) and isinstance(exc, ValueError) and not shape_logged:
                    result = payload.get('result')
                    _logger.warning('ETA UUID detail response shape: kind=%s keys=%s '
                                    'result_keys=%s body_type=%s', kind,
                                    sorted(str(key) for key in payload)[:30],
                                    sorted(str(key) for key in result)[:30]
                                    if isinstance(result, dict) else [],
                                    type(payload.get('document' if kind == 'invoice'
                                                     else 'receipt')).__name__)
                    shape_logged = True
                _logger.warning('ETA export detail failed for %s: %s', record.uuid, exc)
            processed += 1
            if progress:
                progress(100.0 * (progress_offset + processed) / progress_total,
                         msg=progress_message, cancellable=False)
            if (self.env.context.get('cron_id') and
                    not self.env['ir.cron']._commit_progress(1, remaining=1)):
                break
        _logger.info('ETA UUID detail batch: connection=%s kind=%s direction=%s day=%s '
                     'selected=%s attempted=%s ready=%s errors=%s unattempted=%s elapsed=%.2fs',
                     config.id, kind, direction, report_date, len(missing), processed,
                     ready, processed - ready, len(missing) - processed,
                     time.monotonic() - batch_started_at)
        if ready:
            self._wake_cron('cron_eta_prepare_files')
        return processed

    def _progress_iter(self, data, message, total=None):
        progress_iter = getattr(self, 'web_progress_iter', None)
        if progress_iter:
            return progress_iter(data, msg=message, total=total, cancellable=False)
        return data

    @api.model
    def _prepare(self, config, report_date, category, kind, direction, export=None):
        if export:
            export = export.try_lock_for_update()
            if not export:
                return False
            export.invalidate_recordset()
        model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice' else 'ab_tax_eta_archive_receipt']
        if model.search_count([
                ('config_id', '=', config.id), ('report_date', '=', report_date),
                ('direction', '=', direction),
                '|', ('detail_json', '=', False), ('detail_json', '=', '')]):
            return False
        records = model.search([('config_id', '=', config.id), ('report_date', '=', report_date),
                                ('direction', '=', direction)],
                               order=('issued_at desc, uuid' if direction == 'sent' else
                                      'issued_at, uuid'))
        if not records:
            return False
        source_updated_at = max(filter(None, records.mapped('write_date')), default=False)
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
            export.source_updated_at = source_updated_at
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
        normal_font = Font(name='Calibri', size=11)
        header_font = Font(name='Calibri', size=11)
        detail_font = Font(name='Comic Sans MS', size=12, bold=True, underline='single')
        centered = Alignment(horizontal='center')
        header_cells = [WriteOnlyCell(sheet, value=value) for value in headers]
        for cell in header_cells:
            cell.font = header_font
            cell.border = border
            cell.alignment = centered
        sheet.append(header_cells)
        for serial, record in enumerate(records, start=1):
            cells = export_cells(record, serial)
            cells = [_excel_cell(value) if isinstance(value, str) else value for value in cells]
            row = []
            for index, value in enumerate(cells):
                cell = WriteOnlyCell(sheet, value=value)
                cell.font = normal_font
                cell.border = border
                cell.alignment = centered
                if index in ((4, 5) if kind == 'receipt' else (5, 6)):
                    cell.number_format = 'mm-dd-yy'
                if index == 1:
                    cell.font = detail_font
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
            'source_updated_at': source_updated_at,
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
                  'telegram_error': False, 'telegram_send_requested': False}
        if checked_through:
            values['checked_through'] = checked_through
        self.write(values)
