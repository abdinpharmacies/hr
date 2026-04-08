from odoo import api, fields, models


class HrRewardTransaction(models.Model):
    _name = "hr.reward.transaction"
    _description = "Reward Transaction"
    _order = "date desc, create_date desc"

    employee_id = fields.Many2one(
        "ab_hr_employee",
        string="Employee",
        required=True,
        tracking=True,
    )
    reward_id = fields.Many2one(
        "hr.reward",
        string="Reward",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    points = fields.Integer(string="Points", required=True)
    type = fields.Selection(
        [
            ("earn", "Earn"),
            ("redeem", "Redeem"),
        ],
        string="Type",
        required=True,
        default="earn",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="State",
        required=True,
        default="draft",
        tracking=True,
    )
    date = fields.Date(string="Date", required=True, default=fields.Date.today)
    approved_by = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
    )
    notes = fields.Text(string="Notes")
    balance_id = fields.Many2one(
        "hr.reward.balance",
        string="Balance",
        ondelete="cascade",
    )

    def action_approve(self):
        for record in self:
            record.write(
                {
                    "state": "approved",
                    "approved_by": self.env.user.id,
                }
            )

    def action_reject(self):
        self.write({"state": "rejected"})

    def action_pending(self):
        self.write({"state": "pending"})
