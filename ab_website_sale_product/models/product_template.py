from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools import float_round


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
    eplus_stock_shown_qty_type = fields.Selection(
        selection=[
            ("quantity", "Quantity"),
            ("percentage", "Percentage"),
        ],
        string="Eplus Stock Shown Qty Type",
        default="quantity",
        required=True,
        groups="base.group_user",
        help="Choose whether eCommerce should show a fixed quantity or a percentage of Eplus stock.",
    )
    eplus_stock_shown_qty_value = fields.Float(
        string="Eplus Stock Shown Qty",
        default=lambda self: self._default_eplus_stock_shown_qty_value(),
        groups="base.group_user",
        help="Quantity or percentage of Eplus stock to show on eCommerce.",
    )

    _ab_product_unique = models.UniqueIndex(
        "(ab_product_id) WHERE ab_product_id IS NOT NULL",
        "Each Abdin product can only be linked to one eCommerce product.",
    )

    @api.constrains("eplus_stock_shown_qty_type", "eplus_stock_shown_qty_value")
    def _check_eplus_stock_shown_qty(self):
        for template in self:
            shown_qty = template.eplus_stock_shown_qty_value
            if shown_qty < 0:
                raise ValidationError(_("Eplus Stock Shown Qty cannot be negative."))
            if template.eplus_stock_shown_qty_type == "percentage" and shown_qty > 100:
                raise ValidationError(_("Eplus Stock Shown Qty percentage cannot exceed 100."))

    def _default_eplus_stock_shown_qty_value(self):
        ab_product_id = self.env.context.get("default_ab_product_id")
        if not ab_product_id:
            return 0.0
        ab_product = self.env["ab_product"].browse(ab_product_id)
        return ab_product.eplus_stock_total_qty or 0.0

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

    def _is_sold_out(self):
        self.ensure_one()
        if self.ab_product_id and not self.ab_product_id.is_service:
            return self.product_variant_id._is_sold_out()
        return super()._is_sold_out()

    def _get_additionnal_combination_info(self, product_or_template, quantity, uom, date, website):
        res = super()._get_additionnal_combination_info(product_or_template, quantity, uom, date, website)
        if not self.env.context.get("website_sale_stock_get_quantity"):
            return res
        if not product_or_template.is_product_variant:
            return res
        product = product_or_template.sudo()
        if not product._ab_website_uses_eplus_stock():
            return res

        computed_qty = product.uom_id._compute_quantity(
            website._get_product_available_qty(product),
            to_unit=uom,
            round=False,
        )
        free_qty = float_round(computed_qty, precision_digits=0, rounding_method="DOWN")
        try:
            cart = request.cart
        except RuntimeError:
            cart = False
        cart_quantity = product.uom_id._compute_quantity(
            cart._get_cart_qty(product.id),
            to_unit=uom,
        ) if cart else 0.0
        res.update({
            "is_storable": True,
            "allow_out_of_stock_order": False,
            "available_threshold": product.available_threshold,
            "free_qty": free_qty,
            "cart_qty": cart_quantity,
            "uom_name": uom.name,
            "uom_rounding": uom.rounding,
            "show_availability": True,
            "out_of_stock_message": product.out_of_stock_message,
        })
        return res


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

    def _ab_website_uses_eplus_stock(self):
        self.ensure_one()
        return bool(self.ab_product_id and not self.ab_product_id.is_service)

    def _get_ab_website_available_qty(self):
        self.ensure_one()
        if not self._ab_website_uses_eplus_stock():
            return None
        groups = self.env["ab_eplus_stock_snapshot"].sudo()._read_group(
            [("product_id", "=", self.ab_product_id.id), ("active", "=", True)],
            [],
            ["itm_qty:sum"],
        )
        eplus_qty = groups[0][0] if groups else 0.0
        eplus_qty = max(eplus_qty or 0.0, 0.0)
        template = self.product_tmpl_id
        shown_qty = max(template.eplus_stock_shown_qty_value or 0.0, 0.0)
        if template.eplus_stock_shown_qty_type == "percentage":
            shown_qty = eplus_qty * shown_qty / 100.0
        return min(shown_qty, eplus_qty)

    def _is_sold_out(self):
        self.ensure_one()
        if self._ab_website_uses_eplus_stock():
            return self._get_ab_website_available_qty() <= 0
        return super()._is_sold_out()
