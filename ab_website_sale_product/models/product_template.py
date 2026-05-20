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
    eplus_stock_snapshot_ids = fields.One2many(
        related="ab_product_id.eplus_stock_snapshot_ids",
        string="Eplus Stock",
        readonly=True,
        groups="base.group_user",
    )
    eplus_stock_item_count = fields.Integer(
        related="ab_product_id.eplus_stock_item_count",
        string="Eplus Item Count",
        readonly=True,
        groups="base.group_user",
    )
    eplus_stock_total_qty = fields.Float(
        related="ab_product_id.eplus_stock_total_qty",
        string="Eplus Total Quantity",
        readonly=True,
        groups="base.group_user",
    )

    _ab_product_unique = models.UniqueIndex(
        "(ab_product_id) WHERE ab_product_id IS NOT NULL",
        "Each Abdin product can only be linked to one eCommerce product.",
    )

    def action_refresh_eplus_stock_items(self):
        self.ensure_one()
        if not self.ab_product_id:
            return False
        return self.env["ab_eplus_stock_snapshot"].sudo().action_refresh_from_eplus()

    def action_open_eplus_stock_items(self):
        self.ensure_one()
        if not self.ab_product_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Eplus Items - %s" % (self.display_name,),
            "res_model": "ab_eplus_stock_snapshot",
            "view_mode": "list,form,pivot",
            "domain": [("product_id", "=", self.ab_product_id.id)],
            "context": {"search_default_filter_matched": 1},
        }


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
