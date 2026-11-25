import logging
import json
import time
import hashlib
import re
from email.utils import parsedate_to_datetime
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
ETA_MAX_RECEIPTS_PER_SEARCH = 3000
ETA_INVOICE_SEARCH_DELAY = 2.1
ETA_RECEIPT_SEARCH_DELAY = 0.6
ETA_RECEIPT_SEARCH_DAYS = 29
ETA_HISTORICAL_RECEIPT_PACKAGES_ENABLED = True


@contextmanager
def eta_task_lock(env, task):
    """Keep an ETA task exclusive across progress commits and cron/manual runs."""
    # A dedicated transaction owns only this advisory lock, never business rows.
    # Its cursor context releases the lock on success, exception or worker exit.
    with env.registry.cursor() as lock_cr:
        lock_cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', (0x455441, task))
        yield bool(lock_cr.fetchone()[0])


class EtaSearchNoResult(Exception):
    """ETA found no documents for the requested receipt search criteria."""


class EtaSearchLimit(Exception):
    """ETA requires a narrower receipt search interval."""


class EtaPageSizeError(Exception):
    """The server's configured maximum page size is below the requested size."""


class EtaHttpError(UserError):
    """HTTP diagnostics without retaining response payloads or credentials."""

    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def eta_error_codes(payload):
    """Support standard nested errors and flat errors; retain only code/target."""
    if not isinstance(payload, dict):
        return ''
    error = payload.get('error')
    short_error = error if isinstance(error, str) and re.fullmatch(r'[A-Za-z][\w.-]{0,79}', error) else None
    error = error if isinstance(error, dict) else payload
    rows = [error] + (error.get('details') if isinstance(error.get('details'), list) else [])[:5]
    diagnostics = []
    if short_error and not error.get('code'):
        diagnostics.append('code=' + short_error)
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = []
        for name in ('code', 'target'):
            value = row.get(name)
            if isinstance(value, (str, int)) and re.fullmatch(r'[\w.\[\]-]{1,80}', str(value)):
                values.append('%s=%s' % (name, value))
        if values:
            diagnostics.append(', '.join(values))
    return '; '.join(diagnostics)


class EtaRequestDeferred(Exception):
    """Leave work queued when the request cannot fit in the current cron slice."""

    def __init__(self, config=None, endpoint=None, delay=0):
        super().__init__()
        self.config = config
        self.endpoint = endpoint
        self.delay = delay


