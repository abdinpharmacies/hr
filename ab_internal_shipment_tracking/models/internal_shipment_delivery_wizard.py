from odoo import api, fields, models, _
from odoo.exceptions import UserError


class InternalShipmentDeliveryWizard(models.TransientModel):
    _name = "ab_internal_shipment.delivery_wizard"
    _description = "Internal Shipment Evidence"

    operation = fields.Selection(
        [
            ("dispatch", "Dispatch Shipment"),
            ("delivery", "Confirm Delivery"),
            ("warehouse_receipt", "Confirm Warehouse Receipt"),
            ("receipt", "Confirm Shipment Receipt"),
        ],
        required=True,
        default="dispatch",
        readonly=True,
    )

    shipment_id = fields.Many2one(
        "ab_internal_shipment",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        "ab_internal_shipment_evidence_wizard_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="Proof of Receipt",
    )
    evidence_required = fields.Boolean(
        default=lambda self: self._default_evidence_required(),
        readonly=True,
    )

    @api.model
    def _default_evidence_required(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("ab_internal_shipment_tracking.delivery_evidence_required", "False")
            .lower()
            in ("1", "true", "yes", "on")
        )

    def action_confirm(self):
        self.ensure_one()
        if self.operation == "delivery" and self.evidence_required and not self.evidence_attachment_ids:
            raise UserError(_("Capture or upload at least one delivery evidence image before delivery."))
        shipment = self.shipment_id
        if self.operation == "dispatch":
            self._add_evidence_to_shipment("dispatch")
            return shipment.with_context(skip_dispatch_evidence_wizard=True).action_send()
        if self.operation == "warehouse_receipt":
            self._add_evidence_to_shipment("receipt")
            return shipment.with_context(skip_warehouse_receipt_evidence_wizard=True).action_confirm_warehouse_receipt()
        if self.operation == "receipt":
            self._add_evidence_to_shipment("receipt")
            return shipment.with_context(skip_receipt_evidence_wizard=True).action_receive()

        self._add_evidence_to_shipment("delivery")
        return shipment.with_context(skip_delivery_evidence_wizard=True).action_deliver()

    def action_confirm_delivery(self):
        return self.action_confirm()

    def _add_evidence_to_shipment(self, evidence_type):
        attachments = self.evidence_attachment_ids
        if not attachments:
            return
        shipment = self.shipment_id
        attachments.write({
            "res_model": shipment._name,
            "res_id": shipment.id,
        })
        commands = [(4, attachment.id) for attachment in attachments]
        shipment.manual_evidence_attachment_ids = commands
        if evidence_type == "dispatch":
            shipment.waybill_attachment_ids = commands
        elif evidence_type == "receipt":
            shipment.receipt_proof_attachment_ids = commands
        elif evidence_type == "delivery":
            shipment.delivery_proof_attachment_ids = commands
