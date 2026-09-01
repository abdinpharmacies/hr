from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    ab_storefront_has_cart_history = fields.Boolean(
        string="Has Storefront Cart History",
        copy=False,
        readonly=True,
    )
    ab_storefront_has_wishlist_history = fields.Boolean(
        string="Has Storefront Wishlist History",
        copy=False,
        readonly=True,
    )
