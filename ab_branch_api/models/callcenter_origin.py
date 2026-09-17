"""Immutable origin set only by private server-side creation paths."""
from contextvars import ContextVar

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

_origin_creation = ContextVar('callcenter_origin_creation', default=None)


class CallcenterSaleOrigin(models.Model):
    _inherit = 'ab_sales_header'

    is_callcenter_order = fields.Boolean(
        string='Created by Call Center', default=False, copy=False, index=True, readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('is_callcenter_order') for vals in vals_list):
            raise AccessError(_('The call-center origin cannot be changed.'))
        # Explicit False also defeats default_is_callcenter_order in RPC context.
        scope = _origin_creation.get()
        trusted = scope and scope[:3] == (self.env.cr, self.env.uid, self._name)
        return super().create([
            dict(vals, is_callcenter_order=bool(trusted and vals is scope[3]))
            for vals in vals_list
        ])

    @api.model
    def _create_callcenter_order(self, vals):
        # Bind approval to this exact values object and environment, outside RPC context.
        # Use the full create chain so other addons keep their business validations.
        values = dict(vals)
        token = _origin_creation.set((self.env.cr, self.env.uid, self._name, values))
        try:
            return self.create(values)
        finally:
            _origin_creation.reset(token)

    def write(self, vals):
        if 'is_callcenter_order' in vals:
            raise AccessError(_('The call-center origin cannot be changed.'))
        return super().write(vals)


class CallcenterReturnOrigin(models.Model):
    _inherit = 'ab_sales_return_header'

    is_callcenter_order = fields.Boolean(
        string='Created by Call Center', default=False, copy=False, index=True, readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('is_callcenter_order') for vals in vals_list):
            raise AccessError(_('The call-center origin cannot be changed.'))
        # Explicit False also defeats default_is_callcenter_order in RPC context.
        scope = _origin_creation.get()
        trusted = scope and scope[:3] == (self.env.cr, self.env.uid, self._name)
        return super().create([
            dict(vals, is_callcenter_order=bool(trusted and vals is scope[3]))
            for vals in vals_list
        ])

    @api.model
    def _create_callcenter_order(self, vals):
        # Bind approval to this exact values object and environment, outside RPC context.
        # Use the full create chain so other addons keep their business validations.
        values = dict(vals)
        token = _origin_creation.set((self.env.cr, self.env.uid, self._name, values))
        try:
            return self.create(values)
        finally:
            _origin_creation.reset(token)

    def write(self, vals):
        if 'is_callcenter_order' in vals:
            raise AccessError(_('The call-center origin cannot be changed.'))
        return super().write(vals)
