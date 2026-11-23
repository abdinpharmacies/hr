from uuid import UUID, uuid5

from odoo import fields, models, _
from odoo.exceptions import AccessError

from .adapter import _CAPTURE
from .chat import SessionEnded, opaque
from ..protocol import fingerprint


class OrderLifecycle(models.Model):
    _inherit = 'sale.order'

    ab_callcenter_chat_closed = fields.Boolean(string='Order chat ended', readonly=True, copy=False)

    def _ab_callcenter_require_open(self):
        self.ensure_one()
        self.lock_for_update()
        self.invalidate_recordset(['ab_callcenter_chat_closed'])
        if self.ab_callcenter_chat_closed:
            raise SessionEnded(_('This chat has ended. Your order has been sent for delivery.'))

    def _ab_callcenter_close_dispatched(self):
        for order in self.filtered('ab_callcenter_uuid'):
            endpoint = order.ab_callcenter_endpoint_id.sudo()
            if (order.company_id not in self.env.companies or endpoint.company_id != order.company_id
                    or endpoint.website_id != order.website_id):
                raise AccessError(_('Invalid website order.'))
            order.lock_for_update()
            order.invalidate_recordset(['ab_callcenter_chat_closed'])
            if order.ab_callcenter_chat_closed:
                continue
            guard = _CAPTURE.set(True)
            try:
                order.sudo().write({'ab_callcenter_chat_closed': True})
                if endpoint.lifecycle_enabled and endpoint.dispatch_lifecycle_enabled:
                    identity = order.sudo().ab_callcenter_account_uuid
                    event = {'version': 3, 'source': endpoint.source,
                        'event_uuid': str(uuid5(UUID(order.ab_callcenter_uuid), 'order_dispatched')),
                        'kind': 'order_dispatched',
                        'destination': {'kind': 'order', 'uuid': order.ab_callcenter_uuid},
                        'identity': {'kind': 'customer' if identity else 'visitor',
                                     'uuid': identity or opaque(endpoint.source, 'order:' + order.ab_callcenter_uuid)}}
                    event['fingerprint'] = fingerprint(event)
                    self.env['ab_storefront_callcenter_lifecycle'].sudo().create({
                        'endpoint_id': endpoint.id, 'event_uuid': event['event_uuid'], 'envelope': event})
            finally:
                _CAPTURE.reset(guard)

    def write(self, values):
        result = super().write(values)
        if values.get('ab_last_mile_status') in ('out_for_delivery', 'delivered'):
            self._ab_callcenter_close_dispatched()
        return result


class PickingLifecycle(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        result = super()._action_done()
        for order in self.filtered(lambda picking: picking.state == 'done' and picking.picking_type_id.code == 'outgoing').sale_id.filtered('ab_callcenter_uuid'):
            outgoing = order._ab_call_center_outgoing_pickings()
            if outgoing and all(picking.state == 'done' for picking in outgoing):
                order._ab_callcenter_close_dispatched()
        return result


class PrescriptionLifecycle(models.Model):
    _inherit = 'ab.prescription.order'

    def write(self, values):
        result = super().write(values)
        if values.get('state') in ('out_for_delivery', 'delivered'):
            self.sale_order_id._ab_callcenter_close_dispatched()
        return result


class EndpointLifecycle(models.Model):
    _inherit = 'ab_storefront_callcenter_endpoint'

    dispatch_lifecycle_enabled = fields.Boolean(string='Enable dispatch lifecycle after receiver upgrade', default=False)
