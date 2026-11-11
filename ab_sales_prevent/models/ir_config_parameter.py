from odoo import api, models


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    @api.model
    def _sales_prevent_parameter_keys(self):
        return {self.env["ab_sales_prevent.mixin"]._SALES_PREVENT_PARAM}

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self._sales_prevent_parameter_keys() & {vals.get("key") for vals in vals_list}:
            self.env.registry.clear_cache()
        return records

    def write(self, vals):
        old_keys = set(self.mapped("key"))
        result = super().write(vals)
        new_keys = set(self.mapped("key"))
        if self._sales_prevent_parameter_keys() & (old_keys | new_keys | {vals.get("key")}):
            self.env.registry.clear_cache()
        return result

    def unlink(self):
        keys = set(self.mapped("key"))
        result = super().unlink()
        if self._sales_prevent_parameter_keys() & keys:
            self.env.registry.clear_cache()
        return result
