from odoo import models
from odoo.tools import float_round


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_free_qty(self, product):
        product.ensure_one()
        if product._ab_website_uses_eplus_stock():
            return product._get_ab_website_available_qty()
        return super()._get_free_qty(product)

    def _verify_updated_quantity(self, order_line, product_id, new_qty, uom_id, **kwargs):
        self.ensure_one()
        product = self.env["product.product"].browse(product_id)
        if product._ab_website_uses_eplus_stock():
            uom = self.env["uom.uom"].browse(uom_id)
            product_uom = product.uom_id
            product_qty_in_cart, available_qty = self._get_cart_and_free_qty(product)
            product_qty_in_cart = product_uom._compute_quantity(product_qty_in_cart, uom)
            available_qty = product_uom._compute_quantity(available_qty, uom, round=False)
            available_qty = float_round(available_qty, precision_digits=0, rounding_method="DOWN")

            old_qty = order_line.product_uom_qty if order_line else 0.0
            added_qty = new_qty - old_qty
            total_cart_qty = product_qty_in_cart + added_qty
            if available_qty >= total_cart_qty:
                return new_qty, ""

            allowed_line_qty = max(available_qty - (product_qty_in_cart - old_qty), 0.0)

            def format_qty(qty):
                return int(qty) if float(qty).is_integer() else qty

            if allowed_line_qty > 0:
                if order_line:
                    warning = order_line._set_shop_warning_stock(
                        format_qty(total_cart_qty),
                        format_qty(available_qty),
                        save=False,
                    )
                else:
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

        quantity, warning = super()._verify_updated_quantity(
            order_line,
            product_id,
            new_qty,
            uom_id,
            **kwargs,
        )
        return quantity, warning

    def _verify_cart_after_update(self):
        result = super()._verify_cart_after_update()
        for product in self.order_line.product_id.filtered(lambda product: product._ab_website_uses_eplus_stock()):
            cart_qty, available_qty = self._get_cart_and_free_qty(product)
            available_qty = max(available_qty or 0.0, 0.0)
            if cart_qty <= available_qty:
                continue
            warning = False
            remaining_qty = available_qty
            product_lines = self._get_common_product_lines(product.id).sorted("id")
            for line in product_lines:
                line_qty = line.product_uom_id._compute_quantity(
                    line.product_uom_qty,
                    product.uom_id,
                )
                allowed_product_qty = min(line_qty, remaining_qty)
                remaining_qty -= allowed_product_qty
                if allowed_product_qty <= 0:
                    warning = warning or line._set_shop_warning_stock(cart_qty, available_qty, save=False)
                    line.unlink()
                    continue
                allowed_line_qty = product.uom_id._compute_quantity(
                    allowed_product_qty,
                    line.product_uom_id,
                    round=False,
                )
                if allowed_line_qty < line.product_uom_qty:
                    warning = warning or line._set_shop_warning_stock(cart_qty, available_qty, save=False)
                    line.product_uom_qty = allowed_line_qty
            if warning:
                self.shop_warning = warning
        return result
