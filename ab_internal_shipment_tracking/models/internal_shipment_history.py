from odoo import api, fields, models, _
from odoo.exceptions import UserError


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
            ("warehouse_received", "Warehouse Received"),
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

    @api.model_create_multi
    def create(self, vals_list):
        self._check_followup_notes_not_closed(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._check_followup_notes_not_closed(vals, records=self)
        return super().write(vals)

    def unlink(self):
        self._check_followup_notes_not_closed({}, records=self)
        return super().unlink()

    @api.model
    def _check_followup_notes_not_closed(self, vals, records=None):
        vals_list = vals if isinstance(vals, list) else [vals]
        if records:
            vals_list = vals_list * len(records)
            record_values = zip(records, vals_list)
        else:
            record_values = ((self.browse(), item) for item in vals_list)

        shipment_ids = {
            item.get("shipment_id")
            for _, item in record_values
            if item.get("shipment_id")
        }
        shipments = self.env["ab_internal_shipment"].browse(shipment_ids)
        shipment_by_id = {shipment.id: shipment for shipment in shipments}

        if records:
            record_values = zip(records, vals_list)
        else:
            record_values = ((self.browse(), item) for item in vals_list)

        for record, item in record_values:
            action = item["action"] if "action" in item else record.action
            shipment = shipment_by_id.get(item.get("shipment_id"))
            if not shipment:
                shipment = record.shipment_id
            if action == "note" and shipment.state == "closed":
                raise UserError(_("Follow-up notes cannot be changed after the shipment is closed."))
