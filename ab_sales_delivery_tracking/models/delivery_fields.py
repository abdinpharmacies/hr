from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DeliveryFields(models.Model):
    _inherit = 'ab_sales_header'

    delivery_notify = fields.Boolean(string='Notify Delivery Bot', default=False, copy=False)
    delivery_instructions = fields.Text(string='Delivery Instructions', copy=False)


class DeliveryClient(models.AbstractModel):
    _inherit = 'ab_sales_branch_client'

    def _sale_payload(self, payload):
        result = super()._sale_payload(payload)
        header = result.get('header', {})
        if header.get('delivery_notify'):
            store = self.env['ab_store'].browse(int(payload['header'].get('store_id') or 0))
            capability = self._call(store, 'get_capabilities')
            if capability.get('delivery_notifications') != 1:
                raise UserError(_('This branch does not support delivery notifications.'))
        else:
            # Ordinary sales remain compatible with providers without this extension.
            header.pop('delivery_notify', None)
            header.pop('delivery_instructions', None)
        return self._remove_omitted_delivery_descriptors(result)

    def _remove_omitted_delivery_descriptors(self, wire):
        header = wire.get('header', {})
        descriptors = (wire.get('metadata_context') or {}).get('header', {})
        for name in ('delivery_notify', 'delivery_instructions'):
            if name not in header:
                descriptors.pop(name, None)
        return wire

    def _sale_correction_payload(self, wire):
        # Only the new, authorized revision is repaired; frozen retries stay intact.
        return self._remove_omitted_delivery_descriptors(super()._sale_correction_payload(wire))


class DeliveryCapabilities(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @api.model
    def pos_delivery_capability(self, store_id):
        store = self.env['ab_store'].browse(int(store_id)).exists()
        result = self.env['ab_sales_branch_client']._call(store, 'get_capabilities')
        return result.get('delivery_notifications') == 1
