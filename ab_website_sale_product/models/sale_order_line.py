from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    ab_product_id = fields.Many2one(
        "ab_product",
        string="Abdin Product",
        related="product_id.ab_product_id",
        store=True,
        readonly=True,
        groups="base.group_user",
    )

    def _ab_website_must_check_stock(self):
        self.ensure_one()
        product = self.product_id
        return (
            product._ab_website_uses_eplus_stock()
            or (product.is_storable and not product.allow_out_of_stock_order)
        )

    def _get_max_available_qty(self):
        self.ensure_one()
        cart_and_free_quantities = [
            line.order_id._get_cart_and_free_qty(line.product_id)
            for line in self._get_lines_with_price()
            if line._ab_website_must_check_stock()
        ]
        if cart_and_free_quantities:
            return min(
                free_qty - cart_qty
                for cart_qty, free_qty in cart_and_free_quantities
            )
        return super()._get_max_available_qty()

    def _check_availability(self):
        self.ensure_one()
        if self.product_id._ab_website_uses_eplus_stock():
            cart_qty, available_qty = self.order_id._get_cart_and_free_qty(self.product_id)
            if cart_qty > available_qty:
                self._set_shop_warning_stock(cart_qty, max(available_qty, 0))
                return False
        return super()._check_availability()
