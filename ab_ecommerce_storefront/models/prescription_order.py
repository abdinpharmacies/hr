import secrets

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__)


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
    internal_note = fields.Text(groups="base.group_user")
    payment_method_id = fields.Many2one(
        "payment.method",
        string="Preferred Payment Method",
        readonly=True,
        tracking=True,
    )
    sale_order_id = fields.Many2one("sale.order", tracking=True)
    website_id = fields.Many2one("website", readonly=True)
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
            _lt("Prescription received"),
            _lt("We received the prescription image successfully."),
        ),
        "under_review": (
            _lt("Reviewing prescription"),
            _lt("The pharmacy team is reviewing the prescription."),
        ),
        "waiting_call_center": (
            _lt("Waiting for Call Center confirmation"),
            _lt("The Call Center team will contact you to confirm the order details."),
        ),
        "confirmed": (
            _lt("Order confirmed"),
            _lt("The order is confirmed by Abdin Pharmacies."),
        ),
        "preparing": (
            _lt("Preparing order"),
            _lt("Your items are reserved for preparation."),
        ),
        "out_for_delivery": (
            _lt("Out for delivery"),
            _lt("Your order has left the pharmacy and is on the way."),
        ),
        "delivered": (
            _lt("Delivered"),
            _lt("Your order has been delivered."),
        ),
        "cancelled": (
            _lt("Cancelled"),
            _lt("This prescription request was cancelled."),
        ),
        "rejected": (
            _lt("Rejected"),
            _lt("This prescription request could not be processed."),
        ),
    }

    _STATE_SEQUENCE = [
        "new",
        "under_review",
        "waiting_call_center",
        "confirmed",
        "preparing",
        "out_for_delivery",
        "delivered",
    ]

    @api.model
    def _ab_storefront_cash_on_delivery_method(self, company=None):
        company = company or self.env.company
        providers = self.env["payment.provider"].sudo().search([
            ("code", "=", "custom"),
            ("custom_mode", "=", "cash_on_delivery"),
            ("state", "in", ("enabled", "test")),
            ("company_id", "=", company.id),
        ])
        return providers.payment_method_ids.filtered(
            lambda method: method.active and method.code == "cash_on_delivery"
        ).sorted(lambda method: (method.sequence, method.id))[:1]

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("payment_method_id"):
                company = self.env["res.company"].browse(
                    vals.get("company_id")
                ).exists() or self.env.company
                payment_method = self._ab_storefront_cash_on_delivery_method(company)
                if payment_method:
                    vals["payment_method_id"] = payment_method.id
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = sequence.next_by_code("ab.prescription.order") or _("New")
            if not vals.get("access_token"):
                vals["access_token"] = secrets.token_urlsafe(32)
        return super().create(vals_list)

    def _ab_storefront_state_index(self):
        self.ensure_one()
        if self.state in self._STATE_SEQUENCE:
            return self._STATE_SEQUENCE.index(self.state)
        return 0

    def _ab_storefront_create_sale_order(self, allow_unreviewed=False):
        self.ensure_one()
        self.check_access("write")
        if self.sale_order_id:
            return self.sale_order_id
        if not allow_unreviewed and self.state not in ("waiting_call_center", "confirmed"):
            raise ValidationError(_("Review the prescription before creating a quotation."))
        sale_order = self.env["sale.order"].create({
            "partner_id": self.partner_id.id,
            "partner_invoice_id": self.partner_id.id,
            "partner_shipping_id": self.partner_id.id,
            "origin": self.name,
            "client_order_ref": self.name,
            "company_id": self.company_id.id,
            "website_id": self.website_id.id,
        })
        sale_order._portal_ensure_token()
        self.write({"sale_order_id": sale_order.id})
        return sale_order

    def action_create_sale_order(self):
        self.ensure_one()
        order = self._ab_storefront_create_sale_order()
        return {"type": "ir.actions.act_window", "res_model": "sale.order",
                "res_id": order.id, "view_mode": "form"}

    @api.constrains("sale_order_id", "partner_id", "company_id", "website_id")
    def _check_sale_order_customer(self):
        for prescription in self:
            order = prescription.sale_order_id
            if order and (
                order.partner_id.commercial_partner_id != prescription.partner_id.commercial_partner_id
                or order.company_id != prescription.company_id
                or (prescription.website_id and order.website_id != prescription.website_id)
            ):
                raise ValidationError(_("The sale order must belong to the same customer, company and website."))

    def _ab_storefront_tracking_steps(self, include_order=True):
        self.ensure_one()
        linked_order = self.sale_order_id
        if include_order and linked_order:
            return linked_order._ab_storefront_tracking_steps()
        keys = self._STATE_SEQUENCE[:4] if linked_order else self._STATE_SEQUENCE
        current = self._ab_storefront_state_index()
        terminal = self.state in ("cancelled", "rejected")
        steps = []
        for index, key in enumerate(keys):
            if terminal and index > 0:
                break
            # Linked orders own confirmation and fulfillment; review remains independent.
            if linked_order and key == "confirmed":
                break
            if linked_order.state == "sale" and index > current:
                continue
            label, description = self._STATE_COPY[key]
            steps.append({
                "key": "prescription_" + key,
                "label": self.env._(label), "description": self.env._(description),
                "state": "complete" if terminal or index < current or linked_order.state == "sale"
                else ("current" if index == current else "pending"),
            })
        if terminal:
            label, description = self._STATE_COPY[self.state]
            steps.append({"key": self.state, "label": self.env._(label),
                          "description": self.env._(description), "state": "exception"})
        return steps

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
        self._check_unlinked_fulfillment()
        self.write({"state": "preparing"})

    def action_out_for_delivery(self):
        self._check_unlinked_fulfillment()
        self.write({"state": "out_for_delivery"})

    def action_delivered(self):
        self._check_unlinked_fulfillment()
        self.write({"state": "delivered"})

    def _check_unlinked_fulfillment(self):
        self.check_access("write")
        if self.sale_order_id:
            raise ValidationError(_("Manage preparation and delivery on the linked sale order."))

    def action_cancelled(self):
        self.write({"state": "cancelled"})

    def action_rejected(self):
        self.write({"state": "rejected"})
