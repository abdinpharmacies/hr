import base64
import hashlib
import io
import json
import logging
from datetime import datetime, timedelta, timezone

import pytz

import requests
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CATEGORIES = (
    ('sent_invoice', 'Sent invoices', 'invoice', 'sent'),
    ('sent_receipt', 'Sent receipts', 'receipt', 'sent'),
    ('received_invoice', 'Purchase invoices', 'invoice', 'received'),
    ('received_receipt', 'Purchase receipts', 'receipt', 'received'),
)


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
    filename = fields.Char(required=True, readonly=True)
    file_data = fields.Binary(attachment=True, readonly=True)
    record_count = fields.Integer(readonly=True)
    checked_through = fields.Date(string='Submission Days Checked Through', readonly=True)
    telegram_sent_at = fields.Datetime(readonly=True)
    telegram_message_id = fields.Char(readonly=True)
    telegram_error = fields.Char(readonly=True)

    _unique_file = models.Constraint(
        'UNIQUE(config_id, report_date, category, revision)',
        'Only one ETA file revision is allowed per day and category.')

    @api.model
    def _cron_export_and_send(self):
        cairo = pytz.timezone('Africa/Cairo')
        today = datetime.now(cairo).date()
        cutoff = today - timedelta(days=4)
        for config in self.env['ab_tax_eta_archive_config'].search([
            ('active', '=', True), ('start_date', '<=', cutoff),
        ]):
            pending = self.search([('config_id', '=', config.id),
                                   ('report_date', '<=', cutoff),
                                   ('report_date', '>=', config.telegram_start_date or cutoff),
                                   ('telegram_sent_at', '=', False)],
                                  order='report_date asc, category')
            for target in sorted(set(pending.mapped('report_date'))):
                first_submission_day = max(target, config.start_date)
                runs = self.env['ab_tax_eta_archive_sync'].search([
                    ('config_id', '=', config.id),
                    ('report_date', '>=', first_submission_day),
                    ('report_date', '<', today),
                    ('state', '=', 'done'),
                ])
                if len(runs) != (today - first_submission_day).days * 4:
                    continue
                yesterday_runs = runs.filtered(lambda run: run.report_date == today - timedelta(days=1))
                if any(not run.last_run_at or fields.Datetime.to_datetime(run.last_run_at).replace(
                        tzinfo=timezone.utc).astimezone(cairo).date() < today
                       for run in yesterday_runs):
                    continue
                for category, _label, kind, direction in CATEGORIES:
                    export = self.search([
                        ('config_id', '=', config.id), ('report_date', '=', target),
                        ('category', '=', category),
                    ], order='revision desc', limit=1)
                    if not export or not export.telegram_sent_at:
                        export = self._prepare(config, target, category, kind, direction, export=export)
                    if not export.telegram_sent_at:
                        export._send_telegram(checked_through=today - timedelta(days=1))

    @api.model
    def _ensure_files(self, config, report_date):
        for category, _label, kind, direction in CATEGORIES:
            export = self.search([('config_id', '=', config.id),
                                  ('report_date', '=', report_date),
                                  ('category', '=', category)], order='revision desc', limit=1)
            self._prepare(config, report_date, category, kind, direction, export=export)

    @api.model
    def _prepare(self, config, report_date, category, kind, direction, export=None):
        model = self.env['ab_tax_eta_archive_invoice' if kind == 'invoice' else 'ab_tax_eta_archive_receipt']
        records = model.search([('config_id', '=', config.id), ('report_date', '=', report_date),
                                ('direction', '=', direction)],
                               order='issued_at, uuid')
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Invoices' if kind == 'invoice' else 'Receipts'
        identifier = 'Internal ID' if kind == 'invoice' else 'Receipt Number'
        sheet.append(['UUID', identifier, 'Submission UUID', 'Type', 'Status',
                      'Issuer ID', 'Issuer Name', 'Receiver ID', 'Receiver Name',
                      'Issued At (UTC)', 'Received At (UTC)', 'Total', 'Currency'])
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='17426B')
        sheet.freeze_panes = 'A2'
        source_rows = []
        for record in records:
            row = [
                record.uuid,
                record.internal_id if kind == 'invoice' else record.receipt_number,
                record.submission_uuid, record.document_type, record.status,
                record.issuer_id, record.issuer_name, record.receiver_id,
                record.receiver_name,
            ]
            cells = ([_excel_cell(value) for value in row] +
                     [record.issued_at or None, record.received_at,
                      record.total, _excel_cell(record.currency)])
            sheet.append(cells)
            source_rows.append(cells)
        source_digest = hashlib.sha256(
            json.dumps(source_rows, ensure_ascii=False, default=str).encode('utf-8')
        ).hexdigest()
        if export and export.source_digest == source_digest:
            return export
        for row in sheet.iter_rows(min_row=2, min_col=10, max_col=11):
            for cell in row:
                cell.number_format = 'yyyy-mm-dd hh:mm:ss'
        for column, width in enumerate((67, 25, 35, 18, 18, 22, 36, 22, 36,
                                        23, 23, 18, 12), start=1):
            sheet.column_dimensions[get_column_letter(column)].width = width
        sheet.auto_filter.ref = sheet.dimensions
        output = io.BytesIO()
        workbook.save(output)
        revision = export.revision + 1 if export and export.telegram_sent_at else (export.revision if export else 1)
        filename = f'{category}_{report_date}_r{revision}.xlsx'
        values = {
            'config_id': config.id, 'report_date': report_date,
            'category': category, 'revision': revision, 'filename': filename,
            'file_data': base64.b64encode(output.getvalue()),
            'record_count': len(records), 'source_digest': source_digest,
        }
        if export and not export.telegram_sent_at:
            export.write(values)
            return export
        if export:
            values['supersedes_id'] = export.id
        return self.create(values)

    def _send_telegram(self, checked_through=None):
        self.ensure_one()
        config = self.config_id
        if not config.telegram_bot_token or not config.telegram_chat_id:
            self.telegram_error = _('Configure the Telegram bot token and group chat ID.')
            return
        label = next(row[1] for row in CATEGORIES if row[0] == self.category)
        caption = f'{_(label)} - {self.report_date}'
        if self.revision > 1:
            caption += ' - ' + _('Revision %(number)s', number=self.revision)
        try:
            response = requests.post(
                f'https://api.telegram.org/bot{config.telegram_bot_token}/sendDocument',
                data={'chat_id': config.telegram_chat_id,
                      'caption': caption},
                files={'document': (self.filename, base64.b64decode(self.file_data),
                                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get('ok'):
                raise UserError(_('Telegram rejected the ETA file.'))
        except (requests.RequestException, ValueError, UserError):
            _logger.warning('ETA Telegram delivery failed for %s', self.filename)
            self.telegram_error = _('Telegram delivery failed; this file will be retried.')
            return
        self.write({'telegram_sent_at': fields.Datetime.now(),
                    'checked_through': checked_through,
                    'telegram_message_id': str(payload.get('result', {}).get('message_id', '')),
                    'telegram_error': False})
