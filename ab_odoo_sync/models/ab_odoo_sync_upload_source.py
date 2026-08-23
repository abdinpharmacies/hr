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
    active = fields.Boolean(default=False, index=True)

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
        if self.env["ab_odoo_sync_rules"].sudo().is_upload_source_forbidden(model_name):
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
            if self.env["ab_odoo_sync_rules"].sudo().is_upload_source_forbidden(record.model_name):
                raise ValidationError(
                    _("Source model %(model)s is protected by sync-rules.md and cannot be a branch upload source.")
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

    @api.model
    def _is_loadable_model(self, model_name):
        if not model_name or model_name not in self.env:
            return False
        if model_name.startswith("ab_odoo_sync"):
            return False
        try:
            model = self.env[model_name]
        except KeyError:
            return False
        if getattr(model, "_abstract", False) or getattr(model, "_transient", False):
            return False
        return bool(getattr(model, "_auto", True))

    def action_load_installed_models(self):
        existing = set(
            self.with_context(active_test=False).sudo().search([]).mapped("model_name")
        )
        vals_list = []
        for model_record in self.env["ir.model"].sudo().search([], order="model"):
            model_name = model_record.model
            if model_name in existing or not self._is_loadable_model(model_name):
                continue
            vals_list.append(
                {
                    "model_name": model_name,
                    "active": False,
                }
            )
            existing.add(model_name)
        created = len(self.sudo().create(vals_list)) if vals_list else 0
        return self._notification(
            _("Branch Upload Sources"),
            _("Loaded %(count)s installed model(s) as inactive upload sources.") % {"count": created},
            "success" if created else "warning",
        )

    @api.model
    def ensure_upload_sources(self, source_specs):
        existing = {
            source.model_name: source
            for source in self.with_context(active_test=False).sudo().search([])
        }
        vals_list = []
        for spec in source_specs or []:
            model_name = (spec.get("model_name") or "").strip()
            if not model_name or model_name in existing:
                continue
            if self.env["ab_odoo_sync_rules"].sudo().is_upload_source_forbidden(model_name):
                raise ValueError(
                    _("Source model %(model)s is protected by sync-rules.md and cannot be a branch upload source.")
                    % {"model": model_name}
                )
            vals = {
                "model_name": model_name,
                "active": bool(spec.get("active", False)),
            }
            if spec.get("aggregate_parent_field"):
                vals["aggregate_parent_field"] = spec["aggregate_parent_field"]
            vals_list.append(vals)
        if vals_list:
            self.sudo().create(vals_list)
        return True

    @api.model
    def _notification(self, title, message, notification_type):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "reload",
                },
            },
        }

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
