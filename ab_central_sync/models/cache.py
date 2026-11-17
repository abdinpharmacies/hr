"""Central balance snapshots and conservative branch reservations; no local ledger."""
import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Backend(models.Model):
    _inherit = 'ab_sales_backend'

    @api.model
    def _is_native(self, store_id):
        store = self.env['ab_store'].sudo().browse(int(store_id or 0))
        if self.env['ab_central_sync_operation']._uses_central(store):
            return True
        return super()._is_native(store_id)

    @api.model
    def _check_store(self, store_id, cashier=False):
        store = self.env.user._central_replay_store()
        if store and store.id != int(store_id or 0):
            raise AccessError(_('The API user has no inventory access to this branch.'))
        return super()._check_store(store_id, cashier=cashier)

    @api.model
    def _check_employee_session(self, store, permission, token=False):
        replay_store = self.env.user._central_replay_store()
        if replay_store:
            if store != replay_store:
                raise AccessError(_('The API user has no inventory access to this branch.'))
            return False
        return super()._check_employee_session(store, permission, token=token)


class InventoryProcess(models.AbstractModel):
    _inherit = 'ab_inventory_process'

    @api.model
    def _check_store(self, store_id):
        store = self.env.user._central_replay_store()
        if store:
            if store.id != int(store_id or 0):
                raise AccessError(_('The API user has no inventory access to this branch.'))
            return store
        return super()._check_store(store_id)
