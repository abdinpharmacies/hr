from odoo import api, models


CONNECTION_KEYS = frozenset('ab_branch_sync.' + key for key in ('url', 'database', 'api_key'))


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def _branch_sync_connection_values(self):
        return tuple(self.sudo().get_param(key) for key in sorted(CONNECTION_KEYS))

    @api.model
    def _invalidate_branch_sync_connection(self):
        params = self.sudo()
        params.set_param('ab_branch_sync.authorized', False)
        params.set_param('ab_branch_sync.ready', False)
        params.set_param('ab_branch_sync.connection_status', 'attention')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if CONNECTION_KEYS.intersection(records.mapped('key')):
            self._invalidate_branch_sync_connection()
        return records

    def write(self, vals):
        connection_changed = bool(CONNECTION_KEYS.intersection(self.mapped('key') + [vals.get('key')]))
        previous = self._branch_sync_connection_values() if connection_changed else None
        result = super().write(vals)
        if connection_changed and previous != self._branch_sync_connection_values():
            self._invalidate_branch_sync_connection()
        return result

    def unlink(self):
        connection_changed = bool(CONNECTION_KEYS.intersection(self.mapped('key')))
        result = super().unlink()
        if connection_changed:
            self._invalidate_branch_sync_connection()
        return result
