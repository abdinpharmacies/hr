from odoo import fields, models


class AbOdooSyncCheckpoint(models.Model):
    _name = "ab_odoo_sync_checkpoint"
    _description = "AB Odoo Sync Checkpoint"

    branch_code = fields.Char(required=True, index=True)
    last_event_id = fields.Integer(default=0, required=True, index=True)
    last_sync_at = fields.Datetime()
    active = fields.Boolean(default=True, index=True)

    _uniq_branch_code = models.Constraint(
        "UNIQUE(branch_code)",
        "Branch code must be unique.",
    )
