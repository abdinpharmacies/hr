import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL


class WebsiteEvent(models.Model):
    _name = 'ab_oms_sync_event'
    _inherit = 'ab_crm_scoped'
    _description = 'OMS Website Event'
    _rec_name = 'event_id'
    _order = 'id desc'

    event_id = fields.Char(required=True, readonly=True, index=True)
    source = fields.Char(required=True, readonly=True)
    reference = fields.Char(required=True, readonly=True)
    revision = fields.Integer(required=True, readonly=True)
    payload = fields.Json(required=True, readonly=True)
    digest = fields.Char(required=True, readonly=True)
    state = fields.Selection([('received', 'Received'), ('applied', 'Applied'), ('obsolete', 'Obsolete'), ('review', 'Manual Review')], default='received', required=True, readonly=True)
    request_id = fields.Many2one('ab_oms_request', readonly=True, ondelete='restrict', check_company=True)
    last_error = fields.Text(readonly=True)
    review_note = fields.Text()
    _event_unique = models.Constraint('UNIQUE(source, event_id)', 'This website event was already received.')
    _revision_unique = models.Constraint('UNIQUE(source, reference, revision)', 'This website revision was already received.')

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            raise AccessError(_('Website events are managed by the integration service.'))
        return super().create(values_list)

    def write(self, values):
        if not _INTERNAL.get() and set(values) - {'review_note'}:
            raise AccessError(_('Website events are managed by the integration service.'))
        return super().write(values)

    @api.model
    def receive_event(self, channel_code, event):
        if not self.env.user.has_group('ab_oms_sync.group_sync'):
            raise AccessError(_('Only the synchronization service can receive website events.'))
        channel = self.env['ab_crm_channel'].search(fields.Domain('code', '=', channel_code) & fields.Domain('provider', '=', 'website'), limit=1)
        channel.ensure_one()
        channel._authorize('read')
        channel.lock_for_update()
        if (not isinstance(event, dict) or type(event.get('revision')) is not int or event['revision'] < 1
                or any(not isinstance(event.get(k), str) or not event[k] or len(event[k]) > 256 for k in ('event_id', 'reference', 'source'))
                or event['source'] != channel_code or not isinstance(event.get('snapshot'), dict)):
            raise ValidationError(_('Invalid website event.'))
        digest = hashlib.sha256(json.dumps(event, sort_keys=True, allow_nan=False).encode()).hexdigest()
        existing = self.search(fields.Domain('source', '=', channel_code) & fields.Domain('event_id', '=', event['event_id']), limit=1)
        if existing:
            if existing.digest != digest:
                raise ValidationError(_('An event ID cannot be reused with different content.'))
            return {'received': True, 'id': existing.id}
        token = _INTERNAL.set(True)
        try:
            record = self.create({'branch_id': channel.branch_id.id, 'company_id': channel.company_id.id,
                'source': channel_code, 'event_id': event['event_id'], 'reference': event['reference'],
                'revision': event['revision'], 'payload': event, 'digest': digest})
            try:
                with self.env.cr.savepoint():
                    record._apply_event()
            except (UserError, ValidationError, KeyError, TypeError, ValueError):
                record.write({'state': 'review', 'last_error': _('The website event needs staff review. Its original payload has been retained.')})
        finally:
            _INTERNAL.reset(token)
        return {'received': True, 'id': record.id}

    def _apply_event(self):
        self.ensure_one()
        key = json.dumps([self.source, self.reference], separators=(',', ':'))
        request = self.env['ab_oms_request'].search(fields.Domain('source_reference', '=', key), limit=1)
        snapshot = self.payload['snapshot']
        if request and self.revision <= request.source_revision:
            self.write({'request_id': request.id, 'state': 'obsolete'})
            return
        customer = snapshot['customer']
        values = {'source_reference': key, 'source_revision': self.revision, 'source_snapshot': snapshot,
                  'branch_id': self.branch_id.id, 'company_id': self.company_id.id,
                  'customer_name': customer['name'], 'customer_phone': customer['phone'], 'customer_address': customer.get('address', ''),
                  'paid_amount': snapshot.get('paid_amount', 0), 'payment_references': snapshot.get('payments', []),
                  'cancellation_requested': snapshot.get('cancellation_requested', False)}
        currency = self.env['res.currency'].search(fields.Domain('name', '=', snapshot['currency']), limit=1)
        if not currency:
            raise ValidationError(_('The website currency is not configured.'))
        values['currency_id'] = currency.id
        if not request:
            request = self.env['ab_oms_request'].create(values)
            for line in snapshot['lines']:
                self.env['ab_oms_line'].create({'request_id': request.id, 'branch_id': self.branch_id.id,
                    'company_id': self.company_id.id, 'name': line['name'], 'quantity': line['quantity'],
                    'price_unit': line['price_unit'], 'source_product_reference': line['product'], 'source_unit_reference': line['unit']})
            self.write({'state': 'applied', 'request_id': request.id})
        else:
            request.lock_for_update()
            request._internal_write({k: values[k] for k in ('source_revision', 'source_snapshot', 'paid_amount', 'payment_references', 'cancellation_requested')})
            self.write({'state': 'review', 'request_id': request.id,
                        'last_error': _('A newer website snapshot requires staff comparison with the retained draft.')})

    def action_review(self):
        self._staff_action()
        self._authorize()
        self.lock_for_update()
        for event in self:
            if event.state != 'review' or not event.request_id or not event.review_note or not event.review_note.strip():
                raise UserError(_('Record the outcome of comparing the website snapshot with the draft.'))
            if event.request_id.attempt_ids or event.request_id.state != 'draft':
                raise UserError(_('Resolve the frozen branch submission before reviewing changed website requirements.'))
            self.env['ab_oms_note'].create({'request_id': event.request_id.id, 'body': event.review_note})
        return self._internal_write({'state': 'applied', 'last_error': False})

    def action_retry(self):
        self._authorize()
        token = _INTERNAL.set(True)
        try:
            for event in self:
                event.lock_for_update()
                if event.state not in ('received', 'review') or event.request_id:
                    raise UserError(_('Review the linked request before applying a newer snapshot.'))
                event._apply_event()
        finally:
            _INTERNAL.reset(token)
        return True


