from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AbPharmacyDeliveryAssignment(models.Model):
    _name = "ab_pharmacy_delivery_assignment"
    _description = "Pharmacy Delivery Assignment"
    _order = "start_datetime desc, id desc"
    _rec_name = "order_number"

    pilot_id = fields.Many2one(
        "ab_pharmacy_delivery_pilot",
        required=True,
        ondelete="cascade",
        index=True,
    )
    branch_id = fields.Many2one(
        "ab_pharmacy_delivery_branch",
        required=True,
        ondelete="restrict",
        index=True,
    )
    order_number = fields.Char(required=True, index=True)
    transaction_type = fields.Selection(
        [
            ("delivery", "Transaction Delivery"),
            ("order", "Client Order"),
        ],
        required=True,
        index=True,
    )
    status = fields.Selection(
        [
            ("assigned", "Assigned"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="assigned",
        required=True,
        index=True,
    )
    start_datetime = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    end_datetime = fields.Datetime(index=True)
    note = fields.Text()
    assigned_by_user_id = fields.Many2one(
        "res.users",
        string="Assigned By",
        readonly=True,
        default=lambda self: self.env.user,
        ondelete="restrict",
    )
    completed_by_user_id = fields.Many2one(
        "res.users",
        string="Completed By",
        readonly=True,
        ondelete="restrict",
    )
    completed_by_pilot_id = fields.Many2one(
        "ab_pharmacy_delivery_pilot",
        string="Pilot Name",
        related="pilot_id",
        readonly=True,
        store=True,
    )

    _uniq_assignment_order = models.Constraint(
        "UNIQUE(branch_id, order_number, transaction_type)",
        "The same order number cannot be duplicated for the same branch and type.",
    )

    @api.onchange("pilot_id")
    def _onchange_pilot_id(self):
        for assignment in self:
            if assignment.pilot_id and not assignment.branch_id:
                assignment.branch_id = assignment.pilot_id.branch_id

    @api.constrains("status", "end_datetime")
    def _check_completion_data(self):
        for assignment in self:
            if assignment.status == "done" and not assignment.end_datetime:
                raise ValidationError(_("Completed assignments must have an end datetime."))
            if assignment.status in {"assigned", "cancelled"} and assignment.end_datetime:
                raise ValidationError(_("Only done assignments can have an end datetime."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            pilot_id = vals.get("pilot_id")
            branch_id = vals.get("branch_id")
            if pilot_id and not branch_id:
                pilot = self.env["ab_pharmacy_delivery_pilot"].browse(pilot_id)
                if pilot.exists():
                    vals["branch_id"] = pilot.branch_id.id
        records = super().create(vals_list)
        records.mapped("pilot_id")._sync_status_from_assignments()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.mapped("pilot_id")._sync_status_from_assignments()
        return res

    def unlink(self):
        pilots = self.mapped("pilot_id")
        res = super().unlink()
        pilots._sync_status_from_assignments()
        return res

    def action_mark_done(self, note=False):
        for assignment in self:
            if assignment.status != "assigned":
                raise UserError(_("Only assigned records can be completed."))
            assignment.write(
                {
                    "status": "done",
                    "end_datetime": fields.Datetime.now(),
                    "completed_by_user_id": self.env.user.id,
                    "note": "\n".join(filter(None, [assignment.note or "", note or ""])).strip(),
                }
            )
        return True

    def action_cancel(self, note=False):
        for assignment in self:
            if assignment.status != "assigned":
                raise UserError(_("Only assigned records can be cancelled."))
            assignment.write(
                {
                    "status": "cancelled",
                    "end_datetime": fields.Datetime.now(),
                    "completed_by_user_id": self.env.user.id,
                    "note": "\n".join(filter(None, [assignment.note or "", note or ""])).strip(),
                }
            )
        return True
