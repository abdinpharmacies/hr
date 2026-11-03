"""Keep machine-local enrollment secrets and stock caches out of replication."""
from odoo import models


class Replication(models.AbstractModel):
    _inherit = 'ab_odoo_replication'

    def _get_repldb_flds__name_type_rel(self):
        rows = super()._get_repldb_flds__name_type_rel()
        if self.ReplShare.model_name == 'ab_replica_db':
            rows = [row for row in rows if not row[0].startswith('central_')]
        return rows

    def _replicate_model(self, model_name, limit, commit, extra_fields,
                         replicate_all, extra_domain, *args, **kwargs):
        if model_name == 'ab_central_sync_operation':
            return
        if model_name == 'ab_replica_db':
            extra_fields = {key: value for key, value in (extra_fields or {}).items() if not key.startswith('central_')}
        if model_name == 'ab_sales_inventory' and self.env['ab_central_sync_operation']._param('role') == 'branch':
            return
        return super()._replicate_model(model_name, limit, commit, extra_fields,
                                       replicate_all, extra_domain, *args, **kwargs)
