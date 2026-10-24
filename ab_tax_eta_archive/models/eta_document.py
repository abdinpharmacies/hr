import json
from datetime import datetime, timezone
import pytz

from odoo import fields, models, _
from odoo.exceptions import ValidationError


def eta_datetime(value):
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError) as exc:
        raise ValidationError(_('ETA returned an invalid document timestamp.')) from exc
    if parsed.tzinfo is None:
        raise ValidationError(_('ETA returned a timestamp without a time zone.'))
    return fields.Datetime.to_string(parsed.astimezone(timezone.utc).replace(tzinfo=None))


def eta_report_date(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed.astimezone(pytz.timezone('Africa/Cairo')).date()


class EtaInvoice(models.Model):
    _name = 'ab_tax_eta_archive_invoice'
    _description = 'ETA Invoice'
    _order = 'received_at desc, id desc'
    _rec_name = 'internal_id'

    config_id = fields.Many2one('ab_tax_eta_archive_config', required=True, ondelete='restrict', readonly=True)
    uuid = fields.Char(required=True, index=True, readonly=True)
    internal_id = fields.Char(readonly=True)
    submission_uuid = fields.Char(readonly=True)
    direction = fields.Selection([('sent', 'Sent'), ('received', 'Received')], required=True, index=True, readonly=True)
    document_type = fields.Char(readonly=True)
    status = fields.Char(readonly=True)
    issuer_id = fields.Char(readonly=True)
    issuer_name = fields.Char(readonly=True)
    receiver_id = fields.Char(readonly=True)
    receiver_name = fields.Char(readonly=True)
    issued_at = fields.Datetime(readonly=True)
    received_at = fields.Datetime(required=True, index=True, readonly=True)
    report_date = fields.Date(string='Issue Date', required=True, index=True, readonly=True)
    total = fields.Float(digits=(16, 3), readonly=True)
    currency = fields.Char(readonly=True)
    raw_json = fields.Text(readonly=True, groups='ab_tax_eta_archive.group_eta_manager')

    _unique_uuid = models.Constraint('UNIQUE(config_id, uuid, direction)', 'ETA invoice UUID must be unique per connection and direction.')

    def _eta_values(self, item, direction, config):
        if (not isinstance(item, dict) or not item.get('uuid') or
                not item.get('dateTimeReceived') or not item.get('dateTimeIssued')):
            raise ValidationError(_('ETA returned an invoice without a UUID, issue timestamp, or received timestamp.'))
        return {
            'config_id': config.id, 'uuid': item['uuid'], 'internal_id': item.get('internalId'),
            'submission_uuid': item.get('submissionUUID'), 'direction': direction,
            'document_type': item.get('typeName'), 'status': item.get('status'),
            'issuer_id': item.get('issuerId'), 'issuer_name': item.get('issuerName'),
            'receiver_id': item.get('receiverId'), 'receiver_name': item.get('receiverName'),
            'issued_at': eta_datetime(item.get('dateTimeIssued')),
            'received_at': eta_datetime(item['dateTimeReceived']),
            'report_date': eta_report_date(item['dateTimeIssued']),
            'total': item.get('total') or 0.0,
            'currency': 'EGP',
            'raw_json': json.dumps(item, ensure_ascii=False, sort_keys=True),
        }


class EtaReceipt(models.Model):
    _name = 'ab_tax_eta_archive_receipt'
    _description = 'ETA Receipt'
    _order = 'received_at desc, id desc'
    _rec_name = 'receipt_number'

    config_id = fields.Many2one('ab_tax_eta_archive_config', required=True, ondelete='restrict', readonly=True)
    uuid = fields.Char(required=True, index=True, readonly=True)
    receipt_number = fields.Char(readonly=True)
    pos_serial_number = fields.Char(readonly=True, index=True)
    submission_uuid = fields.Char(readonly=True)
    direction = fields.Selection([('sent', 'Sent'), ('received', 'Received')], required=True, index=True, readonly=True)
    document_type = fields.Char(readonly=True)
    status = fields.Char(readonly=True)
    issuer_id = fields.Char(readonly=True)
    issuer_name = fields.Char(readonly=True)
    receiver_id = fields.Char(readonly=True)
    receiver_name = fields.Char(readonly=True)
    issued_at = fields.Datetime(readonly=True)
    received_at = fields.Datetime(required=True, index=True, readonly=True)
    report_date = fields.Date(string='Issue Date', required=True, index=True, readonly=True)
    total = fields.Float(digits=(16, 3), readonly=True)
    currency = fields.Char(readonly=True)
    raw_json = fields.Text(readonly=True, groups='ab_tax_eta_archive.group_eta_manager')

    _unique_uuid = models.Constraint('UNIQUE(config_id, uuid, direction)', 'ETA receipt UUID must be unique per connection and direction.')

    def _eta_values(self, item, direction, config):
        if (not isinstance(item, dict) or not item.get('uuid') or
                not item.get('dateTimeReceived') or not item.get('dateTimeIssued')):
            raise ValidationError(_('ETA returned a receipt without a UUID, issue timestamp, or received timestamp.'))
        return {
            'config_id': config.id, 'uuid': item['uuid'], 'receipt_number': item.get('receiptNumber'),
            'pos_serial_number': item.get('posSerialNumber') or item.get('deviceSerialNumber'),
            'submission_uuid': item.get('submissionUuid'), 'direction': direction,
            'document_type': item.get('typeName'), 'status': item.get('status'),
            'issuer_id': item.get('issuerId'), 'issuer_name': item.get('issuerName'),
            'receiver_id': item.get('receiverId'), 'receiver_name': item.get('receiverName'),
            'issued_at': eta_datetime(item.get('dateTimeIssued')),
            'received_at': eta_datetime(item['dateTimeReceived']),
            'report_date': eta_report_date(item['dateTimeIssued']),
            'total': item.get('totalAmount') or 0.0,
            'currency': item.get('currency') or 'EGP',
            'raw_json': json.dumps(item, ensure_ascii=False, sort_keys=True),
        }
