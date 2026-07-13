from odoo import api, fields, models, _
from odoo.exceptions import UserError


class InternalShipmentDeliveryWizard(models.TransientModel):
    _name = "ab_internal_shipment.delivery_wizard"
    _description = "Internal Shipment Delivery Evidence"

    shipment_id = fields.Many2one(
        "ab_internal_shipment",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    delivery_proof_attachment_ids = fields.Many2many(
        "ir.attachment",
        "ab_internal_shipment_delivery_wizard_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="Delivery Evidence",
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

    def action_confirm_delivery(self):
        self.ensure_one()
        if self.evidence_required and not self.delivery_proof_attachment_ids:
            raise UserError(_("Capture or upload at least one delivery evidence image before delivery."))
        shipment = self.shipment_id
        if self.delivery_proof_attachment_ids:
            self.delivery_proof_attachment_ids.write(
                {
                    "res_model": shipment._name,
                    "res_id": shipment.id,
                }
            )
            shipment.delivery_proof_attachment_ids = [
                (4, attachment.id) for attachment in self.delivery_proof_attachment_ids
            ]
        return shipment.with_context(skip_delivery_evidence_wizard=True).action_deliver()
