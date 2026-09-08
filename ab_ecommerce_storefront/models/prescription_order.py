import secrets

from odoo import api, fields, models, _


class AbPrescriptionOrder(models.Model):
    _name = "ab.prescription.order"
    _description = "Prescription Order"
    _inherit = ["portal.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    partner_id = fields.Many2one("res.partner", required=True, readonly=True, tracking=True)
    user_id = fields.Many2one("res.users", readonly=True, tracking=True)
    prescription_image = fields.Binary(required=True, attachment=True, readonly=True)
    prescription_filename = fields.Char(readonly=True)
    prescription_mimetype = fields.Char(readonly=True)
    customer_note = fields.Text(readonly=True)
    internal_note = fields.Text(tracking=True)
    sale_order_id = fields.Many2one("sale.order", tracking=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    state = fields.Selection(
        [
            ("new", "New"),
            ("under_review", "Under Review"),
            ("waiting_call_center", "Waiting for Call Center"),
            ("confirmed", "Confirmed"),
            ("preparing", "Preparing"),
            ("out_for_delivery", "Out for Delivery"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
            ("rejected", "Rejected"),
        ],
        default="new",
        required=True,
        tracking=True,
    )
    state_label = fields.Char(compute="_compute_state_copy")
    state_description = fields.Char(compute="_compute_state_copy")

    _STATE_COPY = {
        "new": (
            "Prescription received",
            "We received the prescription image successfully.",
        ),
        "under_review": (
            "Under review",
            "Our team is reviewing the prescription and preparing the next steps.",
        ),
        "waiting_call_center": (
            "Waiting for Call Center confirmation",
            "Our Call Center team will contact you to confirm the order details.",
        ),
        "confirmed": (
            "Confirmed",
            "Your prescription request is confirmed and will move to preparation.",
        ),
        "preparing": (
            "Preparing",
            "We are preparing your request now.",
        ),
        "out_for_delivery": (
            "Out for delivery",
            "Your order is on its way to you.",
        ),
        "delivered": (
            "Delivered",
            "Your request was delivered successfully.",
        ),
        "cancelled": (
            "Cancelled",
            "This prescription request was cancelled.",
        ),
        "rejected": (
            "Rejected",
            "This prescription request could not be processed.",
        ),
    }

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = sequence.next_by_code("ab.prescription.order") or _("New")
            if not vals.get("access_token"):
                vals["access_token"] = secrets.token_urlsafe(32)
        return super().create(vals_list)

    def _compute_access_url(self):
        super()._compute_access_url()
        for order in self:
            order.access_url = f"/my/prescriptions/{order.id}"

    def _compute_state_copy(self):
        for order in self:
            label, description = self._STATE_COPY.get(order.state, ("", ""))
            order.state_label = order.env._(label)
            order.state_description = order.env._(description)

    def action_under_review(self):
        self.write({"state": "under_review"})

    def action_waiting_call_center(self):
        self.write({"state": "waiting_call_center"})

    def action_confirmed(self):
        self.write({"state": "confirmed"})

    def action_preparing(self):
        self.write({"state": "preparing"})

    def action_out_for_delivery(self):
        self.write({"state": "out_for_delivery"})

    def action_delivered(self):
        self.write({"state": "delivered"})

    def action_cancelled(self):
        self.write({"state": "cancelled"})

    def action_rejected(self):
        self.write({"state": "rejected"})
