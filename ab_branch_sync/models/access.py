"""Use the installation's branch scope without assigning inventory roles to tills."""
import json

from odoo import api, models


class Users(models.Model):
    _inherit = 'res.users'

    def _branch_sync_inventory_store_ids(self):
        self.ensure_one()
        stores = self.inventory_store_ids
        journal = self.env['ab_branch_sync_operation']
        if (self.has_group('base.group_user')
                and self.env['ab_sales_header'].with_user(self).has_access('read')
                and all(journal._param(key) for key in ('url', 'database', 'api_key'))
                and journal._param('authorized')
                and journal._param('origin') == self.env['ir.config_parameter'].sudo().get_param('database.uuid')):
            replica = self.env['ab_replica_db'].get_current_from_config()
            codes = json.loads(journal._param('stores', '[]'))
            stores |= replica.allowed_sales_store_ids.filtered(lambda store: store.code in codes)
        return stores.ids


class Replica(models.Model):
    _inherit = 'ab_replica_db'

    @api.model_create_multi
    def create(self, vals_list):
        replicas = super().create(vals_list)
        self.env.registry.clear_cache()
        return replicas

    def write(self, vals):
        result = super().write(vals)
        if {'active', 'db_serial', 'allowed_sales_store_ids'} & vals.keys():
            # ir.rule caches evaluated store IDs. Reassignment must revoke the
            # previous branch scope immediately, including in other workers.
            self.env.registry.clear_cache()
        return result
