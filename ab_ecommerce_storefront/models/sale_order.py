from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _cart_add(self, product_id, quantity=1.0, *, uom_id=None, **kwargs):
        result = super()._cart_add(product_id, quantity=quantity, uom_id=uom_id, **kwargs)
        if quantity > 0 and self.partner_id and not self.env.user._is_public():
            self.partner_id.sudo().write({"ab_storefront_has_cart_history": True})
        return result
