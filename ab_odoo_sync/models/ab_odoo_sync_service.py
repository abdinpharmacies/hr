from odoo import api, models
from odoo.tools.translate import _


class AbOdooSyncService(models.AbstractModel):
    _name = "ab_odoo_sync_service"
    _description = "AB Odoo Sync Service"

    @api.model
    def _icp(self):
        return self.env["ir.config_parameter"].sudo()

    @api.model
    def is_placeholder_config(self, value):
        return (value or "").strip().startswith("---")

    @api.model
    def is_configured(self, value):
        return bool((value or "").strip()) and not self.is_placeholder_config(value)

    @api.model
    def _ensure_config_parameter_defaults(self, defaults):
        if not isinstance(defaults, dict):
            raise ValueError(_("Configuration defaults must be a dictionary."))
        Parameters = self._icp().with_context(active_test=False)
        existing_keys = set(
            Parameters.search([("key", "in", list(defaults))]).mapped("key")
        )
        missing_values = [
            {"key": key, "value": value}
            for key, value in defaults.items()
            if key not in existing_keys
        ]
        if missing_values:
            Parameters.create(missing_values)
        return True

    @api.model
    def get_batch_size(self):
        raw = self._icp().get_param("ab_odoo_sync.batch_size") or "1000"
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = 1000
        return max(1, min(value, 10000))

    @api.model
    def parse_positive_int(self, value, field_name):
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError) as ex:
            raise ValueError(_("%s must be a positive integer.") % field_name) from ex
        if parsed <= 0:
            raise ValueError(_("%s must be a positive integer.") % field_name)
        return parsed
