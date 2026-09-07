from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbOdooSyncBranchRegistry(models.Model):
    _name = "ab_odoo_sync_branch_registry"
    _inherit = "ab_odoo_sync_passive_mirror_mixin"
    _log_access = False
    _description = "AB Odoo Sync Branch Registration"
    _order = "db_serial"

    name = fields.Char()
    db_serial = fields.Integer(string="DB Serial", index=True)
    last_upload_at = fields.Datetime(string="Last Upload At", readonly=True)
    active = fields.Boolean(default=True, index=True)

    _uniq_db_serial = models.Constraint(
        "UNIQUE(db_serial)",
        "DB serial must be unique in the branch registry.",
    )
    _uniq_sync_identity = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Source DB and record ID must be unique per branch registration.",
    )
    _positive_db_serial = models.Constraint(
        "CHECK(db_serial > 0)",
        "DB serial must be a positive integer.",
    )

    def unlink(self):
        raise UserError(_("Archive branch registrations instead of deleting them."))
