from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    ab_product_id = fields.Many2one(
        "ab_product",
        string="Abdin Product",
        copy=False,
        index=True,
        ondelete="restrict",
        groups="base.group_user",
    )

    _ab_product_unique = models.UniqueIndex(
        "(ab_product_id) WHERE ab_product_id IS NOT NULL",
        "Each Abdin product can only be linked to one eCommerce product.",
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    ab_product_id = fields.Many2one(
        "ab_product",
        string="Abdin Product",
        related="product_tmpl_id.ab_product_id",
        store=True,
        readonly=True,
        groups="base.group_user",
    )
