"""Temporary store access for authenticated transport, never client RPC context."""
from odoo import models, _
from odoo.exceptions import AccessError

from .sales import REPLAY_ORIGIN


class Users(models.Model):
    _inherit = 'res.users'

    def _central_replay_store(self):
        self.ensure_one()
        origin = REPLAY_ORIGIN.get()
        stores = self.env['ab_store'].sudo()
        if not origin or origin.get('inventory_writer_id') != self.id:
            return stores.browse()
        # Read authorization with sudo to avoid recursive record-rule evaluation.
        # This grants no ORM superuser access to the actor executing the sale.
        replica = self.env['ab_replica_db'].sudo().browse(origin['inventory_replica_id']).exists()
        store = stores.browse(origin['inventory_store_id']).exists()
        if (not replica or replica.db_serial != origin['replica_serial']
                or not store or store not in self.sudo()._central_inventory_stores(replica)):
            raise AccessError(_('The API user has no inventory access to this branch.'))
        return store

    def _central_sync_inventory_store_ids(self):
        store = self._central_replay_store()
        return store.ids if store else self.inventory_store_ids.ids


class Rule(models.Model):
    _inherit = 'ir.rule'

    def _compute_domain_context_values(self):
        yield from super()._compute_domain_context_values()
        # Cache isolation is derived from a server-only ContextVar. An RPC caller
        # cannot reuse a replay domain by supplying matching context keys.
        yield self.env.user._central_replay_store().id or False
