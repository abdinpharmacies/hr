import logging
import io
import json
import time
import zipfile
from datetime import datetime, time as day_time, timedelta, timezone
from urllib.parse import urlsplit
import pytz

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .eta_document import eta_report_date

_logger = logging.getLogger(__name__)
ETA_MAX_RECEIPTS_PER_SEARCH = 3000
ETA_RECEIPT_PAGE_SIZE = 10
ETA_MAX_RECEIPT_PAGE_NO = ETA_MAX_RECEIPTS_PER_SEARCH // ETA_RECEIPT_PAGE_SIZE
ETA_MAX_INVOICE_PAGES = 1000


class EtaSync(models.Model):
    _name = 'ab_tax_eta_archive_sync'
    _description = 'ETA Daily Retrieval'
    _order = 'report_date desc, id desc'

    config_id = fields.Many2one('ab_tax_eta_archive_config', required=True, ondelete='restrict')
    report_date = fields.Date(string='Submission Date', required=True, index=True)
    kind = fields.Selection([('invoice', 'Invoice'), ('receipt', 'Receipt')], required=True)
    direction = fields.Selection([('sent', 'Sent'), ('received', 'Received')], required=True)
    state = fields.Selection([('pending', 'Pending'), ('done', 'Done'), ('error', 'Error')],
                             required=True, default='pending')
    item_count = fields.Integer(readonly=True)
    last_run_at = fields.Datetime(readonly=True)
    error_message = fields.Text(readonly=True)
    package_ids = fields.One2many('ab_tax_eta_archive_package', 'sync_id', readonly=True)

    _unique_stream_day = models.Constraint(
        'UNIQUE(config_id, report_date, kind, direction)',
        'Only one ETA retrieval is allowed for each day and stream.')

    @api.model
    def _cron_sync(self):
        cairo = pytz.timezone('Africa/Cairo')
        today = datetime.now(cairo).date()
        delivery_day = today - timedelta(days=4)
        for config in self.env['ab_tax_eta_archive_config'].search([('active', '=', True)]):
            if not config.start_date:
                continue
            for kind in ('invoice', 'receipt'):
                for direction in ('sent', 'received'):
                    attempted = set()
                    for priority_day in (today - timedelta(days=1), delivery_day):
                        if priority_day < config.start_date:
                            continue
                        priority_run = self.search([
                            ('config_id', '=', config.id), ('kind', '=', kind),
                            ('direction', '=', direction), ('report_date', '=', priority_day),
                        ], limit=1) or self.create({
                            'config_id': config.id, 'kind': kind,
                            'direction': direction, 'report_date': priority_day,
                        })
                        if (priority_run.state != 'done' or
                                (priority_day == delivery_day and
                                 (not priority_run.last_run_at or
                                  fields.Datetime.to_datetime(priority_run.last_run_at).replace(
                                      tzinfo=timezone.utc).astimezone(cairo).date() < today))):
                            priority_run._attempt()
                            attempted.add(priority_day)
                    stream_domain = [
                        ('config_id', '=', config.id), ('kind', '=', kind),
                        ('direction', '=', direction),
                        ('report_date', '>=', config.start_date),
                        ('report_date', '<', today),
                    ]
                    pending_packages = self.search(stream_domain + [('state', '=', 'pending')]).filtered(
                        lambda run: run.package_ids and run.report_date not in attempted)
                    if pending_packages:
                        oldest_package = min(
                            pending_packages,
                            key=lambda run: fields.Datetime.to_datetime(run.last_run_at)
                            if run.last_run_at else datetime.min,
                        )
                        oldest_package._attempt()
                        attempted.add(oldest_package.report_date)

                    attempted_days = set(self.search(stream_domain).mapped('report_date'))
                    day = config.start_date
                    while day in attempted_days:
                        day += timedelta(days=1)
                    if day < today:
                        run = self.create({
                            'config_id': config.id, 'kind': kind,
                            'direction': direction, 'report_date': day,
                        })
                        run._attempt()
                        continue

                    unfinished = self.search(stream_domain + [('state', 'in', ['pending', 'error'])]).filtered(
                        lambda run: run.report_date not in attempted)
                    if unfinished:
                        oldest_unfinished = min(
                            unfinished,
                            key=lambda run: fields.Datetime.to_datetime(run.last_run_at)
                            if run.last_run_at else datetime.min,
                        )
                        oldest_unfinished._attempt()
                        continue

                    overlap_start = max(config.start_date, today - timedelta(days=14))
                    overlap_runs = self.search(stream_domain + [
                        ('state', '=', 'done'),
                        ('report_date', '>=', overlap_start),
                        ('report_date', '<', today - timedelta(days=1)),
                    ]).filtered(lambda run: run.report_date not in attempted)
                    if overlap_runs:
                        oldest_check = min(
                            overlap_runs,
                            key=lambda run: fields.Datetime.to_datetime(run.last_run_at)
                            if run.last_run_at else datetime.min,
                        )
                        oldest_check._attempt()

    def action_retry(self):
        for run in self:
            run._attempt()

    def _attempt(self):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                result = self._retrieve()
        except (requests.RequestException, UserError, ValidationError, ValueError, KeyError) as exc:
            _logger.warning('ETA retrieval failed for %s %s %s: %s',
                            self.report_date, self.kind, self.direction, exc)
            self.write({'state': 'error', 'last_run_at': fields.Datetime.now(),
                        'error_message': str(exc)[:2000]})
            return
        if result is None:
            self.write({'state': 'pending', 'last_run_at': fields.Datetime.now(),
                        'error_message': False})
            return
        count, issue_dates = result
        self.write({'state': 'done', 'item_count': count,
                    'last_run_at': fields.Datetime.now(), 'error_message': False})
        export_model = self.env['ab_tax_eta_archive_export']
        for issue_date in sorted(issue_dates):
            export_model._ensure_files(self.config_id, issue_date)
        completed = self.search_count([
            ('config_id', '=', self.config_id.id), ('report_date', '=', self.report_date),
            ('state', '=', 'done'),
        ])
        if completed == 4 and self.report_date not in issue_dates:
            export_model._ensure_files(self.config_id, self.report_date)

    def _retrieve(self):
        self.ensure_one()
        config = self.config_id
        receipt_auth_mode = config.receipt_auth_mode or 'taxpayer'
        if self.kind == 'invoice' or receipt_auth_mode == 'taxpayer':
            client_id = config.invoice_client_id
            client_secret = config.invoice_client_secret
        else:
            client_id = config.receipt_client_id
            client_secret = config.receipt_client_secret
        if not client_id or not client_secret:
            if self.kind == 'invoice' or receipt_auth_mode == 'taxpayer':
                raise UserError(_('Configure the ETA invoice client ID and secret before retrieval.'))
            raise UserError(_('Configure the ETA receipt client ID and secret before retrieval.'))
        identity_url, api_url = config._base_urls()
        headers = {}
        if self.kind == 'receipt' and receipt_auth_mode == 'pos':
            required = (config.pos_serial, config.pos_os_version,
                        config.pos_model_framework, config.pos_preshared_key)
            if not all(required):
                raise UserError(_('Configure all ETA POS authentication headers.'))
            headers = dict(zip(('posserial', 'pososversion', 'posmodelframework', 'presharedkey'), required))
        token_data = {'grant_type': 'client_credentials'}
        token_options = {'headers': headers}
        if self.kind == 'invoice' or receipt_auth_mode == 'taxpayer':
            token_options['auth'] = (client_id, client_secret)
        else:
            token_data.update({'client_id': client_id, 'client_secret': client_secret})
        token_response = self._request('POST', f'{identity_url}/connect/token',
                                       data=token_data, **token_options)
        token = token_response.get('access_token')
        if not token:
            raise ValidationError(_('ETA authentication returned no access token.'))
        auth = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
        cairo = pytz.timezone('Africa/Cairo')
        start = cairo.localize(datetime.combine(self.report_date, day_time.min)).astimezone(timezone.utc)
        end = cairo.localize(datetime.combine(self.report_date + timedelta(days=1),
                                              day_time.min)).astimezone(timezone.utc) - timedelta(milliseconds=1)
        if self.kind == 'invoice':
            items = self._invoice_pages(api_url, auth, start, end)
            model = self.env['ab_tax_eta_archive_invoice']
        else:
            if self.report_date < datetime.now(cairo).date() - timedelta(days=29):
                items = self._receipt_package_pages(api_url, auth, start, end)
            else:
                items = self._receipt_pages(api_url, auth, start, end)
            if items is None:
                return None
            model = self.env['ab_tax_eta_archive_receipt']
        unique = {}
        for item in items:
            values = model._eta_values(item, self.direction, config)
            if eta_report_date(item['dateTimeReceived']) != self.report_date:
                raise ValidationError(_('ETA returned a document outside the requested Cairo date.'))
            unique[values['uuid']] = values
        if len(unique) != len(items):
            raise ValidationError(_('ETA returned duplicate document UUIDs for one retrieval.'))
        existing = model.search([('config_id', '=', config.id),
                                 ('direction', '=', self.direction),
                                 ('uuid', 'in', list(unique))])
        by_uuid = {record.uuid: record for record in existing}
        issue_dates = set()
        for uuid, values in unique.items():
            issue_dates.add(values['report_date'])
            if uuid in by_uuid:
                issue_dates.add(by_uuid[uuid].report_date)
                by_uuid[uuid].write(values)
            else:
                model.create(values)
        return len(unique), issue_dates

    def _receipt_package_pages(self, api_url, headers, start, end):
        packages = self.package_ids
        if not packages:
            self.env['ab_tax_eta_archive_package'].create({
                'sync_id': self.id, 'start_at': start.replace(tzinfo=None),
                'end_at': end.replace(tzinfo=None),
            })
            return None
        leaf = packages.filtered(lambda item: item.state == 'pending').sorted('start_at')[:1]
        if leaf:
            part = leaf[0]
            part_start = fields.Datetime.to_datetime(part.start_at).replace(tzinfo=timezone.utc)
            part_end = fields.Datetime.to_datetime(part.end_at).replace(tzinfo=timezone.utc)
            if not part.package_id:
                query = {
                    'represntedTaxpayerTypeId': 'Issuer' if self.direction == 'sent' else 'Receiver',
                    'dateFrom': part_start.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                    'dateTo': part_end.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
                }
                payload = self._request(
                    'POST', f'{api_url}/api/v1.0/receiptpackages/requests',
                    headers={**headers, 'Content-Type': 'application/json'},
                    json={'type': 'Summary', 'format': 'JSON', 'queryParameters': query},
                    allow_package_limit=True,
                )
                if payload.get('__limit__'):
                    if part_end - part_start <= timedelta(milliseconds=1):
                        raise ValidationError(_('ETA receipt package limit reached for a one-millisecond window.'))
                    midpoint = part_start + (part_end - part_start) / 2
                    midpoint = midpoint.replace(microsecond=(midpoint.microsecond // 1000) * 1000)
                    part.write({'state': 'split'})
                    self.env['ab_tax_eta_archive_package'].create([
                        {'sync_id': self.id, 'start_at': part_start.replace(tzinfo=None),
                         'end_at': midpoint.replace(tzinfo=None)},
                        {'sync_id': self.id, 'start_at': (midpoint + timedelta(milliseconds=1)).replace(tzinfo=None),
                         'end_at': part_end.replace(tzinfo=None)},
                    ])
                else:
                    result = payload.get('result') if isinstance(payload.get('result'), dict) else payload
                    package_id = result.get('packageId') or result.get('requestId') or result.get('id')
                    if not package_id:
                        raise ValidationError(_('ETA receipt package request returned no package ID.'))
                    part.package_id = package_id
                return None
            response = self._download_package(api_url, headers, part.package_id)
            if response is None:
                return None
            part.write({'state': 'done', 'payload_json': json.dumps(response, ensure_ascii=False),
                        'item_count': len(response)})
            packages = self.package_ids
        if packages.filtered(lambda item: item.state == 'pending'):
            return None
        completed = packages.filtered(lambda item: item.state == 'done')
        if not completed:
            raise ValidationError(_('ETA receipt package retrieval completed without data or a valid empty package.'))
        items = []
        for part in completed:
            items.extend(json.loads(part.payload_json))
        return items

    def _download_package(self, api_url, headers, package_id):
        for attempt in range(4):
            response = requests.get(f'{api_url}/api/v1.0/receiptpackages/{package_id}',
                                    headers=headers, timeout=120)
            if response.status_code in (429, 503) and attempt < 3:
                retry_after = response.headers.get('Retry-After', '')
                delay = int(retry_after) if retry_after.isdigit() else 2 ** attempt
                time.sleep(max(delay, 1))
                continue
            break
        if response.status_code == 204:
            return None
        try:
            response.raise_for_status()
            archive = zipfile.ZipFile(io.BytesIO(response.content))
            items = []
            names = [name for name in archive.namelist() if name.lower().endswith('.json')]
            if not names:
                raise ValueError('No JSON content')
            for name in names:
                if name.startswith('/') or '..' in name.split('/'):
                    raise ValueError('Invalid ZIP member')
                payload = json.loads(archive.read(name).decode('utf-8-sig'))
                if isinstance(payload, list):
                    page = payload
                elif isinstance(payload, dict) and 'uuid' in payload:
                    page = [payload]
                elif isinstance(payload, dict):
                    page = payload.get('receipts', payload.get('result'))
                else:
                    page = None
                if not isinstance(page, list) or any(not isinstance(item, dict) for item in page):
                    raise ValueError('Unexpected receipt package JSON structure')
                items.extend(page)
            return items
        except (requests.RequestException, zipfile.BadZipFile, ValueError, UnicodeError) as exc:
            raise ValidationError(_('ETA receipt package download is invalid or incomplete.')) from exc

    def _invoice_pages(self, api_url, headers, start, end):
        params = {
            'submissionDateFrom': start.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'submissionDateTo': end.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'direction': 'Sent' if self.direction == 'sent' else 'Received',
            'pageSize': 100,
        }
        items, token, seen = [], None, set()
        while True:
            if len(seen) >= ETA_MAX_INVOICE_PAGES:
                raise ValidationError(_('ETA invoice search exceeded the safe page limit.'))
            current = dict(params)
            if token:
                current['continuationToken'] = token
            payload = self._request('GET', f'{api_url}/api/v1.0/documents/search',
                                    headers=headers, params=current)
            page = payload.get('result')
            metadata = payload.get('metadata')
            if not isinstance(page, list) or not isinstance(metadata, dict):
                raise ValidationError(_('ETA invoice search returned an invalid page.'))
            items.extend(page)
            next_token = metadata.get('continuationToken')
            if next_token == 'EndofResultSet':
                return items
            if not next_token or next_token in seen:
                raise ValidationError(_('ETA invoice pagination stopped before the final page.'))
            seen.add(next_token)
            token = next_token
            time.sleep(0.5)

    def _receipt_pages(self, api_url, headers, start, end):
        params = {
            'Direction': 'Submitted' if self.direction == 'sent' else 'Received',
            'DateTimeReceivedFrom': start.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'DateTimeReceivedTo': end.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'PageSize': ETA_RECEIPT_PAGE_SIZE,
        }
        items = []
        total = None
        for page_no in range(1, ETA_MAX_RECEIPT_PAGE_NO + 1):
            if page_no > 1:
                time.sleep(0.5)
            payload = self._request('GET', f'{api_url}/api/v1/receipts/search',
                                    headers=headers, params={**params, 'PageNo': page_no})
            page = payload.get('receipts')
            metadata = payload.get('metadata')
            if not isinstance(page, list) or not isinstance(metadata, dict):
                raise ValidationError(_('ETA receipt search returned an invalid page.'))
            page_total = metadata.get('totalCount')
            if not isinstance(page_total, int) or page_total < 0:
                raise ValidationError(_('ETA receipt search returned invalid pagination metadata.'))
            if total is not None and page_total != total:
                raise ValidationError(_('ETA receipt count changed while reading the result pages.'))
            total = page_total
            if total >= ETA_MAX_RECEIPTS_PER_SEARCH:
                break
            if not page:
                break
            items.extend(page)
            if len(items) >= total:
                break
        else:
            raise ValidationError(_('ETA receipt search exceeded the safe page limit.'))

        if total is None:
            raise ValidationError(_('ETA receipt search returned invalid pagination metadata.'))
        if total >= ETA_MAX_RECEIPTS_PER_SEARCH:
            if end - start <= timedelta(milliseconds=1):
                raise ValidationError(_('ETA receipt result limit reached for a one-millisecond window.'))
            midpoint = start + (end - start) / 2
            midpoint = midpoint.replace(microsecond=(midpoint.microsecond // 1000) * 1000)
            return (self._receipt_pages(api_url, headers, start, midpoint) +
                    self._receipt_pages(api_url, headers, midpoint + timedelta(milliseconds=1), end))
        if len({item.get('uuid') for item in items}) != total:
            raise ValidationError(_('ETA receipt page count does not match the reported total.'))
        return items

    def _request(self, method, url, allow_package_limit=False, **kwargs):
        for attempt in range(4):
            try:
                response = requests.request(method, url, timeout=40, **kwargs)
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
                continue
            if response.status_code in (429, 503) and attempt < 3:
                retry_after = response.headers.get('Retry-After', '')
                delay = int(retry_after) if retry_after.isdigit() else 2 ** attempt
                time.sleep(max(delay, 1))
                continue
            if response.status_code == 400 and allow_package_limit:
                try:
                    error = response.json()
                except ValueError:
                    error = {}
                if isinstance(error, dict) and (
                    error.get('error') == 'OperationExceedsLimit' or
                    error.get('code') == 'OperationExceedsLimit'
                ):
                    return {'__limit__': True}
            try:
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                endpoint = urlsplit(response.url)
                request_target = f'{method} {endpoint.netloc}{endpoint.path}'
                detail = ''
                try:
                    error_body = response.json()
                except ValueError:
                    error_body = {}
                if isinstance(error_body, dict):
                    error = error_body.get('error')
                    if isinstance(error, dict):
                        detail = ': '.join(str(error.get(key, '')).strip()
                                           for key in ('code', 'message', 'target')
                                           if error.get(key))
                if not detail and response.text:
                    detail = ' '.join(response.text.split())[:1000]
                correlation_id = response.headers.get('correlationId')
                if correlation_id:
                    detail = f'{detail} (correlationId: {correlation_id})'.strip()
                _logger.warning('ETA HTTP %s at %s: %s', response.status_code,
                                request_target, detail)
                error_message = '%s %s' % (
                    _('ETA request failed (HTTP %(status)s).', status=response.status_code),
                    request_target,
                )
                if detail:
                    error_message = f'{error_message}: {detail}'
                raise UserError(error_message) from exc
            if not isinstance(payload, dict):
                raise ValidationError(_('ETA returned an invalid JSON response.'))
            return payload
        raise UserError(_('ETA request exhausted its retries.'))


class EtaReceiptPackage(models.Model):
    _name = 'ab_tax_eta_archive_package'
    _description = 'ETA Receipt Package Request'
    _order = 'start_at'

    sync_id = fields.Many2one('ab_tax_eta_archive_sync', required=True, ondelete='restrict')
    start_at = fields.Datetime(required=True)
    end_at = fields.Datetime(required=True)
    package_id = fields.Char(readonly=True)
    state = fields.Selection([('pending', 'Pending'), ('split', 'Split'), ('done', 'Done')],
                             required=True, default='pending')
    item_count = fields.Integer(readonly=True)
    payload_json = fields.Text(readonly=True, groups='ab_tax_eta_archive.group_eta_manager')

    _unique_window = models.Constraint(
        'UNIQUE(sync_id, start_at, end_at)',
        'Only one ETA package request is allowed per time window.')
