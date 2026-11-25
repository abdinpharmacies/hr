import io
import json
import logging
import zipfile
from datetime import datetime, time as day_time, timedelta, timezone
from urllib.parse import quote

import pytz
import requests

from odoo import fields, models, _
from odoo.exceptions import ValidationError
from .eta_export import _detail_values
from .eta_sync import EtaHttpError, EtaSearchLimit, EtaSearchNoResult
from .eta_policy import TICK, api_inclusive_end, split_interval

_logger = logging.getLogger(__name__)


def package_items(content):
    """Read bounded JSON ZIP content in memory; never extract archive paths."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) > 4000 or sum(item.file_size for item in members) > 200 * 1024 * 1024:
            raise ValueError('Package exceeds the supported expanded size')
        items = []
        found = False
        for member in members:
            if not member.filename.lower().endswith('.json'):
                continue
            found = True
            payload = json.loads(archive.read(member).decode('utf-8-sig'))
            if isinstance(payload, list):
                page = payload
            elif isinstance(payload, dict):
                page = ([payload] if 'uuid' in payload or 'receipt' in payload else
                        payload.get('receipts', payload.get('result')))
            else:
                page = None
            if not isinstance(page, list) or any(not isinstance(item, dict) for item in page):
                raise ValueError('Unsupported receipt package JSON structure')
            items.extend(page)
        if not found:
            raise ValueError('Package contains no JSON files')
        return items


def receipt_package_summary(item):
    """Convert ReceiptExtended to the same summary used by search imports."""
    receipt = item.get('receipt')
    if not receipt and 'seller' in item and 'itemData' in item:
        receipt = item
    if not isinstance(receipt, dict):
        return item
    seller = receipt.get('seller') or {}
    buyer = receipt.get('buyer') or {}
    doc_type = receipt.get('documentType') or {}
    return {
        **receipt,
        'dateTimeReceived': item.get('dateTimeReceived') or receipt.get('dateTimeReceived'),
        'dateTimeIssued': receipt.get('dateTimeIssued') or item.get('dateTimeIssued'),
        'submissionUuid': item.get('submissionUUID') or receipt.get('submissionUuid'),
        'issuerId': seller.get('sellerId'), 'issuerName': seller.get('sellerName'),
        'receiverId': buyer.get('buyerId'), 'receiverName': buyer.get('buyerName'),
        'posSerialNumber': seller.get('deviceSerialNumber'),
        'typeName': doc_type.get('receiptType'),
    }


class EtaPackage(models.Model):
    _inherit = 'ab_tax_eta_archive_package'

    import_offset = fields.Integer(readonly=True)
    imported = fields.Boolean(readonly=True)
    full_details = fields.Boolean(readonly=True)
    notified_at = fields.Datetime(readonly=True)
    status_page = fields.Integer(readonly=True)
    status_checked_at = fields.Datetime(readonly=True)
    remote_status = fields.Selection([
        ('1', 'Preparing'), ('2', 'Available'), ('3', 'Preparation failed'),
        ('4', 'Expired or deleted'), ('missing', 'Package not found')], readonly=True)
    remote_error = fields.Char(readonly=True)
    request_history = fields.Json(readonly=True, copy=False,
                                  groups='ab_tax_eta_archive.group_eta_manager')
    state = fields.Selection(selection_add=[('ready', 'Ready'), ('importing', 'Importing')],
                             ondelete={'ready': 'set default', 'importing': 'set default'})


class EtaPackageSync(models.Model):
    _inherit = 'ab_tax_eta_archive_sync'

    def _poll_receipt_package(self, part, api_url, headers, refresh_auth):
        """Read one documented request-list page; never infer readiness from an ID."""
        payload = self._request(
            'GET', f'{api_url}/api/v1.0/receiptpackages/requests', headers=headers,
            params={'pageNo': part.status_page, 'pageSize': 20}, refresh_auth=refresh_auth)
        rows, metadata = payload.get('result'), payload.get('metadata')
        if not isinstance(rows, list) or not isinstance(metadata, dict):
            raise ValidationError(_('ETA package status response is invalid.'))
        pages = metadata.get('totalPages')
        if type(pages) is not int or pages < 0 or any(not isinstance(row, dict) for row in rows):
            raise ValidationError(_('ETA package status response is invalid.'))
        match = next((row for row in rows if str(row.get('packageId')) == part.package_id), None)
        now = fields.Datetime.now()
        if match:
            status = '4' if match.get('isExpired') else str(match.get('status'))
            if status not in ('1', '2', '3', '4'):
                raise ValidationError(_('ETA package status response is invalid.'))
            error = False
            if status == '3':
                error = _('ETA failed to prepare package %(package)s.', package=part.package_id)
            elif status == '4':
                error = _('ETA package %(package)s has expired or was deleted.', package=part.package_id)
            part.write({'remote_status': status, 'remote_error': error,
                        'status_checked_at': now, 'status_page': 0})
            if status == '1':
                self.next_attempt_at = now + timedelta(minutes=5)
            _logger.info('ETA package status: connection=%s day=%s direction=%s package=%s status=%s',
                         self.config_id.id, self.report_date, self.direction, part.package_id, status)
            return status == '2'
        last_page = part.status_page + 1 >= max(pages, 1)
        part.write({'status_page': 0 if last_page else part.status_page + 1,
                    'remote_status': 'missing' if last_page else False,
                    'status_checked_at': now if last_page else False,
                    'remote_error': (_('ETA package %(package)s was not found; verify its ID and credentials.',
                                      package=part.package_id) if last_page else False)})
        return False

    def _retrieve_historical_receipts(self):
        self.ensure_one()
        cairo = pytz.timezone('Africa/Cairo')
        start = cairo.localize(datetime.combine(self.report_date, day_time.min)).astimezone(timezone.utc)
        end = cairo.localize(datetime.combine(self.report_date + timedelta(days=1),
                                              day_time.min)).astimezone(timezone.utc) - timedelta(milliseconds=1)
        packages = self.env['ab_tax_eta_archive_package']
        parts = packages.search([('sync_id', '=', self.id)])
        if not parts:
            packages.create({'sync_id': self.id, 'start_at': start.replace(tzinfo=None),
                             'end_at': end.replace(tzinfo=None), 'full_details': True})
            return None
        part = parts.filtered(lambda row: row.state != 'split' and not row.imported).sorted(
            'start_at', reverse=True)[:1]
        if not part:
            return sum(parts.filtered('imported').mapped('item_count')), set()
        if part.payload_json:
            items = json.loads(part.payload_json)
            if not isinstance(items, list):
                raise ValidationError(_('ETA receipt package download is invalid or incomplete.'))
            model = self.env['ab_tax_eta_archive_receipt']
            page = items[part.import_offset:part.import_offset + 200]
            values_by_uuid = {}
            for item in page:
                summary = receipt_package_summary(item)
                values = model._eta_values(summary, self.direction, self.config_id)
                received = datetime.fromisoformat(summary['dateTimeReceived'].replace('Z', '+00:00'))
                received = received.astimezone(timezone.utc).replace(tzinfo=None)
                if not part.start_at <= received < part.end_at + TICK:
                    raise ValidationError(_('ETA returned a document outside the requested Cairo date.'))
                if part.full_details:
                    try:
                        detail = _detail_values(item, 'receipt')
                    except ValueError as exc:
                        raise ValidationError(_('ETA receipt package download is invalid or incomplete.')) from exc
                    values.update(detail_json=json.dumps(detail, ensure_ascii=False),
                                  detail_error=False, detail_attempt_at=fields.Datetime.now())
                values_by_uuid[values['uuid']] = values
            existing = model.search([
                ('config_id', '=', self.config_id.id), ('direction', '=', self.direction),
                ('uuid', 'in', list(values_by_uuid)),
            ])
            by_uuid = {record.uuid: record for record in existing}
            creates = []
            for uuid, values in values_by_uuid.items():
                if uuid in by_uuid:
                    by_uuid[uuid].write(values)
                else:
                    creates.append(values)
            if creates:
                model.create(creates)
            offset = part.import_offset + len(page)
            part.write({'import_offset': offset, 'imported': offset >= len(items),
                        'state': 'done' if offset >= len(items) else 'importing',
                        'item_count': len(items)})
            self.item_count = sum(parts.mapped('import_offset'))
            _logger.info('ETA historical package import: connection=%s day=%s direction=%s '
                         'package=%s saved=%s total=%s', self.config_id.id, self.report_date,
                         self.direction, part.package_id, offset, len(items))
            return None
        # Packages use taxpayer ERP credentials, including for receipts.
        api_url, headers = self.env['ab_tax_eta_archive_export']._detail_headers(
            self.config_id, 'invoice', session=self.env.context.get('eta_request_session'))
        if not part.package_id:
            query = {
                'represntedTaxpayerTypeId': 'Issuer' if self.direction == 'sent' else 'Receiver',
                'dateFrom': part.start_at.replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds'),
                'dateTo': api_inclusive_end(part.end_at.replace(tzinfo=timezone.utc)),
            }
            try:
                payload = self._request('POST', f'{api_url}/api/v1.0/receiptpackages/requests',
                                        headers=headers,
                                        json={'type': 'Full', 'format': 'JSON', 'queryParameters': query},
                                        allow_no_result=True, allow_search_limit=True,
                                        refresh_auth=lambda: self.config_id._eta_auth_headers(
                                            'invoice', session=self.env.context.get('eta_request_session'),
                                            force_refresh=True)[1])
            except EtaSearchLimit:
                first, second = split_interval(part.start_at, part.end_at)
                packages.create([{'sync_id': self.id, 'start_at': left, 'end_at': right,
                                  'full_details': True} for left, right in (first, second)])
                part.state = 'split'
            except EtaSearchNoResult:
                part.write({'state': 'done', 'imported': True, 'item_count': 0})
            else:
                result = payload.get('result') if isinstance(payload.get('result'), dict) else payload
                package_id = result.get('packageId') or result.get('requestId') or result.get('id')
                if not package_id:
                    raise ValidationError(_('ETA receipt package request returned no package ID.'))
                part.write({'package_id': str(package_id), 'full_details': True})
                _logger.info('ETA historical package requested: connection=%s package=%s day=%s',
                             self.config_id.id, part.package_id, self.report_date)
            return None
        refresh_auth = lambda: self.config_id._eta_auth_headers(
            'invoice', session=self.env.context.get('eta_request_session'), force_refresh=True)[1]
        fresh_status = part.status_checked_at and part.status_checked_at > (
            fields.Datetime.now() - timedelta(minutes=5))
        if fresh_status and part.remote_status == '4':
            history = list(part.request_history or [])
            if len(history) >= 2:
                raise ValidationError(_('ETA package renewal limit reached; verify the request in the ETA portal.'))
            history.append({'package_id': part.package_id, 'status': part.remote_status,
                            'error': part.remote_error,
                            'replaced_at': fields.Datetime.to_string(fields.Datetime.now())})
            self.last_error = part.remote_error
            # Replace only a confirmed expired remote request, retaining its
            # history and the same date window. Archived documents are untouched.
            part.write({'request_history': history, 'package_id': False,
                        'remote_status': False, 'remote_error': False,
                        'status_checked_at': False, 'status_page': 0})
            self.next_attempt_at = fields.Datetime.now() + timedelta(minutes=5)
            return None
        if fresh_status and part.remote_status in ('3', '4', 'missing'):
            raise ValidationError(part.remote_error)
        if not fresh_status or part.remote_status != '2':
            self._poll_receipt_package(part, api_url, headers, refresh_auth)
            return None
        try:
            response = self._request(
                'GET', f'{api_url}/api/v1.0/receiptpackages/{quote(part.package_id, safe="")}',
                headers={**headers, 'Accept': 'application/octet-stream'},
                timeout=(5, 15), stream=True, raw_response=True,
                refresh_auth=lambda: {**refresh_auth(), 'Accept': 'application/octet-stream'})
        except EtaHttpError as exc:
            if exc.status_code not in (400, 404):
                raise
            # Readiness may have changed since the previous status check. Retain
            # the package ID and all saved rows; do not guess or recreate it.
            if self._poll_receipt_package(part, api_url, headers, refresh_auth):
                raise
            self.last_error = str(exc)
            return None
        with response:
            if response.status_code == 204:
                part.write({'remote_status': '1', 'status_checked_at': fields.Datetime.now()})
                self.next_attempt_at = fields.Datetime.now() + timedelta(minutes=5)
                _logger.info('ETA historical package preparing: package=%s', part.package_id)
                return None
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 50 * 1024 * 1024:
                    raise ValidationError(_('ETA receipt package download is invalid or incomplete.'))
        try:
            items = package_items(content)
        except (ValueError, zipfile.BadZipFile, UnicodeError, RuntimeError) as exc:
            raise ValidationError(_('ETA receipt package download is invalid or incomplete.')) from exc
        part.write({'payload_json': json.dumps(items, ensure_ascii=False),
                    'item_count': len(items), 'state': 'ready'})
        return None
