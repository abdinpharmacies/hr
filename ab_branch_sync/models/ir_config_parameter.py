from odoo import api, models


CONNECTION_KEYS = frozenset('ab_central_branch_connection.' + key for key in ('url', 'database', 'api_key'))
ACCESS_KEYS = CONNECTION_KEYS | frozenset(
    'ab_central_branch_connection.' + key for key in ('authorized', 'origin', 'stores')
) | {'database.uuid'}


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def _branch_sync_connection_values(self):
        return tuple(self.sudo().get_param(key) for key in sorted(CONNECTION_KEYS))

    @api.model
    def _invalidate_branch_sync_connection(self):
        params = self.sudo()
        params.set_param('ab_central_branch_connection.authorized', False)
        params.set_param('ab_central_branch_connection.ready', False)
        params.set_param('ab_central_branch_connection.connection_status', 'attention')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if CONNECTION_KEYS.intersection(records.mapped('key')):
            self._invalidate_branch_sync_connection()
        if ACCESS_KEYS.intersection(records.mapped('key')):
            self.env.registry.clear_cache()
        return records

    def write(self, vals):
        affected_keys = self.mapped('key') + [vals.get('key')]
        connection_changed = bool(CONNECTION_KEYS.intersection(affected_keys))
        previous = self._branch_sync_connection_values() if connection_changed else None
        result = super().write(vals)
        if connection_changed and previous != self._branch_sync_connection_values():
            self._invalidate_branch_sync_connection()
        if ACCESS_KEYS.intersection(affected_keys):
            self.env.registry.clear_cache()
        return result

    def unlink(self):
        affected_keys = self.mapped('key')
        connection_changed = bool(CONNECTION_KEYS.intersection(affected_keys))
        result = super().unlink()
        if connection_changed:
            self._invalidate_branch_sync_connection()
        if ACCESS_KEYS.intersection(affected_keys):
            self.env.registry.clear_cache()
        return result
