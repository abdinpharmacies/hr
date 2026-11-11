"""Central balance snapshots and conservative branch reservations; no local ledger."""
import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from .sales import REPLAY_ORIGIN


class Backend(models.Model):
    _inherit = 'ab_sales_backend'

    @api.model
    def _is_native(self, store_id):
        store = self.env['ab_store'].sudo().browse(int(store_id or 0))
        if self.env['ab_central_sync_operation']._uses_central(store):
            return True
        return super()._is_native(store_id)

    @api.model
    def _check_employee_session(self, store, permission, token=False):
        origin = REPLAY_ORIGIN.get()
        if (origin and origin.get('inventory_writer_id') == self.env.uid
                and origin.get('inventory_store_id') == store.id):
            if store not in self.env.user._central_inventory_stores():
                raise AccessError(_('The API user has no inventory access to this branch.'))
            return False
        return super()._check_employee_session(store, permission, token=token)
