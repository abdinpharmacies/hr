from odoo import fields, models


class AbOdooSyncBranchHardwareRejectWizard(models.TransientModel):
    _name = "ab_odoo_sync_branch_hardware_reject_wizard"
    _description = "AB Odoo Sync Branch Hardware Rejection"

    branch_id = fields.Many2one(
        "ab_odoo_sync_branch_registry",
        string="Branch",
        readonly=True,
        required=True,
    )
    reason = fields.Text(string="Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        return self.branch_id.action_reject_pending_hardware(self.reason)


class AbOdooSyncBranchHardwareReplaceWizard(models.TransientModel):
    _name = "ab_odoo_sync_branch_hardware_replace_wizard"
    _description = "AB Odoo Sync Branch Hardware Replacement"

    branch_id = fields.Many2one(
        "ab_odoo_sync_branch_registry",
        string="Branch",
        readonly=True,
        required=True,
    )
    replacement_hdd_serial = fields.Char(
        string="Replacement Hardware Serial",
        required=True,
    )
    reason = fields.Text(string="Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        return self.branch_id.action_replace_hardware(
            self.replacement_hdd_serial,
            self.reason,
        )
