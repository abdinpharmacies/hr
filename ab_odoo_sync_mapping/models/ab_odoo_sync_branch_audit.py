from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbOdooSyncBranchAudit(models.Model):
    _name = "ab_odoo_sync_branch_audit"
    _description = "AB Odoo Sync Branch Security Audit"
    _order = "event_at desc, id desc"

    branch_id = fields.Many2one(
        "ab_odoo_sync_branch_registry",
        string="Branch",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
    )
    db_serial = fields.Integer(
        string="DB Serial",
        related="branch_id.db_serial",
        store=True,
        readonly=True,
        index=True,
    )
    event_type = fields.Selection(
        selection=[
            ("key_rotated", "API Key Rotated"),
            ("hardware_pending", "Hardware Pending Approval"),
            ("hardware_approved", "Hardware Approved"),
            ("hardware_rejected", "Hardware Rejected"),
            ("hardware_replaced", "Hardware Replaced"),
            ("hardware_mismatch", "Hardware Mismatch"),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    hdd_serial = fields.Char(string="Hardware Serial", readonly=True)
    pending_hdd_serial = fields.Char(string="Pending Hardware Serial", readonly=True)
    reason = fields.Text(string="Reason", readonly=True)
    user_id = fields.Many2one(
        "res.users",
        string="User",
        readonly=True,
        default=lambda self: self.env.user,
        index=True,
    )
    event_at = fields.Datetime(
        string="Event At",
        default=fields.Datetime.now,
        readonly=True,
        required=True,
        index=True,
    )

    def write(self, vals):
        raise UserError(_("Branch security audit records cannot be modified."))

    def unlink(self):
        raise UserError(_("Branch security audit records cannot be deleted."))
