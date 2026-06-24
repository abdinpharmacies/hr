from odoo import fields, models


class InternalShipmentHistory(models.Model):
    _name = "ab_internal_shipment.history"
    _description = "Internal Shipment History"
    _order = "action_date desc, id desc"

    shipment_id = fields.Many2one(
        "ab_internal_shipment",
        string="Shipment",
        required=True,
        ondelete="cascade",
        index=True,
    )
    action = fields.Selection(
        [
            ("created", "Created"),
            ("sent", "Sent"),
            ("in_transit", "In Transit"),
            ("delivered", "Delivered"),
            ("received", "Confirmed"),
            ("closed", "Closed"),
            ("note", "Note"),
        ],
        required=True,
        index=True,
    )
    action_by_id = fields.Many2one(
        "res.users",
        string="Action By",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    action_date = fields.Datetime(
        string="Action Date",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    state_from = fields.Char(string="State Before Action", readonly=True)
    state_to = fields.Char(string="State After Action")
    from_holder_display = fields.Char(readonly=True)
    to_holder_display = fields.Char(readonly=True)
    notes = fields.Text()
