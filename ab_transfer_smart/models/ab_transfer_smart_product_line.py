# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class AbTransferSmartProductLine(models.Model):
    _name = "ab_transfer_smart_product_line"
    _description = "Smart Transfer Requested Product"
    _order = "sequence, product_id, id"

    sequence = fields.Integer(default=10)
    wizard_id = fields.Many2one(
        "ab_transfer_smart_wizard",
        string="Smart Wizard",
        ondelete="cascade",
        index=True,
    )
    header_id = fields.Many2one(
        "ab_transfer_header",
        string="Transfer",
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        required=True,
        ondelete="restrict",
    )
    product_code = fields.Char(
        related="product_id.code",
        string="Code",
        readonly=True,
        store=True,
    )
    product_name = fields.Char(
        related="product_id.name",
        string="Full Name",
        readonly=True,
    )
    qty = fields.Float(
        string="Quantity",
        default=1.0,
        required=True,
        digits=(16, 3),
    )

    @api.constrains("wizard_id", "header_id")
    def _check_single_parent(self):
        for rec in self:
            if bool(rec.wizard_id) == bool(rec.header_id):
                raise ValidationError(_("Smart product line must belong to one wizard or one transfer."))

    @api.constrains("qty")
    def _check_qty(self):
        for rec in self:
            if float_compare(rec.qty or 0.0, 0.0, precision_digits=3) <= 0:
                raise ValidationError(_("Smart product quantity must be greater than zero."))

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id and not rec.qty:
                rec.qty = rec.product_id.min_sale_purchase_qty or 1.0

    @api.model_create_multi
    def create(self, vals_list):
        product_ids = [vals.get("product_id") for vals in vals_list if vals.get("product_id")]
        products = {
            product.id: product
            for product in self.env["ab_product"].browse(product_ids).exists()
        }
        for vals in vals_list:
            if vals.get("qty"):
                continue
            product = products.get(vals.get("product_id"))
            vals["qty"] = product.min_sale_purchase_qty if product else 1.0
        return super().create(vals_list)
