from odoo import models


class Website(models.Model):
    _inherit = "website"

    def _get_product_available_qty(self, product, **kwargs):
        product.ensure_one()
        if product._ab_website_uses_eplus_stock():
            return product._get_ab_website_available_qty()
        return super()._get_product_available_qty(product, **kwargs)
