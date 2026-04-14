from odoo import fields, models
from odoo.tools.translate import _


class AbdinProductBarcodeTemp(models.Model):
    _name = "ab_product_barcode_temp"
    _description = "Abdin Product Barcode Temp"

    name = fields.Char(required=True, index=True)
    product_ids = fields.Many2many(
        comodel_name="ab_product",
        relation="ab_product_barcode_temp_rel",
        column2="product_id",
        column1="barcode_id",
    )

    _uniq_name = models.Constraint(
        "UNIQUE(name)",
        _("Barcode must be unique."),
    )
