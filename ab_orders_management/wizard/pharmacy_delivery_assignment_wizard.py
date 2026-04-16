from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbPharmacyDeliveryAssignmentWizard(models.TransientModel):
    _name = "ab_pharmacy_delivery_assignment_wizard"
    _description = "Pharmacy Delivery Assignment Wizard"

    pilot_id = fields.Many2one(
        "ab_pharmacy_delivery_pilot",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    target_status = fields.Selection(
        [
            ("free", _("Available")),
            ("in_delivery", _("In Delivery")),
        ],
        required=True,
        default="in_delivery",
    )
    current_order_number = fields.Char(readonly=True)
    current_transaction_type = fields.Selection(
        [
            ("delivery", _("Transaction Delivery")),
            ("order", _("Client Order")),
        ],
        readonly=True,
    )
    current_branch_id = fields.Many2one(
        "ab_pharmacy_delivery_branch",
        readonly=True,
    )
    order_number = fields.Char()
    transaction_type = fields.Selection(
        [
            ("delivery", _("Transaction Delivery")),
            ("order", _("Client Order")),
        ],
    )
    branch_id = fields.Many2one(
        "ab_pharmacy_delivery_branch",
    )
    note = fields.Text(string="Notes")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        pilot_id = self.env.context.get("default_pilot_id")
        if pilot_id:
            pilot = self.env["ab_pharmacy_delivery_pilot"].browse(pilot_id)
            if pilot.exists():
                values.setdefault("pilot_id", pilot.id)
                values.setdefault("target_status", "free" if pilot.status == "in_delivery" else "in_delivery")
                values.setdefault("branch_id", pilot.branch_id.id)
                if pilot.status == "in_delivery":
                    assignment = pilot._get_open_assignment()
                    if assignment:
                        values.setdefault("current_order_number", assignment.order_number)
                        values.setdefault("current_transaction_type", assignment.transaction_type)
                        values.setdefault("current_branch_id", assignment.branch_id.id)
        return values

    @api.onchange("pilot_id")
    def _onchange_pilot_id(self):
        for wizard in self:
            if not wizard.pilot_id:
                continue
            wizard.branch_id = wizard.branch_id or wizard.pilot_id.branch_id
            if wizard.pilot_id.status == "in_delivery" and not wizard.target_status:
                wizard.target_status = "free"
            elif wizard.pilot_id.status == "free" and not wizard.target_status:
                wizard.target_status = "in_delivery"

    @api.onchange("target_status")
    def _onchange_target_status(self):
        for wizard in self:
            if wizard.target_status == "in_delivery" and wizard.pilot_id:
                wizard.branch_id = wizard.branch_id or wizard.pilot_id.branch_id

    def action_apply(self):
        self.ensure_one()
        if not self.pilot_id:
            raise UserError(_("Please select a pilot."))
        if self.target_status == "in_delivery":
            if not self.order_number:
                raise UserError(_("Order number is required."))
            if not self.transaction_type:
                raise UserError(_("Transaction type is required."))
            if not self.branch_id:
                raise UserError(_("Branch is required."))
            self.pilot_id.action_start_delivery(
                self.order_number,
                self.transaction_type,
                self.branch_id.id,
                note=self.note,
            )
        else:
            if self.pilot_id.status == "in_delivery":
                self.pilot_id.action_finish_delivery(note=self.note)
        return {"type": "ir.actions.act_window_close"}