def eta_retry_delay(value, attempt=0):
    """Retry-After supports both delta seconds and an HTTP date (RFC 9110)."""
    try:
        delay = float(value)
        if not 0 <= delay < float('inf'):
            raise ValueError()
    except (TypeError, ValueError):
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            delay = 2 ** attempt
    return max(delay, 1) + 0.5


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
    issue_day_rows = fields.Integer(string='Issue-Day Saved Rows',
                                    compute='_compute_issue_day_coverage', compute_sudo=True)
    issue_day_uuid_ready = fields.Integer(string='Issue-Day UUID Details Ready',
                                          compute='_compute_issue_day_coverage', compute_sudo=True)
    issue_day_uuid_pending = fields.Integer(string='Issue-Day UUID Details Pending',
                                            compute='_compute_issue_day_coverage', compute_sudo=True)
    last_run_at = fields.Datetime(readonly=True)
    error_message = fields.Text(readonly=True)
    next_receipt_window_at = fields.Datetime(readonly=True)
    receipt_issue_dates_json = fields.Text(readonly=True)
    # Historical receipt requests and their resumable import checkpoints.
    package_ids = fields.One2many('ab_tax_eta_archive_package', 'sync_id', readonly=True)
    segment_ids = fields.One2many('ab_tax_eta_archive_segment', 'sync_id',
                                  string='Receipt Segments', readonly=True)

    _unique_stream_day = models.Constraint(
        'UNIQUE(config_id, report_date, kind, direction)',
        'Only one ETA retrieval is allowed for each day and stream.')

    @api.depends('config_id', 'report_date', 'kind', 'direction')
    def _compute_issue_day_coverage(self):
        for run in self:
            run.issue_day_rows = 0
            run.issue_day_uuid_ready = 0
            run.issue_day_uuid_pending = 0
        for kind in ('invoice', 'receipt'):
            runs = self.filtered(lambda run: run.kind == kind)
            if not runs:
                continue
            by_key = {}
            for run in runs:
                by_key.setdefault((run.config_id.id, run.report_date, run.direction), []).append(run)
            model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice'
                             else 'ab_tax_eta_archive_receipt']
            domain = (fields.Domain('config_id', 'in', runs.mapped('config_id').ids) &
                      fields.Domain('report_date', 'in', runs.mapped('report_date')) &
                      fields.Domain('direction', 'in', runs.mapped('direction')))
            groupby = ['config_id', 'report_date:day', 'direction']
            for config, day, direction, count in model._read_group(domain, groupby, ['__count']):
                for run in by_key.get((config.id, day, direction), []):
                    run.issue_day_rows = count
            ready_domain = (domain & fields.Domain('detail_json', '!=', False) &
                            fields.Domain('detail_json', '!=', ''))
            for config, day, direction, count in model._read_group(
                    ready_domain, groupby, ['__count']):
                for run in by_key.get((config.id, day, direction), []):
                    run.issue_day_uuid_ready = count
        for run in self:
            run.issue_day_uuid_pending = run.issue_day_rows - run.issue_day_uuid_ready

    def _progress_iter(self, data, message, total=None):
        progress_iter = getattr(self, 'web_progress_iter', None)
        if progress_iter:
            return progress_iter(data, msg=message, total=total, cancellable=False)
        return data


    def _ensure_run_days(self, config, today, kind=None):
        existing = self.search([
            ('config_id', '=', config.id),
            ('kind', 'in', [kind] if kind else ['invoice', 'receipt']),
            ('report_date', '>=', config.start_date),
            ('report_date', '<=', today),
        ])
        known = {(run.report_date, run.kind, run.direction) for run in existing}
        missing = []
        day = config.start_date
        while day <= today:
            for stream_kind in ([kind] if kind else ('invoice', 'receipt')):
                for direction in ('sent', 'received'):
                    if (day, stream_kind, direction) not in known:
                        missing.append({
                            'config_id': config.id, 'report_date': day,
                            'kind': stream_kind, 'direction': direction,
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


    def _request_receipt_page(self, api_url, headers, params, page_no, page_size):
        sizes = (min(page_size, 100), 50, 10) if page_no == 1 else (min(page_size, 100),)
        for candidate in dict.fromkeys(sizes):
            try:
                payload = self._request(
                    'GET', f'{api_url}/api/v1/receipts/search',
                    headers=headers,
                    params={**params, 'PageNo': page_no, 'PageSize': candidate},
                    allow_no_result=True, allow_search_limit=True)
            except EtaPageSizeError:
                if page_no == 1 and candidate != 10:
                    continue
                raise ValidationError(_('ETA receipt search returned an invalid page.'))
            return payload, candidate
        raise ValidationError(_('ETA receipt search returned an invalid page.'))

    def _request(self, method, url, allow_no_result=False, allow_search_limit=False,
                 request_session=None, request_attempts=4, rate_config=None,
                 deadline=None, refresh_auth=None, raw_response=False, **kwargs):
        deadline = deadline or self.env.context.get('eta_retrieval_deadline')
        search_delay = {
            '/api/v1.0/documents/search': ETA_INVOICE_SEARCH_DELAY,
            '/api/v1/receipts/search': ETA_RECEIPT_SEARCH_DELAY,
        }.get(urlsplit(url).path, 0)
        timeout = kwargs.pop('timeout', 40)
        request_session = request_session or self.env.context.get('eta_request_session')
        send = request_session.request if request_session else requests.request
        endpoint = ('invoice_raw' if '/documents/' in urlsplit(url).path else 'receipt_raw')
        search_owner = None
        if search_delay and len(self) == 1:
            search_owner = self.config_id._detail_rate_owner(self.kind)
            endpoint = self.kind + '_search'
            search_owner.invalidate_recordset(['request_schedule'])
            wait = (search_owner.request_schedule or {}).get(endpoint, 0) - time.time()
            if wait > 0:
                raise EtaRequestDeferred(search_owner, endpoint, wait)
        for attempt in range(request_attempts):
            if deadline is not None and time.monotonic() >= deadline:
                raise EtaRequestDeferred()
            if rate_config is not None:
                rate_config._reserve_detail_request(endpoint, deadline or float('inf'))
            request_timeout = timeout
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 1:
                    raise EtaRequestDeferred()
                if isinstance(timeout, tuple):
                    request_timeout = (min(timeout[0], remaining / 3),
                                       min(timeout[1], remaining * 2 / 3))
                else:
                    request_timeout = min(timeout, remaining)
            try:
                if search_delay and search_owner is not None:
                    # Serialize search starts across manual/cron runs and duplicate
                    # configurations sharing credentials. No business-row locks.
                    identity = '%s:%s:%s' % (search_owner.environment,
                        search_owner.receipt_client_id if self.kind == 'receipt'
                        and search_owner.receipt_auth_mode == 'pos'
                        else search_owner.invoice_client_id, endpoint)
                    lock_id = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:4],
                                             'big', signed=True)
                    with self.env.registry.cursor() as slot_cr:
                        slot_cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                                        (0x455442, lock_id))
                        if not slot_cr.fetchone()[0]:
                            raise EtaRequestDeferred()
                        if deadline is not None and time.monotonic() + search_delay + 1 >= deadline:
                            raise EtaRequestDeferred()
                        # Sleep under the shared API lock, including across workers.
                        time.sleep(search_delay)
                        response = send(method, url, timeout=request_timeout, **kwargs)
                else:
                    response = send(method, url, timeout=request_timeout, **kwargs)
            except requests.RequestException:
                if attempt == request_attempts - 1:
                    raise
                if deadline is not None and time.monotonic() + 2 ** attempt + 2 >= deadline:
                    raise EtaRequestDeferred()
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 401 and refresh_auth is None and len(self) == 1:
                refresh_auth = lambda: self.config_id._eta_auth_headers(
                    self.kind, session=request_session, force_refresh=True)[1]
            if response.status_code == 401 and refresh_auth:
                response.close()
                kwargs['headers'].update(refresh_auth())
                return self._request(
                    method, url, allow_no_result=allow_no_result,
                    allow_search_limit=allow_search_limit,
                    request_session=request_session, request_attempts=request_attempts,
                    rate_config=rate_config, deadline=deadline, timeout=timeout,
                    refresh_auth=False, raw_response=raw_response, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                delay = eta_retry_delay(response.headers.get('Retry-After'), attempt)
                _logger.warning('ETA transient HTTP status=%s endpoint=%s attempt=%s delay=%.1fs',
                                response.status_code, urlsplit(url).path, attempt + 1, delay)
                response.close()
                if rate_config is not None:
                    rate_config._defer_detail_requests(endpoint, delay)
                    # Leave this UUID queued; do not hit other UUIDs during a throttle.
                    raise EtaRequestDeferred()
                if attempt < request_attempts - 1 and delay <= 30 and (
                        deadline is None or time.monotonic() + delay + 2 < deadline):
                    time.sleep(delay)
                    continue
                if search_owner is not None:
                    raise EtaRequestDeferred(search_owner, endpoint, delay)
                if len(self) == 1:
                    # Package polling also honors long Retry-After values.
                    raise EtaRequestDeferred(delay=delay)
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
                    if 'page' in message and 'size' in message and 'receipts/search' in url:
                        raise EtaPageSizeError()
                    oversized_query = (code == 'ValidationError' and
                                       'query will return approximately' in message and
                                       'should be under' in message and
                                       'documents' in message)
                    if allow_search_limit and (code == 'OperationExceedsLimit' or oversized_query):
                        raise EtaSearchLimit()
                    if (allow_no_result and code == 'InvalidInput' and
                            'criteria does not return any results' in message):
                        raise EtaSearchNoResult()
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
                if raw_response:
                    return response
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                endpoint = urlsplit(response.url)
                request_target = f'{method} {endpoint.netloc}{endpoint.path}'
                detail = ''
                try:
                    error_body = response.json()
                except ValueError:
                    error_body = {}
                detail = eta_error_codes(error_body)
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
                response.close()
                raise EtaHttpError(error_message, response.status_code) from exc
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