class Update(models.Model):
    _name = 'ab_oms_sync_update'
    _inherit = 'ab_crm_scoped'
    _description = 'OMS Website Update'
    _rec_name = 'reference'

    request_id = fields.Many2one('ab_oms_request', required=True, ondelete='restrict', check_company=True)
    reference = fields.Char(required=True, readonly=True)
    source = fields.Char(required=True, readonly=True)
    payload = fields.Json(required=True, readonly=True)
    state = fields.Selection([('review', 'Awaiting Review'), ('ready', 'Ready'), ('sent', 'Sent')], default='review', required=True, readonly=True)
    last_success = fields.Datetime(readonly=True)
    _payload_unique = models.Constraint('UNIQUE(request_id, reference)', 'This status update already exists.')

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            raise AccessError(_('Status updates are created from confirmed branch evidence.'))
        return super().create(values_list)

    def write(self, values):
        if not _INTERNAL.get():
            raise AccessError(_('Use the supported status review workflow.'))
        return super().write(values)

    def action_approve(self):
        self._staff_action()
        self._authorize()
        if any(r.state != 'review' for r in self):
            raise UserError(_('Only an unreviewed update can be approved.'))
        return self._internal_write({'state': 'ready'})

    @api.model
    def pending_updates(self):
        if not self.env.user.has_group('ab_oms_sync.group_sync'):
            raise AccessError(_('Only the synchronization service can receive website events.'))
        return [{'id': r.id, 'source': r.source, 'event': r.payload} for r in self.search(fields.Domain('state', '=', 'ready'), order='id', limit=100)]

    def acknowledge(self):
        if not self.env.user.has_group('ab_oms_sync.group_sync'):
            raise AccessError(_('Only the synchronization service can receive website events.'))
        self._authorize()
        if any(r.state not in ('ready', 'sent') for r in self):
            raise UserError(_('Only approved updates can be acknowledged.'))
        return self._internal_write({'state': 'sent', 'last_success': fields.Datetime.now()})


class Attempt(models.Model):
    _inherit = 'ab_oms_attempt'

    def _status_event(self):
        super()._status_event()
        self.ensure_one()
        if not self.request_id.source_reference:
            return
        source, reference = json.loads(self.request_id.source_reference)
        status = {'unknown': 'review', 'rejected': 'review', 'pending': 'accepted', 'saved': 'processed'}[self.state]
        key = '%s:%s:%s' % (self.token, self.revision, self.state)
        updates = self.env['ab_oms_sync_update']
        if updates.search_count(fields.Domain('request_id', '=', self.request_id.id) & fields.Domain('reference', '=', key)):
            return
        previous = updates.search(fields.Domain('request_id', '=', self.request_id.id), order='id desc', limit=1)
        revision = previous.payload['revision'] + 1 if previous else 1
        token = _INTERNAL.set(True)
        try:
            updates.create({'request_id': self.request_id.id, 'branch_id': self.branch_id.id, 'company_id': self.company_id.id,
                            'reference': key, 'source': source, 'payload': {'event_id': key, 'source': source,
                            'reference': reference, 'oms_reference': self.request_id.name, 'revision': revision,
                            'status': status, 'invoice_reference': self.invoice_reference}})
        finally:
            _INTERNAL.reset(token)


class Request(models.Model):
    _inherit = 'ab_oms_request'

    def _validate_ready(self):
        super()._validate_ready()
        if self.env['ab_oms_sync_event'].search_count(fields.Domain('request_id', '=', self.id) & fields.Domain('state', '=', 'review')):
            raise UserError(_('Review the latest website changes before submission.'))
