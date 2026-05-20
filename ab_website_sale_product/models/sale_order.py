from odoo import _, models
from odoo.tools import float_is_zero


class SaleOrder(models.Model):
    _inherit = "sale.order"

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
