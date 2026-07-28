from odoo import api, fields, models
from odoo.tools import ormcache


class AbOdooSyncConfig(models.Model):
    _name = "ab_odoo_sync_config"
    _description = "AB Odoo Sync Config"

    model_name = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True, index=True)

    _uniq_model_name = models.Constraint(
        "UNIQUE(model_name)",
        "Model name must be unique in sync config.",
    )

    @ormcache("dbname", "model_name")
    def _is_model_tracked_cached(self, dbname, model_name):
        if not model_name:
            return False
        self.env.cr.execute(
            """
            SELECT 1
            FROM ab_odoo_sync_config
            WHERE active = TRUE
              AND model_name = %s
            LIMIT 1
            """,
            (model_name,),
        )
        return bool(self.env.cr.fetchone())

    @api.model
    def is_model_tracked(self, model_name):
        if not model_name:
            return False
        try:
            return bool(self._is_model_tracked_cached(self.env.cr.dbname, model_name))
        except Exception:
            # During early init/upgrade the table may not be ready yet.
            return False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.clear_caches()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.clear_caches()
        return res

    def unlink(self):
        res = super().unlink()
        self.clear_caches()
        return res
