from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import ormcache
from odoo.tools.translate import _


class AbOdooSyncUploadSource(models.Model):
    _name = "ab_odoo_sync_upload_source"
    _description = "AB Odoo Sync Upload Source"
    _order = "model_name"

    model_name = fields.Char(string="Source Model", required=True, index=True)
    aggregate_parent_field = fields.Char(
        string="Aggregate Parent Field",
        help="Optional Many2one field whose parent must be re-snapshotted after this model changes.",
    )
    active = fields.Boolean(default=True, index=True)

    _uniq_model_name = models.Constraint(
        "UNIQUE(model_name)",
        "Source model must be unique in upload sources.",
    )

    @ormcache("dbname", "model_name", cache="stable")
    def _is_upload_source_cached(self, dbname, model_name):
        if not model_name:
            return False
        self.flush_model(["model_name", "active"])
        self.env.cr.execute(
            """
            SELECT 1
              FROM ab_odoo_sync_upload_source
             WHERE active = TRUE
               AND model_name = %s
             LIMIT 1
            """,
            (model_name,),
        )
        return bool(self.env.cr.fetchone())

    @api.model
    def is_upload_source(self, model_name):
        if not model_name:
            return False
        try:
            return bool(self._is_upload_source_cached(self.env.cr.dbname, model_name))
        except Exception:
            # The table may not be available during early registry setup.
            return False

    @api.constrains("model_name", "aggregate_parent_field")
    def _check_model_name(self):
        for record in self:
            if record.model_name not in self.env:
                raise ValidationError(
                    _("Source model %(model)s is not installed in this database.")
                    % {"model": record.model_name}
                )
            if record.aggregate_parent_field:
                field = self.env[record.model_name]._fields.get(record.aggregate_parent_field)
                if not field or field.type != "many2one":
                    raise ValidationError(
                        _("Aggregate parent field %(field)s must be a Many2one on %(model)s.")
                        % {
                            "field": record.aggregate_parent_field,
                            "model": record.model_name,
                        }
                    )

    @api.model
    def get_aggregate_parents(self, records):
        if not records:
            return False
        source = self.sudo().search(
            [
                ("model_name", "=", records._name),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not source or not source.aggregate_parent_field:
            return False
        return records.mapped(source.aggregate_parent_field).exists()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache("stable")
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env.registry.clear_cache("stable")
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache("stable")
        return result
