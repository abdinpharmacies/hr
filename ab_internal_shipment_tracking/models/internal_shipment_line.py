from odoo import fields, models


class InternalShipmentLine(models.Model):
    _name = "ab_internal_shipment.line"
    _description = "Internal Shipment Line"
    _order = "id"

    shipment_id = fields.Many2one(
        "ab_internal_shipment",
        string="Shipment",
        required=True,
        ondelete="cascade",
        index=True,
    )
    item_name = fields.Char(required=True)
    description = fields.Text()
    quantity = fields.Float(default=1.0, required=True)
    notes = fields.Text()

    _quantity_positive = models.Constraint(
        "CHECK(quantity > 0)",
        "Shipment line quantities must be positive.",
    )
