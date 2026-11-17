"""Attribute synchronized stock to its authenticated originating replica."""
from odoo import api, models, _
from odoo.exceptions import AccessError

from .sales import REPLAY_ORIGIN


class Inventory(models.Model):
    _inherit = 'ab_inventory'

    @api.model
    def _movement_db_serial(self, values):
        origin = REPLAY_ORIGIN.get()
        if origin:
            store = self.env.user._central_replay_store()
            if not store or values.get('store_id') != store.id:
                raise AccessError(_('The API user has no inventory access to this branch.'))
            return origin['replica_serial']
        return super()._movement_db_serial(values)
