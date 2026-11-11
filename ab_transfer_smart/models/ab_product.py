# -*- coding: utf-8 -*-

from odoo import fields, models

SMART_GROUP_PURCHASE = "ab_transfer_smart.group_transfer_smart_purchase"


class AbProduct(models.Model):
    _inherit = "ab_product"

    min_sale_purchase_qty = fields.Float(
        string="Minimum Sale/Purchase Qty",
        default=1.0,
        digits=(16, 3),
        help="Minimum quantity used for selling, buying, and manual Smart Transfer requests.",
    )
    smart_transfer_min_qty = fields.Float(
        string="Smart Transfer Minimum Qty",
        default=1.0,
        digits=(16, 3),
        help="Default manual quantity used by Smart Transfer product lines.",
    )

    def _check_product_field_write_access(self, vals):
        if (
                vals
                and (
                    "smart_transfer_min_qty" in vals
                    or "min_sale_purchase_qty" in vals
                )
                and self.env.user.has_group(SMART_GROUP_PURCHASE)
        ):
            remaining_vals = {
                field_name: value
                for field_name, value in vals.items()
                if field_name not in ("smart_transfer_min_qty", "min_sale_purchase_qty")
            }
            if not remaining_vals:
                return
            return super()._check_product_field_write_access(remaining_vals)
        return super()._check_product_field_write_access(vals)
