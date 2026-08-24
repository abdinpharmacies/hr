from odoo import _, models
from odoo.exceptions import AccessError, UserError


class AbStore(models.Model):
    _inherit = "ab_store"

    def action_open_stock_update(self):
        self.ensure_one()
        if not self.env.user.has_group("ab_stock_update.group_ab_stock_update_manager"):
            raise AccessError(_("Only Stock Update Managers can update branch stock."))

        sto_id = int(self.eplus_serial or 0)
        if sto_id <= 0:
            raise UserError(_("The store must have a valid EPlus Serial before updating stock."))
        if self.with_context(active_test=False).search_count(
            [("eplus_serial", "=", sto_id), ("id", "!=", self.id)],
            limit=1,
        ):
            raise UserError(
                _("EPlus Serial %(sto_id)s is assigned to more than one Odoo store.")
                % {"sto_id": sto_id}
            )

        run = self.env["ab_stock_update_run"].sudo().create(
            {
                "store_id": self.id,
                "sto_id": sto_id,
                "requested_by_id": self.env.user.id,
            }
        )
        run.with_user(self.env.user).action_preview()
        return run.with_user(self.env.user)._get_form_action()
