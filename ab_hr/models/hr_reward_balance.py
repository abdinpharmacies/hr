from odoo import api, fields, models


class HrRewardBalance(models.Model):
    _name = "hr.reward.balance"
    _description = "Reward Balance"
    _order = "employee_id"
    _rec_name = "employee_id"

    employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Employee",
        required=True,
        ondelete="cascade",
    )
    earned_points = fields.Integer(
        string="Earned Points",
        compute="_compute_points",
        store=False,
    )
    redeemed_points = fields.Integer(
        string="Redeemed Points",
        compute="_compute_points",
        store=False,
    )
    total_points = fields.Integer(
        string="Total Points",
        compute="_compute_points",
        store=False,
    )
    transaction_ids = fields.One2many(
        "hr.reward.transaction",
        "balance_id",
        string="Transactions",
    )

    def _compute_points(self):
        for record in self:
            earned = sum(
                record.transaction_ids.filtered(lambda t: t.type == "earn" and t.state == "approved").mapped("points")
            )
            redeemed = sum(
                record.transaction_ids.filtered(lambda t: t.type == "redeem" and t.state == "approved").mapped("points")
            )
            record.earned_points = earned
            record.redeemed_points = redeemed
            record.total_points = earned - redeemed

    @api.model
    def get_or_create_balance(self, employee_id):
        balance = self.search([("employee_id", "=", employee_id)], limit=1)
        if not balance:
            balance = self.create({"employee_id": employee_id})
        return balance
