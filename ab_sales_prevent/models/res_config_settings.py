from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ab_sales_prevent_enabled = fields.Boolean(
        string="Prevent Sales Operations",
        help="Hide sales menus and block sales operations on this database.",
    )

    def get_values(self):
        result = super().get_values()
        result["ab_sales_prevent_enabled"] = self.env[
            "ab_sales_prevent.mixin"
        ]._sales_prevent_enabled()
        return result

    def set_values(self):
        previous = self.env["ab_sales_prevent.mixin"]._sales_prevent_enabled()
        result = super().set_values()
        enabled = bool(self.ab_sales_prevent_enabled)
        self.env["ir.config_parameter"].sudo().set_param(
            self.env["ab_sales_prevent.mixin"]._SALES_PREVENT_PARAM,
            "1" if enabled else "0",
        )
        if enabled != previous:
            self.env.registry.clear_cache()
        return result
