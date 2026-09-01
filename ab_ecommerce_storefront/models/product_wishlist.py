from odoo import models


class ProductWishlist(models.Model):
    _inherit = "product.wishlist"

    def _add_to_wishlist(self, pricelist_id, currency_id, website_id, price, product_id, partner_id=False):
        wish = super()._add_to_wishlist(
            pricelist_id,
            currency_id,
            website_id,
            price,
            product_id,
            partner_id=partner_id,
        )
        if partner_id:
            self.env["res.partner"].sudo().browse(partner_id).write({
                "ab_storefront_has_wishlist_history": True,
            })
        return wish
