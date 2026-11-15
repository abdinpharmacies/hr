import hashlib
import json
from contextvars import ContextVar
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_INTERNAL = ContextVar('ab_oms_website_internal', default=False)


class Website(models.Model):
    _inherit = 'website'

    oms_enabled = fields.Boolean(string='Send New Requests to OMS', groups='base.group_system')
    oms_cutoff = fields.Datetime(string='OMS Activation Cutoff', groups='base.group_system')
    oms_source = fields.Char(string='OMS Source Identity', groups='base.group_system')

    @api.constrains('oms_enabled', 'oms_cutoff', 'oms_source')
    def _check_oms_settings(self):
        for website in self:
            if website.oms_enabled and (not website.oms_cutoff or not website.oms_source):
                raise ValidationError(_('Set an activation cutoff and source identity before enabling OMS.'))


class Event(models.Model):
    _name = 'ab_oms_website_event'
    _description = 'Website OMS Event'
    _rec_name = 'event_id'
    _order = 'id'

    order_id = fields.Many2one('sale.order', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    event_id = fields.Char(required=True, readonly=True)
    payload = fields.Json(required=True, readonly=True)
    direction = fields.Selection([('out', 'To OMS'), ('in', 'From OMS')], required=True, readonly=True)
    digest = fields.Char(readonly=True)
    delivered = fields.Boolean(readonly=True)
    last_success = fields.Datetime(readonly=True)
    _event_unique = models.Constraint('UNIQUE(event_id, direction)', 'This integration event already exists.')

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            raise AccessError(_('Integration events are recorded automatically.'))
        return super().create(values_list)

    def write(self, values):
        if not _INTERNAL.get():
            raise AccessError(_('Integration events are immutable.'))
        return super().write(values)

    def unlink(self):
        raise AccessError(_('Integration events are immutable.'))

    def _service(self):
        if not self.env.user.has_group('ab_oms_website_adapter.group_sync'):
            raise AccessError(_('Only the website synchronization service can exchange events.'))

    @api.model
    def pending_events(self):
        self._service()
        return [{'id': r.id, 'event': r.payload} for r in self.search(fields.Domain('direction', '=', 'out') & fields.Domain('delivered', '=', False), limit=100)]

    def acknowledge(self):
        self._service()
        self.check_access('write')
        if any(r.direction != 'out' for r in self):
            raise AccessError(_('Only outgoing events can be acknowledged.'))
        token = _INTERNAL.set(True)
        try:
            return self.write({'delivered': True, 'last_success': fields.Datetime.now()})
        finally:
            _INTERNAL.reset(token)

    @api.model
    def receive_update(self, event):
        self._service()
        if (not isinstance(event, dict) or type(event.get('revision')) is not int or event['revision'] < 1
                or event.get('status') not in ('review', 'accepted', 'processed')
                or not all(isinstance(event.get(k), str) and event[k] for k in ('event_id', 'reference', 'source', 'oms_reference'))):
            raise ValidationError(_('Invalid OMS status update.'))
        order = self.env['sale.order'].search(fields.Domain('oms_request_reference', '=', event['reference']), limit=1)
        order.ensure_one()
        order.check_access('write')
        order.lock_for_update()
        if order.oms_source_identity != event['source']:
            raise AccessError(_('The OMS update belongs to another website.'))
        digest = hashlib.sha256(json.dumps(event, sort_keys=True, allow_nan=False).encode()).hexdigest()
        existing = self.search(fields.Domain('event_id', '=', event['event_id']) & fields.Domain('direction', '=', 'in'), limit=1)
        if existing:
            if existing.digest != digest:
                raise ValidationError(_('An event ID cannot be reused with different content.'))
            return {'received': True}
        token = _INTERNAL.set(True)
        try:
            self.create({'order_id': order.id, 'event_id': event['event_id'], 'direction': 'in', 'payload': event, 'digest': digest, 'delivered': True, 'last_success': fields.Datetime.now()})
            if event['revision'] > order.oms_status_revision:
                order.write({'oms_status_revision': event['revision'], 'oms_status': event['status'], 'oms_reference': event['oms_reference']})
        finally:
            _INTERNAL.reset(token)
        return {'received': True}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    oms_request_reference = fields.Char(readonly=True, copy=False, index=True)
    oms_source_identity = fields.Char(readonly=True, copy=False)
    oms_revision = fields.Integer(readonly=True, copy=False)
    oms_status_revision = fields.Integer(readonly=True, copy=False)
    oms_reference = fields.Char(readonly=True, copy=False)
    oms_status = fields.Selection([('review', 'Under Review'), ('accepted', 'Accepted by Branch'), ('processed', 'Processed by Branch')], readonly=True, copy=False)
    oms_cancellation_requested = fields.Boolean(readonly=True, copy=False)
    _oms_reference_unique = models.Constraint('UNIQUE(oms_request_reference)', 'OMS request reference must be unique.')

    def _oms_managed(self):
        return self.filtered(lambda r: r.oms_request_reference or (r.website_id.sudo().oms_enabled and r.website_id.sudo().oms_cutoff and r.create_date >= r.website_id.sudo().oms_cutoff))

    def action_confirm(self):
        managed = self._oms_managed()
        result = super(SaleOrder, self - managed).action_confirm() if self - managed else True
        managed.check_access('write')
        token = _INTERNAL.set(True)
        try:
            for order in managed:
                order.lock_for_update()
                if not order.oms_request_reference:
                    if order.state not in ('draft', 'sent'):
                        raise UserError(_('Only new unconfirmed website requests can enter OMS.'))
                    order.write({'oms_request_reference': str(uuid4()), 'oms_source_identity': order.website_id.sudo().oms_source, 'state': 'sent', 'oms_status': 'review'})
                    order._oms_event()
        finally:
            _INTERNAL.reset(token)
        return result

    def action_cancel(self):
        managed = self.filtered('oms_request_reference')
        result = super(SaleOrder, self - managed).action_cancel() if self - managed else True
        managed.check_access('write')
        token = _INTERNAL.set(True)
        try:
            for order in managed:
                order.write({'oms_cancellation_requested': True})
                order._oms_event()
        finally:
            _INTERNAL.reset(token)
        return result

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            if any(any(k.startswith('oms_') for k in v) for v in values_list):
                raise AccessError(_('OMS coordination fields are managed by the integration.'))
            values_list = [dict(v, oms_request_reference=False, oms_source_identity=False, oms_revision=0,
                                oms_status_revision=0, oms_reference=False, oms_status=False, oms_cancellation_requested=False) for v in values_list]
        return super().create(values_list)

    def write(self, values):
        if not _INTERNAL.get():
            if self.env.user.has_group('ab_oms_website_adapter.group_sync'):
                raise AccessError(_('The synchronization account cannot edit business orders directly.'))
            if any(k.startswith('oms_') for k in values):
                raise AccessError(_('OMS coordination fields are managed by the integration.'))
            if self.filtered('oms_request_reference') and values.get('state') in ('sale', 'cancel'):
                raise UserError(_('The branch owns execution. Use the OMS cancellation request workflow.'))
        result = super().write(values)
        if not _INTERNAL.get() and {'order_line', 'partner_id', 'partner_shipping_id'} & values.keys():
            self.filtered('oms_request_reference')._oms_event()
        return result

    def _oms_event(self):
        token = _INTERNAL.set(True)
        try:
            for order in self:
                order.check_access('read')
                order.lock_for_update()
                if not order.oms_request_reference:
                    continue
                order.write({'oms_revision': order.oms_revision + 1})
                transactions = order.transaction_ids.filtered(lambda t: t.state in ('authorized', 'done') and t.operation != 'refund')
                payments = [{'reference': t.reference, 'provider_reference': t.provider_reference, 'amount': t.amount,
                             'currency': t.currency_id.name, 'state': t.state} for t in transactions]
                snapshot = {'customer': {'name': order.partner_id.name, 'phone': order.partner_id.phone or '',
                            'address': order.partner_shipping_id.contact_address or ''},
                            'amount_total': order.amount_total, 'amount_tax': order.amount_tax, 'currency': order.currency_id.name, 'paid_amount': sum(t.amount for t in transactions if t.state == 'done'),
                            'payments': payments, 'cancellation_requested': order.oms_cancellation_requested,
                            'lines': [{'name': l.name, 'product': str(l.product_id.id), 'unit': str(l.product_uom_id.id),
                                       'quantity': l.product_uom_qty, 'price_unit': l.price_unit, 'discount': l.discount, 'subtotal': l.price_subtotal, 'total': l.price_total} for l in order.order_line if not l.display_type]}
                event_id = str(uuid4())
                self.env['ab_oms_website_event'].sudo().create({'order_id': order.id, 'event_id': event_id, 'direction': 'out',
                    'payload': {'event_id': event_id, 'source': order.oms_source_identity, 'reference': order.oms_request_reference,
                                'revision': order.oms_revision, 'snapshot': snapshot}})
        finally:
            _INTERNAL.reset(token)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model_create_multi
    def create(self, values_list):
        records = super().create(values_list)
        records.order_id.filtered('oms_request_reference')._oms_event()
        return records

    def unlink(self):
        orders = self.order_id.filtered('oms_request_reference')
        result = super().unlink()
        orders._oms_event()
        return result

    def write(self, values):
        result = super().write(values)
        if {'product_id', 'product_uom_id', 'product_uom_qty', 'price_unit', 'discount'} & values.keys():
            self.order_id.filtered('oms_request_reference')._oms_event()
        return result


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def write(self, values):
        result = super().write(values)
        if {'state', 'provider_reference'} & values.keys():
            self.sale_order_ids.filtered('oms_request_reference')._oms_event()
        return result
