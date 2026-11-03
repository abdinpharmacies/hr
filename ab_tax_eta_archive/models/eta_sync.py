import logging
import json
import time
from datetime import datetime, time as day_time, timedelta, timezone
from urllib.parse import urlsplit
import pytz

import requests
from psycopg2.errors import UniqueViolation

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .eta_document import eta_report_date

_logger = logging.getLogger(__name__)
ETA_MAX_RECEIPTS_PER_SEARCH = 3000
ETA_RECEIPT_PAGE_SIZE = 1000
ETA_MAX_RECEIPT_PAGE_NO = 300
ETA_MAX_INVOICE_PAGES = 20
ETA_INVOICE_SEARCH_DELAY = 2.1
ETA_RECEIPT_SEARCH_DELAY = 0.6
ETA_RECEIPT_WINDOWS_PER_CRON_ATTEMPT = 4


class EtaSearchNoResult(Exception):
    """ETA found no documents for the requested receipt search criteria."""


class EtaSearchLimit(Exception):
    """ETA requires a narrower receipt search interval."""


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
    next_receipt_window_at = fields.Datetime(readonly=True)
    receipt_issue_dates_json = fields.Text(readonly=True)
    # Preserve records from earlier deployments without issuing new package requests.
    package_ids = fields.One2many('ab_tax_eta_archive_package', 'sync_id', readonly=True)
    segment_ids = fields.One2many('ab_tax_eta_archive_segment', 'sync_id',
                                  string='Receipt Segments', readonly=True)

    _unique_stream_day = models.Constraint(
        'UNIQUE(config_id, report_date, kind, direction)',
        'Only one ETA retrieval is allowed for each day and stream.')

    def _progress_iter(self, data, message, total=None):
        progress_iter = getattr(self, 'web_progress_iter', None)
        if progress_iter:
            return progress_iter(data, msg=message, total=total, cancellable=False)
        return data

    @api.model
    def _cron_sync(self):
        cairo = pytz.timezone('Africa/Cairo')
        today = datetime.now(cairo).date()
        error_retry_before = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        delivery_day = today - timedelta(days=4)
        made_progress = False
        configs = self.env['ab_tax_eta_archive_config'].search([('active', '=', True)])
        streams = (('invoice', 'received'), ('invoice', 'sent'),
                   ('receipt', 'sent'), ('receipt', 'received'))
        yesterday = today - timedelta(days=1)
        for config in configs:
            if not config.start_date:
                continue
            if not self._ensure_run_days(config, today):
                return
            runs = self.search([
                ('config_id', '=', config.id),
                ('report_date', '>=', config.start_date),
                ('report_date', '<', today),
            ])
            by_day_stream = {(run.report_date, run.kind, run.direction): run for run in runs}
            unfinished_days = {
                run.report_date for run in runs
                if run.state == 'pending' or
                (run.state == 'error' and
                 (not run.last_run_at or
                  fields.Datetime.to_datetime(run.last_run_at) <= error_retry_before))
            }
            overlap_days = {
                run.report_date for run in runs
                if run.state == 'done' and
                max(config.start_date, today - timedelta(days=14)) <= run.report_date < yesterday and
                (not run.last_run_at or
                 fields.Datetime.to_datetime(run.last_run_at).replace(
                     tzinfo=timezone.utc).astimezone(cairo).date() < today)
            }
            priority_days = [day for day in (yesterday, delivery_day)
                             if config.start_date <= day < today]
            ordered_days = list(dict.fromkeys(
                priority_days + sorted(unfinished_days) + sorted(overlap_days)))
            for day in ordered_days:
                for kind, direction in streams:
                    run = by_day_stream.get((day, kind, direction))
                    if not run:
                        continue
                    due = (run.state == 'pending' or
                           (run.state == 'error' and
                            (not run.last_run_at or
                             fields.Datetime.to_datetime(run.last_run_at) <= error_retry_before)) or
                           (run.state == 'done' and day in overlap_days and
                            (not run.last_run_at or
                             fields.Datetime.to_datetime(run.last_run_at).replace(
                                 tzinfo=timezone.utc).astimezone(cairo).date() < today)))
                    if not due:
                        continue
                    keep_running, progressed = self._cron_attempt(run)
                    made_progress |= progressed
                    if not keep_running:
                        return
                if day in unfinished_days:
                    break
        if self.env.context.get('cron_id'):
            remaining = (sum(self._eligible_remaining(config, today, error_retry_before)
                             for config in configs if config.start_date)
                         if made_progress else 0)
            self.env['ir.cron']._commit_progress(remaining=remaining)

    def _eligible_remaining(self, config, today, error_retry_before):
        runs = self.search([
            ('config_id', '=', config.id),
            ('report_date', '>=', config.start_date),
            ('report_date', '<', today),
            ('state', 'in', ['pending', 'error']),
        ])
        return len(runs.filtered(
            lambda run: run.state == 'pending' or not run.last_run_at or
            fields.Datetime.to_datetime(run.last_run_at) <= error_retry_before))

    def _ensure_run_days(self, config, today):
        existing = self.search([
            ('config_id', '=', config.id),
            ('report_date', '>=', config.start_date),
            ('report_date', '<=', today),
        ])
        today_runs = existing.filtered(lambda run: run.report_date == today)
        today_runs.filtered(lambda run: run.state == 'done').write({'state': 'pending'})
        today_runs.filtered(
            lambda run: run.kind == 'receipt' and
            (run.next_receipt_window_at or run.receipt_issue_dates_json)
        ).write({'next_receipt_window_at': False, 'receipt_issue_dates_json': False})
        known = {(run.report_date, run.kind, run.direction) for run in existing}
        missing = []
        day = config.start_date
        while day <= today:
            for kind in ('invoice', 'receipt'):
                for direction in ('sent', 'received'):
                    if (day, kind, direction) not in known:
                        missing.append({
                            'config_id': config.id, 'report_date': day,
                            'kind': kind, 'direction': direction,
                        })
            day += timedelta(days=1)
        for offset in range(0, len(missing), 200):
            self.create(missing[offset:offset + 200])
            if (self.env.context.get('cron_id') and
                    not self.env['ir.cron']._commit_progress(
                        min(200, len(missing) - offset),
                        remaining=max(len(missing) - offset - 200, 0) + 1)):
                return False
        return True

    def _cron_attempt(self, run):
        in_cron = bool(self.env.context.get('cron_id'))
        auth_cache = {}
        attempts = ETA_RECEIPT_WINDOWS_PER_CRON_ATTEMPT if in_cron else 1
        progressed = False
        windows = (self._progress_iter(
            range(attempts), _('Retrieving ETA receipt windows'), total=attempts)
            if run.kind == 'receipt' else range(attempts))
        for window_number in windows:
            previous_state = run.state
            previous_count = run.item_count
            previous_window = run.next_receipt_window_at
            manual_progress = (run.kind == 'receipt' and not in_cron and
                               getattr(run, 'web_progress_percent', None))
            if manual_progress:
                run.web_progress_percent(0, _('Retrieving ETA receipt window'),
                                         cancellable=False)
            run._attempt(auth_cache=auth_cache)
            if manual_progress:
                run.web_progress_percent(100, _('ETA receipt retry finished'),
                                         cancellable=False)
            step_progressed = (run.state != previous_state or
                               run.item_count != previous_count or
                               run.next_receipt_window_at != previous_window)
            progressed |= step_progressed
            if in_cron and not self.env['ir.cron']._commit_progress(
                    int(step_progressed), remaining=1):
                return False, progressed
            if run.kind != 'receipt' or run.state != 'pending':
                return True, progressed
            if (run.next_receipt_window_at and
                    run.next_receipt_window_at != previous_window):
                continue
            return True, progressed
        return True, progressed

    def action_retry(self):
        for run in self:
            self._cron_attempt(run)

    def _attempt(self, auth_cache=None):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                if not self.try_lock_for_update():
                    _logger.info('ETA retrieval is already running for %s %s %s',
                                 self.report_date, self.kind, self.direction)
                    return
                result = self._retrieve(auth_cache=auth_cache)
        except (requests.RequestException, UserError, ValidationError, ValueError, KeyError) as exc:
            _logger.warning('ETA retrieval failed for %s %s %s: %s',
                            self.report_date, self.kind, self.direction, exc)
            self.write({'state': 'error', 'last_run_at': fields.Datetime.now(),
                        'error_message': str(exc)[:2000]})
            try:
                with self.env.cr.savepoint():
                    self._record_receipt_segment_error(exc)
            except Exception:
                _logger.exception('ETA receipt segment error could not be recorded')
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
            try:
                with self.env.cr.savepoint():
                    export_model._ensure_files(self.config_id, issue_date)
            except Exception:
                _logger.exception('ETA daily file generation failed for issue date %s', issue_date)
        completed = self.search_count([
            ('config_id', '=', self.config_id.id), ('report_date', '=', self.report_date),
            ('state', '=', 'done'),
        ])
        if completed == 4 and self.report_date not in issue_dates:
            try:
                with self.env.cr.savepoint():
                    export_model._ensure_files(self.config_id, self.report_date)
            except Exception:
                _logger.exception('ETA daily file generation failed for issue date %s', self.report_date)

    def _retrieve(self, auth_cache=None):
        self.ensure_one()
        config = self.config_id
        cairo = pytz.timezone('Africa/Cairo')
        if self.report_date >= datetime.now(cairo).date():
            return None
        if (self.kind == 'receipt' and
                self.report_date < datetime.now(cairo).date() - timedelta(days=29)):
            raise ValidationError(_(
                'ETA receipt search cannot verify this older day. Receipt package retrieval is disabled.'))
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
        token = auth_cache.get('access_token') if auth_cache is not None else None
        if not token:
            token_response = self._request('POST', f'{identity_url}/connect/token',
                                           data=token_data, **token_options)
            token = token_response.get('access_token')
        if not token:
            raise ValidationError(_('ETA authentication returned no access token.'))
        if auth_cache is not None:
            auth_cache['access_token'] = token
        auth = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
        start = cairo.localize(datetime.combine(self.report_date, day_time.min)).astimezone(timezone.utc)
        end = cairo.localize(datetime.combine(self.report_date + timedelta(days=1),
                                              day_time.min)).astimezone(timezone.utc) - timedelta(milliseconds=1)
        receipt_checkpoint = (json.loads(self.receipt_issue_dates_json or '[]')
                              if self.kind == 'receipt' and self.state != 'done' else [])
        if self.kind == 'invoice':
            pages = self._invoice_pages(api_url, auth, start, end)
            model = self.env['ab_tax_eta_archive_invoice']
        else:
            model = self.env['ab_tax_eta_archive_receipt']
            window_start, window_end, pages = self._recent_receipt_pages(
                api_url, auth, start, end, receipt_checkpoint)
        seen_uuids = set()
        last_receipt_uuid = False
        last_receipt_at = False
        saved_issue_dates = (receipt_checkpoint.get('issue_dates', [])
                             if isinstance(receipt_checkpoint, dict) else receipt_checkpoint)
        issue_dates = set(fields.Date.to_date(value) for value in saved_issue_dates)
        for page in pages:
            unique = {}
            for item in page:
                values = model._eta_values(item, self.direction, config)
                date_field = 'dateTimeIssued' if self.kind == 'receipt' else 'dateTimeReceived'
                if eta_report_date(item[date_field]) != self.report_date:
                    raise ValidationError(_('ETA returned a document outside the requested Cairo date.'))
                uuid = values['uuid']
                if self.kind == 'receipt':
                    last_receipt_uuid = uuid
                    last_receipt_at = values['issued_at']
                if uuid in seen_uuids:
                    raise ValidationError(_('ETA returned duplicate document UUIDs for one retrieval.'))
                seen_uuids.add(uuid)
                unique[uuid] = values
            if not unique:
                continue
            existing = model.search([('config_id', '=', config.id),
                                     ('direction', '=', self.direction),
                                     ('uuid', 'in', list(unique))])
            by_uuid = {record.uuid: record for record in existing}
            new_values = []
            for uuid, values in unique.items():
                issue_dates.add(values['report_date'])
                if uuid in by_uuid:
                    issue_dates.add(by_uuid[uuid].report_date)
                    by_uuid[uuid].write(values)
                else:
                    new_values.append(values)
            if new_values:
                try:
                    with self.env.cr.savepoint():
                        model.create(new_values)
                except UniqueViolation:
                    for values in new_values:
                        try:
                            with self.env.cr.savepoint():
                                model.create(values)
                        except UniqueViolation:
                            existing = model.search([
                                ('config_id', '=', config.id),
                                ('direction', '=', self.direction),
                                ('uuid', '=', values['uuid']),
                            ], limit=1)
                            if not existing:
                                raise
                            issue_dates.add(existing.report_date)
                            existing.write(values)
        if self.kind == 'receipt':
            document_count = model.search_count([
                ('config_id', '=', config.id), ('direction', '=', self.direction),
                ('issued_at', '>=', start.replace(tzinfo=None)),
                ('issued_at', '<', (end + timedelta(milliseconds=1)).replace(tzinfo=None)),
            ])
            self._record_receipt_segment_done(
                window_start, window_end, len(seen_uuids),
                last_receipt_uuid, last_receipt_at)
            next_window = window_end + timedelta(milliseconds=1)
            self.env['ab_tax_eta_archive_segment'].search([
                ('sync_id', '=', self.id), ('state', '=', 'error'),
                ('end_at', '<', next_window.replace(tzinfo=None)),
            ]).write({'state': 'resolved'})
            if next_window <= end:
                self.write({
                    'next_receipt_window_at': next_window.replace(tzinfo=None),
                    'receipt_issue_dates_json': json.dumps({
                        'basis': 'issued',
                        'issue_dates': sorted(fields.Date.to_string(value) for value in issue_dates),
                    }),
                    'item_count': document_count,
                })
                return None
            self.write({'next_receipt_window_at': False, 'receipt_issue_dates_json': False})
            return document_count, issue_dates
        return len(seen_uuids), issue_dates

    def _record_receipt_segment_done(self, start, end, count, last_uuid, last_at):
        values = {
            'sync_id': self.id,
            'start_at': start.replace(tzinfo=None),
            'end_at': end.replace(tzinfo=None),
            'state': 'done', 'item_count': count,
            'last_receipt_uuid': last_uuid,
            'last_receipt_at': last_at,
            'error_message': False,
            'last_run_at': fields.Datetime.now(),
        }
        segments = self.env['ab_tax_eta_archive_segment']
        existing = segments.search([
            ('sync_id', '=', self.id),
            ('start_at', '=', values['start_at']),
            ('end_at', '=', values['end_at']),
        ], limit=1)
        if existing:
            existing.write(values)
        else:
            segments.create(values)

    def _record_receipt_segment_error(self, exc):
        if self.kind != 'receipt':
            return
        cairo = pytz.timezone('Africa/Cairo')
        today = datetime.now(cairo).date()
        if self.report_date >= today or self.report_date < today - timedelta(days=29):
            return
        start = cairo.localize(datetime.combine(self.report_date, day_time.min))
        start = start.astimezone(timezone.utc)
        checkpoint = json.loads(self.receipt_issue_dates_json or '[]')
        if (self.next_receipt_window_at and isinstance(checkpoint, dict) and
                checkpoint.get('basis') == 'issued'):
            start = fields.Datetime.to_datetime(
                self.next_receipt_window_at).replace(tzinfo=timezone.utc)
        end = min(
            start.replace(minute=0, second=0, microsecond=0)
            + timedelta(hours=1) - timedelta(milliseconds=1),
            cairo.localize(datetime.combine(
                self.report_date + timedelta(days=1), day_time.min)
            ).astimezone(timezone.utc) - timedelta(milliseconds=1))
        values = {
            'sync_id': self.id,
            'start_at': start.replace(tzinfo=None),
            'end_at': end.replace(tzinfo=None),
            'state': 'error',
            'error_message': str(exc)[:2000],
            'last_run_at': fields.Datetime.now(),
        }
        segments = self.env['ab_tax_eta_archive_segment']
        existing = segments.search([
            ('sync_id', '=', self.id),
            ('start_at', '=', values['start_at']),
            ('end_at', '=', values['end_at']),
        ], limit=1)
        if existing:
            existing.write(values)
        else:
            segments.create(values)

    def _recent_receipt_pages(self, api_url, auth, start, end, receipt_checkpoint):
        window_start = start
        if (self.state != 'done' and self.next_receipt_window_at and
                isinstance(receipt_checkpoint, dict) and
                receipt_checkpoint.get('basis') == 'issued'):
            window_start = fields.Datetime.to_datetime(
                self.next_receipt_window_at).replace(tzinfo=timezone.utc)
        if window_start > end:
            window_start = start
        hour_end = min(
            window_start.replace(minute=0, second=0, microsecond=0)
            + timedelta(hours=1) - timedelta(milliseconds=1), end)
        selected = self._select_receipt_window(api_url, auth, window_start, hour_end)
        if selected is None:
            return window_start, hour_end, ()
        selected_start, window_end = selected
        return window_start, window_end, self._receipt_pages(
            api_url, auth, selected_start, window_end, expected_nonempty=True)

    def _invoice_pages(self, api_url, headers, start, end):
        params = {
            'submissionDateFrom': start.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'submissionDateTo': end.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'direction': 'Sent' if self.direction == 'sent' else 'Received',
            'pageSize': 100,
        }
        pages, token, seen = [], None, set()
        while True:
            if len(seen) >= ETA_MAX_INVOICE_PAGES:
                first, second = self._split_search_window(
                    start, end, _('ETA invoice search exceeded the safe page limit.'))
                yield from self._invoice_pages(api_url, headers, *first)
                yield from self._invoice_pages(api_url, headers, *second)
                return
            current = dict(params)
            if token:
                current['continuationToken'] = token
            payload = self._request('GET', f'{api_url}/api/v1.0/documents/search',
                                    headers=headers, params=current)
            page = payload.get('result')
            metadata = payload.get('metadata')
            if not isinstance(page, list) or not isinstance(metadata, dict):
                raise ValidationError(_('ETA invoice search returned an invalid page.'))
            pages.append(page)
            next_token = metadata.get('continuationToken')
            if next_token == 'EndofResultSet':
                yield from pages
                return
            if not next_token or next_token in seen:
                raise ValidationError(_('ETA invoice pagination stopped before the final page.'))
            seen.add(next_token)
            token = next_token

    def _split_search_window(self, start, end, limit_message):
        if end - start <= timedelta(milliseconds=1):
            raise ValidationError(limit_message)
        midpoint = start + (end - start) / 2
        midpoint = midpoint.replace(microsecond=(midpoint.microsecond // 1000) * 1000)
        return (start, midpoint), (midpoint + timedelta(milliseconds=1), end)

    def _split_receipt_pages(self, api_url, headers, start, end):
        first, second = self._split_search_window(
            start, end, _('ETA receipt result limit reached for a one-millisecond window.'))
        yield from self._receipt_pages(api_url, headers, *first)
        yield from self._receipt_pages(api_url, headers, *second)

    def _select_receipt_window(self, api_url, headers, start, end):
        params = {
            'Direction': 'Submitted' if self.direction == 'sent' else 'Received',
            'DateTimeIssuedFrom': start.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'DateTimeIssuedTo': end.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'SortBy': 'DateTimeIssued',
            'SortDir': 'Asc',
            'PageNo': 1,
            'PageSize': 1,
        }
        try:
            payload = self._request(
                'GET', f'{api_url}/api/v1/receipts/search',
                headers=headers, params=params, allow_no_result=True,
                allow_search_limit=True)
        except EtaSearchNoResult:
            return None
        except EtaSearchLimit:
            total = ETA_MAX_RECEIPTS_PER_SEARCH
        else:
            page, metadata = self._receipt_page_and_metadata(payload)
            total = metadata.get('totalCount')
            if not isinstance(total, int) or total < 0:
                raise ValidationError(_('ETA receipt search returned invalid pagination metadata.'))
            if not page:
                if total == 0:
                    return None
                raise ValidationError(_('ETA receipt search returned invalid pagination metadata.'))
        if total < ETA_MAX_RECEIPTS_PER_SEARCH:
            return start, end
        first, second = self._split_search_window(
            start, end, _('ETA receipt result limit reached for a one-millisecond window.'))
        return (self._select_receipt_window(api_url, headers, *first) or
                self._select_receipt_window(api_url, headers, *second))

    def _receipt_page_and_metadata(self, payload):
        result = payload.get('result')
        page = payload.get('receipts')
        if page is None:
            page = result if isinstance(result, list) else payload.get('data')
        if page is None and isinstance(result, dict):
            page = result.get('receipts', result.get('data'))
        metadata = payload.get('metadata')
        if metadata is None and isinstance(result, dict):
            metadata = result.get('metadata')
        if not isinstance(page, list) or not isinstance(metadata, dict):
            raise ValidationError(_('ETA receipt search returned an invalid page.'))
        return page, metadata

    def _receipt_pages(self, api_url, headers, start, end, expected_nonempty=False):
        params = {
            'Direction': 'Submitted' if self.direction == 'sent' else 'Received',
            'DateTimeIssuedFrom': start.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'DateTimeIssuedTo': end.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'SortBy': 'DateTimeIssued',
            'SortDir': 'Asc',
            'PageSize': ETA_RECEIPT_PAGE_SIZE,
        }
        pages = []
        count = 0
        total = None
        page_size = ETA_RECEIPT_PAGE_SIZE
        for page_no in range(1, ETA_MAX_RECEIPT_PAGE_NO + 1):
            try:
                payload, page_size = self._request_receipt_page(
                    api_url, headers, params, page_no, page_size)
            except EtaSearchNoResult:
                if page_no == 1:
                    if expected_nonempty:
                        raise ValidationError(_('ETA receipt count changed while reading the result pages.'))
                    return
                break
            except EtaSearchLimit:
                yield from self._split_receipt_pages(api_url, headers, start, end)
                return
            page, metadata = self._receipt_page_and_metadata(payload)
            page_total = metadata.get('totalCount')
            if not isinstance(page_total, int) or page_total < 0:
                raise ValidationError(_('ETA receipt search returned invalid pagination metadata.'))
            if total is not None and page_total != total:
                raise ValidationError(_('ETA receipt count changed while reading the result pages.'))
            total = page_total
            if total >= ETA_MAX_RECEIPTS_PER_SEARCH:
                yield from self._split_receipt_pages(api_url, headers, start, end)
                return
            if not page:
                break
            count += len(page)
            pages.append(page)
            if count >= total:
                break
        else:
            raise ValidationError(_('ETA receipt search exceeded the safe page limit.'))

        if total is None:
            raise ValidationError(_('ETA receipt search returned invalid pagination metadata.'))
        if expected_nonempty and total == 0:
            raise ValidationError(_('ETA receipt count changed while reading the result pages.'))
        if count != total:
            raise ValidationError(_('ETA receipt page count does not match the reported total.'))
        yield from self._progress_iter(
            pages, _('Saving ETA receipt pages'), total=len(pages))

    def _request_receipt_page(self, api_url, headers, params, page_no, page_size):
        sizes = (page_size, 200, 100, 50, 10) if page_no == 1 else (page_size,)
        for candidate in dict.fromkeys(sizes):
            try:
                payload = self._request(
                    'GET', f'{api_url}/api/v1/receipts/search',
                    headers=headers,
                    params={**params, 'PageNo': page_no, 'PageSize': candidate},
                    allow_no_result=True, allow_search_limit=True)
            except UserError as exc:
                message = str(exc).lower()
                if (page_no == 1 and candidate != 10 and
                        'http 400' in message and 'page' in message and 'size' in message):
                    continue
                raise
            return payload, candidate
        raise ValidationError(_('ETA receipt search returned an invalid page.'))

    def _request(self, method, url, allow_no_result=False, allow_search_limit=False, **kwargs):
        search_delay = {
            '/api/v1.0/documents/search': ETA_INVOICE_SEARCH_DELAY,
            '/api/v1/receipts/search': ETA_RECEIPT_SEARCH_DELAY,
        }.get(urlsplit(url).path, 0)
        for attempt in range(4):
            if search_delay:
                time.sleep(search_delay)
            try:
                response = requests.request(method, url, timeout=40, **kwargs)
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
                continue
            if response.status_code in (429, 503) and attempt < 3:
                retry_after = response.headers.get('Retry-After', '')
                try:
                    delay = float(retry_after)
                except (TypeError, ValueError):
                    delay = 2 ** attempt
                time.sleep(max(delay + 0.5, 1))
                continue
            if response.status_code == 400 and (allow_search_limit or allow_no_result):
                try:
                    error = response.json()
                except ValueError:
                    error = {}
                if isinstance(error, dict):
                    error_detail = error.get('error')
                    detail = error_detail if isinstance(error_detail, dict) else {}
                    code = (error.get('code') or detail.get('code') or
                            (error_detail if isinstance(error_detail, str) else None))
                    message = str(error.get('message') or detail.get('message') or '').lower()
                    oversized_query = (code == 'ValidationError' and
                                       'query will return approximately' in message and
                                       'should be under' in message and
                                       'documents' in message)
                    if allow_search_limit and (code == 'OperationExceedsLimit' or oversized_query):
                        raise EtaSearchLimit()
            if response.status_code == 404 and allow_no_result:
                try:
                    error = response.json()
                except ValueError:
                    error = {}
                if isinstance(error, dict):
                    detail = error.get('error')
                    if isinstance(detail, dict):
                        error = detail
                    message = str(error.get('message') or '').lower()
                    if (error.get('code') == 'NotFound' and
                            (error.get('target') == 'NoResult' or 'no data found' in message)):
                        raise EtaSearchNoResult()
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


class EtaReceiptSegment(models.Model):
    _name = 'ab_tax_eta_archive_segment'
    _description = 'ETA Receipt Segment'
    _order = 'start_at, id'

    sync_id = fields.Many2one('ab_tax_eta_archive_sync', required=True, ondelete='restrict')
    start_at = fields.Datetime(required=True, readonly=True)
    end_at = fields.Datetime(required=True, readonly=True)
    state = fields.Selection([('done', 'Done'), ('error', 'Error'),
                              ('resolved', 'Resolved')], required=True,
                             default='error', readonly=True)
    item_count = fields.Integer(readonly=True)
    last_receipt_uuid = fields.Char(string='Last Receipt UUID', readonly=True)
    last_receipt_at = fields.Datetime(string='Last Receipt At', readonly=True)
    error_message = fields.Text(readonly=True)
    last_run_at = fields.Datetime(readonly=True)

    _unique_segment = models.Constraint(
        'UNIQUE(sync_id, start_at, end_at)',
        'Only one ETA receipt segment is allowed per time window.')
