<<<<<<< Updated upstream
from odoo import _, models
from odoo.tools import float_is_zero
=======
from odoo import models
from odoo.tools import float_round
>>>>>>> Stashed changes


class SaleOrder(models.Model):
    _inherit = "sale.order"

<<<<<<< Updated upstream
    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        new_qty, warning = super()._verify_updated_quantity(
            order_line, product_id, new_qty, uom_id, **kwargs
        )

        product = self.env["product.product"].browse(product_id)
        ab_product = product.ab_product_id
        if not ab_product:
            return new_qty, warning

        max_qty = float(ab_product.eplus_stock_total_qty or 0.0)
        if max_qty < 0:
            max_qty = 0.0

        other_lines_qty = sum(
            self.order_line.filtered(
                lambda line: line.id != order_line.id and line.product_id.id == product.id
            ).mapped("product_uom_qty")
        )
        allowed_qty = max(max_qty - other_lines_qty, 0.0)
        rounding = product.uom_id.rounding or 0.01

        if float_is_zero(allowed_qty - new_qty, precision_rounding=rounding) or new_qty <= allowed_qty:
            return new_qty, warning

        warning = _(
            "You cannot buy more than %(max_qty)s unit(s) of %(product)s. Current Eplus stock is %(available)s."
        ) % {
            "max_qty": max_qty,
            "product": product.display_name,
            "available": allowed_qty,
        }
        return allowed_qty, warning
=======
    def _get_free_qty(self, product):
        product.ensure_one()
        if product._ab_website_uses_eplus_stock():
            return product._get_ab_website_available_qty()
        return super()._get_free_qty(product)

    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        quantity, warning = super()._verify_updated_quantity(
            order_line,
            product_id,
            new_qty,
            uom_id,
            **kwargs,
        )
        product = self.env["product.product"].browse(product_id)
        if not product._ab_website_uses_eplus_stock():
            return quantity, warning

        uom = self.env["uom.uom"].browse(uom_id)
        product_uom = product.uom_id
        product_qty_in_cart = product_uom._compute_quantity(self._get_cart_qty(product.id), uom)
        available_qty = product_uom._compute_quantity(
            product._get_ab_website_available_qty(),
            uom,
            round=False,
        )
        available_qty = float_round(available_qty, precision_digits=0, rounding_method="DOWN")

        old_qty = order_line.product_uom_qty if order_line else 0.0
        added_qty = quantity - old_qty
        total_cart_qty = product_qty_in_cart + added_qty
        if available_qty >= total_cart_qty:
            return quantity, warning

        allowed_line_qty = max(available_qty - (product_qty_in_cart - old_qty), 0.0)

        def format_qty(qty):
            return int(qty) if float(qty).is_integer() else qty

        if allowed_line_qty > 0:
            warning = self.env._(
                "You ask for %(desired_qty)s products but only %(available_qty)s is available.",
                desired_qty=format_qty(total_cart_qty),
                available_qty=format_qty(available_qty),
            )
        elif order_line:
            warning = self.env._(
                "Some products became unavailable and your cart has been updated. We're sorry for the inconvenience."
            )
        else:
            warning = self.env._(
                "%(product_name)s has not been added to your cart since it is not available.",
                product_name=product.name,
            )
        return allowed_line_qty, warning
>>>>>>> Stashed changes
