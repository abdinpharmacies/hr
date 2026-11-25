"""Bounded, restartable retrieval. Each call saves at most one API page."""
import copy
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .eta_policy import CAIRO, TICK, api_stamp, api_inclusive_end, day_bounds, split_interval
from .eta_sync import (EtaRequestDeferred, EtaSearchLimit, EtaSearchNoResult,
                       ETA_MAX_RECEIPTS_PER_SEARCH, ETA_RECEIPT_SEARCH_DAYS, eta_task_lock)

_logger = logging.getLogger(__name__)


class EtaRetrieval(models.Model):
    _inherit = 'ab_tax_eta_archive_sync'

    state = fields.Selection(selection_add=[('partial', 'Partial')],
                             ondelete={'partial': 'set default'})
    checkpoint = fields.Json(readonly=True, copy=False,
                             groups='ab_tax_eta_archive.group_eta_manager')
    last_error = fields.Text(readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    next_attempt_at = fields.Datetime(readonly=True, copy=False)

    @api.model
    def _cron_sync(self, kind='invoice'):
        if kind not in ('invoice', 'receipt'):
            raise ValueError('Unsupported ETA stream')
        # Separate cursor keeps the advisory lock alive across progress commits.
        with eta_task_lock(self.env, 10 if kind == 'invoice' else 11) as acquired:
            if not acquired:
                return
            today = datetime.now(CAIRO).date()
            deadline = min(time.monotonic() + 25,
                           self.env.context.get('cron_end_time', float('inf')) - 2)
            for config in self.env['ab_tax_eta_archive_config'].search(fields.Domain('active', '=', True)):
                latest = min(today - timedelta(days=1),
                             config._retrieval_cutoff().astimezone(CAIRO).date())
                if config.start_date > latest:
                    continue
                if not self._ensure_run_days(config, latest, kind=kind):
                    return
                retry_before = fields.Datetime.now() - timedelta(minutes=5)
                runs = self.search(fields.Domain([
                    ('config_id', '=', config.id), ('kind', '=', kind),
                    ('report_date', '>=', config.start_date), ('report_date', '<=', latest),
                    '|', ('error_message', '=', False), '|', ('last_run_at', '=', False),
                    ('last_run_at', '<=', retry_before),
                    '|', ('state', '!=', 'done'), '&',
                    ('report_date', '>=', today - timedelta(days=14)),
                    ('last_run_at', '<', day_bounds(today)[0].replace(tzinfo=None)),
                ]), order='report_date desc, kind, direction')
                with requests.Session() as session:
                    for run in runs:
                        while time.monotonic() + 2 < deadline:
                            runner = run.with_context(eta_request_session=session,
                                                      eta_retrieval_deadline=deadline)
                            if runner._attempt() is False:
                                break
                            if self.env.context.get('cron_id'):
                                if not self.env['ir.cron']._commit_progress(1, remaining=1):
                                    return
                            if run.state in ('done', 'error') or run.error_message:
                                break
                        if time.monotonic() + 2 >= deadline:
                            return
            if self.env.context.get('cron_id'):
                # The regular interval resumes partial work, without a tight loop.
                self.env['ir.cron']._commit_progress(remaining=0)

    def _cron_attempt(self, run):
        with requests.Session() as session:
            result = run.with_context(eta_request_session=session,
                                      eta_retrieval_deadline=time.monotonic() + 25)._attempt()
        return result is not False, result is not False

    def action_retry(self):
        for run in self:
            self._cron_attempt(run)

    def _attempt(self, auth_cache=None):
        self.ensure_one()
        if self.next_attempt_at and self.next_attempt_at > fields.Datetime.now():
            return False
        # Negative IDs cannot collide with the positive task locks. Manual and
        # cron requests share this lock; backend death releases it automatically.
        with eta_task_lock(self.env, -self.id) as acquired:
            if not acquired:
                return False
            try:
                with self.env.cr.savepoint():
                    if not self.try_lock_for_update():
                        return False
                    self.invalidate_recordset()
                    before = (self.checkpoint, self.item_count,
                              [(p.id, p.state, p.package_id, p.import_offset, bool(p.payload_json),
                                p.status_page, p.remote_status)
                               for p in self.package_ids])
                    result = self._retrieve()
                    if result is None:
                        self.write({'state': 'partial' if self.checkpoint or self.item_count
                                    or self.package_ids else 'pending',
                                    'last_run_at': fields.Datetime.now(), 'error_message': False,
                                    'completed_at': False})
                        after = (self.checkpoint, self.item_count,
                                 [(p.id, p.state, p.package_id, p.import_offset, bool(p.payload_json),
                                   p.status_page, p.remote_status)
                                  for p in self.package_ids])
                        if before == after:
                            return False
                    else:
                        count, _dates = result
                        self.segment_ids.filtered(lambda row: row.state == 'error').write({'state': 'resolved'})
                        self.write({'state': 'done', 'item_count': count,
                                    'last_run_at': fields.Datetime.now(),
                                    'completed_at': fields.Datetime.now(), 'error_message': False,
                                    'next_receipt_window_at': False, 'next_attempt_at': False})
            except EtaRequestDeferred as exc:
                if exc.config is not None:
                    exc.config._defer_detail_requests(exc.endpoint, exc.delay)
                if exc.delay:
                    self.next_attempt_at = fields.Datetime.now() + timedelta(seconds=exc.delay)
                return False
            except (requests.RequestException, UserError, ValueError, KeyError, TypeError) as exc:
                # Page writes and its checkpoint roll back together. Earlier pages
                # remain committed; retry starts at this exact page/window.
                message = (self._checkpoint_label() + '\n' + str(exc))[:2000]
                self.write({'state': 'partial' if self.checkpoint or self.item_count else 'error',
                            'last_run_at': fields.Datetime.now(), 'completed_at': False,
                            'error_message': message, 'last_error': message})
                _logger.warning('ETA retrieval failed config=%s kind=%s direction=%s day=%s '
                                'checkpoint=%s error_type=%s', self.config_id.id, self.kind,
                                self.direction, self.report_date,
                                self._checkpoint_label(), type(exc).__name__)
                return False
        self.env['ab_tax_eta_archive_export']._wake_detail_cron(self.kind)
        if result is not None:
            model = self.env['ab_tax_eta_archive_' + self.kind]
            start, end = day_bounds(self.report_date)
            for issue_day, in model._read_group(fields.Domain([
                    ('config_id', '=', self.config_id.id), ('direction', '=', self.direction),
                    ('received_at', '>=', start.replace(tzinfo=None)),
                    ('received_at', '<', end.replace(tzinfo=None))]), ['report_date:day'], []):
                self.env['ab_tax_eta_archive_export']._queue_generation(
                    self.config_id, issue_day, self.kind, self.direction)
        return True

    def _checkpoint_label(self):
        queue = (self.checkpoint or {}).get('windows') or []
        if not queue:
            part = self.package_ids.filtered(lambda row: row.state != 'split' and not row.imported).sorted(
                'start_at', reverse=True)[:1]
            if part:
                return 'package=%s window=%s/%s imported=%s' % (
                    part.package_id or 'not-requested', part.start_at, part.end_at, part.import_offset)
            return 'new retrieval'
        win = queue[0]
        # Tokens and document identifiers must never appear in logs.
        return '%s/%s page=%s saved=%s' % (
            win['start'], win['end'], win.get('page', 1), win.get('count', 0))

    def _retrieve(self, auth_cache=None):
        self.ensure_one()
        start, full_end = day_bounds(self.report_date)
        cutoff = self.config_id._retrieval_cutoff()
        end = min(full_end, cutoff)
        if start >= end:
            return None
        today = datetime.now(CAIRO).date()
        if self.kind == 'receipt' and self.report_date < today - timedelta(days=ETA_RECEIPT_SEARCH_DAYS):
            # Do not start a historical package until its entire day is eligible.
            if full_end > cutoff:
                return None
            return self._retrieve_historical_receipts()

        checkpoint = copy.deepcopy(self.checkpoint or {})
        checkpoint['basis'] = 'received'
        windows = checkpoint.setdefault('windows', [])
        covered = (datetime.fromisoformat(checkpoint['covered_until'].replace('Z', '+00:00'))
                   if checkpoint.get('covered_until') else None)
        covered = covered.replace(tzinfo=timezone.utc) if covered else start
        if (not self.checkpoint and self.state != 'done' and self.kind == 'receipt'
                and self.next_receipt_window_at):
            legacy = json.loads(self.receipt_issue_dates_json or '{}')
            resume_at = self.next_receipt_window_at.replace(tzinfo=timezone.utc)
            if isinstance(legacy, dict) and legacy.get('basis') == 'received' and start <= resume_at < end:
                covered = resume_at
        if not windows and covered < end:
            windows.append({'start': api_stamp(covered), 'end': api_stamp(end - TICK)})
        if not windows:
            return (self.item_count, set()) if covered >= full_end else None
        win = windows[0]
        left = datetime.fromisoformat(win['start'].replace('Z', '+00:00'))
        right = datetime.fromisoformat(win['end'].replace('Z', '+00:00'))
        # A changed safety setting must never allow an old checkpoint past cutoff.
        if right >= cutoff:
            return None
        api_url, headers = self.config_id._eta_auth_headers(
            self.kind, session=self.env.context.get('eta_request_session'))
        page_started = time.monotonic()
        try:
            if self.kind == 'invoice':
                params = {'submissionDateFrom': api_stamp(left), 'submissionDateTo': api_inclusive_end(right),
                          'direction': 'Sent' if self.direction == 'sent' else 'Received', 'pageSize': 100}
                if win.get('token'):
                    params['continuationToken'] = win['token']
                payload = self._request('GET', api_url + '/api/v1.0/documents/search',
                                        headers=headers, params=params)
                page, metadata = payload.get('result'), payload.get('metadata')
                if not isinstance(page, list) or not isinstance(metadata, dict):
                    raise ValidationError(_('ETA invoice search returned an invalid page.'))
                token = metadata.get('continuationToken')
                finished = token == 'EndofResultSet'
                tokens = win.setdefault('tokens', [])
                if not finished and (not token or token in tokens):
                    raise ValidationError(_('ETA invoice pagination stopped before the final page.'))
                if not finished:
                    tokens.append(token)
                    win['token'] = token
            else:
                params = {'Direction': 'Submitted' if self.direction == 'sent' else 'Received',
                          'DateTimeReceivedFrom': api_stamp(left), 'DateTimeReceivedTo': api_inclusive_end(right),
                          'SortBy': 'DateTimeReceived', 'SortDir': 'Asc'}
                payload, size = self._request_receipt_page(
                    api_url, headers, params, win.get('page', 1), win.get('size', 100))
                page, metadata = self._receipt_page_and_metadata(payload)
                total = metadata.get('totalCount')
                if type(total) is not int or total < 0:
                    raise ValidationError(_('ETA receipt search returned invalid pagination metadata.'))
                if total >= ETA_MAX_RECEIPTS_PER_SEARCH:
                    raise EtaSearchLimit()
                if win.get('total', total) != total:
                    raise ValidationError(_('ETA receipt count changed while reading the result pages.'))
                win.update(total=total, size=size)
                count = win.get('count', 0) + len(page)
                if count > total or (not page and count != total):
                    raise ValidationError(_('ETA receipt page count does not match the reported total.'))
                finished = count == total
        except EtaSearchNoResult:
            if win.get('page', 1) != 1:
                raise ValidationError(_('ETA receipt count changed while reading the result pages.'))
            page, finished = [], True
        except EtaSearchLimit:
            first, second = split_interval(left, right)
            windows[:1] = [{'start': api_stamp(a), 'end': api_stamp(b)} for a, b in (first, second)]
            self.checkpoint = checkpoint
            return None

        model = self.env['ab_tax_eta_archive_' + self.kind]
        values_by_uuid = {}
        seen = set(win.get('uuids', []))
        for item in page:
            values = model._eta_values(item, self.direction, self.config_id)
            timestamp = datetime.fromisoformat(item['dateTimeReceived'].replace('Z', '+00:00'))
            if not left <= timestamp < right + TICK:
                raise ValidationError(_('ETA returned a document outside the requested Cairo date.'))
            uuid = values['uuid']
            if uuid in values_by_uuid or (self.kind == 'receipt' and uuid in seen):
                raise ValidationError(_('ETA returned duplicate document UUIDs for one retrieval.'))
            values_by_uuid[uuid] = values
        existing = model.search(fields.Domain([('config_id', '=', self.config_id.id),
                                 ('direction', '=', self.direction),
                                 ('uuid', 'in', list(values_by_uuid))])) if values_by_uuid else model
        by_uuid = {row.uuid: row for row in existing}
        creates = []
        for uuid, values in values_by_uuid.items():
            row = by_uuid.get(uuid)
            if row:
                if row.raw_json != values['raw_json'] or row.report_date != values['report_date']:
                    row.write(values)
            else:
                creates.append(values)
        if creates:
            model.create(creates)
        win['count'] = win.get('count', 0) + len(page)
        win['page'] = win.get('page', 1) + 1
        if self.kind == 'receipt':
            win['uuids'] = sorted(seen | set(values_by_uuid))
        if finished:
            if self.kind == 'receipt':
                self._record_receipt_segment_done(left, right, win['count'], False, False)
            checkpoint['covered_until'] = api_stamp(right + TICK)
            windows.pop(0)
        if self.kind == 'receipt':
            self.next_receipt_window_at = (
                datetime.fromisoformat(windows[0]['start'].replace('Z', '+00:00'))
                if windows else right + TICK).replace(tzinfo=None)
        self.write({'checkpoint': checkpoint, 'item_count': model.search_count(fields.Domain([
            ('config_id', '=', self.config_id.id), ('direction', '=', self.direction),
            ('received_at', '>=', start.replace(tzinfo=None)),
            ('received_at', '<', full_end.replace(tzinfo=None)),
        ]))})
        _logger.info('ETA page saved config=%s kind=%s direction=%s day=%s window=%s/%s '
                     'page=%s rows=%s saved=%s finished=%s elapsed=%.3fs', self.config_id.id, self.kind,
                     self.direction, self.report_date, win['start'], win['end'],
                     win['page'] - 1, len(page), self.item_count, finished,
                     time.monotonic() - page_started)
        if not windows and right + TICK >= full_end:
            # A later explicit retry starts a fresh idempotent reconciliation.
            self.checkpoint = False
            return self.item_count, set()
        return None
