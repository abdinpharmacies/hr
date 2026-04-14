from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EmployeeToolsInventoryMove(models.Model):
    _name = "ab_employee_tools.inventory_move"
    _description = "Employee Tools Inventory Move"
    _order = "date desc, id desc"

    movement_type = fields.Selection(
        [
            ("receive", "Receive"),
            ("issue", "Issue"),
        ],
        required=True,
        default="receive",
    )
    type_id = fields.Many2one(
        "ab_employee_tools.tools_type",
        string="Tool Type",
        required=True,
        ondelete="cascade",
    )
    quantity = fields.Integer(string="Quantity", default=0)
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    user_id = fields.Many2one(
        "res.users", default=lambda self: self.env.user, required=True
    )
    notes = fields.Text()

    @api.constrains("quantity")
    def _check_quantities(self):
        for rec in self:
            if rec.quantity < 0:
                raise ValidationError(_("Quantity must be zero or positive."))

    def _compute_qty_delta(self):
        self.ensure_one()
        if self.movement_type == "receive":
            return self.quantity
        if self.movement_type == "issue":
            return -self.quantity
        return 0

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            delta = move._compute_qty_delta()
            if (move.type_id.qty_available or 0) + delta < 0:
                raise ValidationError(_("Not enough available units for this tool type."))
            if delta:
                move.type_id.qty_available += delta
        return moves

    def write(self, vals):
        if "movement_type" in vals or "quantity" in vals:
            for move in self:
                old_delta = move._compute_qty_delta()
                new_delta = move._compute_qty_delta_after(vals)
                if (move.type_id.qty_available or 0) - old_delta + new_delta < 0:
                    raise ValidationError(_("Not enough available units for this tool type."))
                if old_delta != new_delta:
                    move.type_id.qty_available += (new_delta - old_delta)
        return super().write(vals)

    def _compute_qty_delta_after(self, vals):
        self.ensure_one()
        movement_type = vals.get("movement_type", self.movement_type)
        quantity = vals.get("quantity", self.quantity)
        if movement_type == "receive":
            return quantity
        if movement_type == "issue":
            return -quantity
        return 0

    def unlink(self):
        for move in self:
            delta = move._compute_qty_delta()
            if delta:
                move.type_id.qty_available -= delta
        return super().unlink()
