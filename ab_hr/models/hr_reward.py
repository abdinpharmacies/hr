from odoo import api, fields, models


class HrReward(models.Model):
    _name = "hr.reward"
    _description = "Reward"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Name", required=True, tracking=True)
    description = fields.Text(string="Description")
    points_cost = fields.Integer(string="Points Cost", required=True, default=0)
    active = fields.Boolean(default=True)
    image = fields.Binary(string="Image")
    transaction_ids = fields.One2many(
        "hr.reward.transaction",
        "reward_id",
        string="Transactions",
    )
    transaction_count = fields.Integer(
        string="Transaction Count",
        compute="_compute_transaction_count",
        store=False,
    )

    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = len(record.transaction_ids)

    def action_view_transactions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Transactions",
            "res_model": "hr.reward.transaction",
            "view_mode": "tree,form",
            "domain": [("reward_id", "=", self.id)],
            "context": {"default_reward_id": self.id},
        }
