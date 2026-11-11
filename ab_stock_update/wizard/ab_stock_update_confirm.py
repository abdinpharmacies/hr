from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class AbStockUpdateConfirmWizard(models.TransientModel):
    _name = "ab_stock_update_confirm_wizard"
    _description = "Confirm Stock Update"

    run_id = fields.Many2one(
        "ab_stock_update_run",
        string="Stock Update Run",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    acknowledge_live = fields.Boolean(
        string="I understand that live branch activity may cause stock drift"
    )

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("ab_stock_update.group_ab_stock_update_manager"):
            raise AccessError(_("Only Stock Update Managers can update branch stock."))
        if not self.acknowledge_live:
            raise UserError(_("Confirm the live-stock warning before applying the update."))
        return self.run_id.action_apply_confirmed()
