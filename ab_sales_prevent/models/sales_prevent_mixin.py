from odoo import _, api, models
from odoo.exceptions import AccessError


class AbSalesPreventMixin(models.AbstractModel):
    _name = "ab_sales_prevent.mixin"
    _description = "Sales Prevention Helper"

    _SALES_PREVENT_PARAM = "ab_sales_prevent.enabled"
    _SALES_PREVENT_TRUTHY = {"1", "true", "yes", "on"}
    _SALES_PREVENT_MESSAGE = "Sales operations are disabled on this database."

    @api.model
    def _sales_prevent_enabled(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            self._SALES_PREVENT_PARAM,
            "0",
        )
        return str(value or "").strip().lower() in self._SALES_PREVENT_TRUTHY

    @api.model
    def _sales_prevent_access_error(self):
        return AccessError(_(self._SALES_PREVENT_MESSAGE))

    @api.model
    def _raise_sales_prevented(self):
        if self._sales_prevent_enabled():
            raise self._sales_prevent_access_error()


class AbSalesPreventAccessMixin(models.AbstractModel):
    _name = "ab_sales_prevent.access.mixin"
    _description = "Sales Prevention Access Guard"
    _inherit = "ab_sales_prevent.mixin"

    @api.model_create_multi
    def create(self, vals_list):
        self._raise_sales_prevented()
        return super().create(vals_list)

    def write(self, vals):
        self._raise_sales_prevented()
        return super().write(vals)

    def unlink(self):
        self._raise_sales_prevented()
        return super().unlink()

    def _check_access(self, operation):
        result = super()._check_access(operation)
        if result:
            return result
        if operation != "read" and self._sales_prevent_enabled():
            return self, self._sales_prevent_access_error
        return None
