from odoo import fields, models


class ProjectRole(models.Model):
    _name = "project.role"
    _inherit = ["project.role", "ab_odoo_sync_passive_mirror_mixin"]

    name = fields.Char(required=False, translate=True)
    db_serial = fields.Integer(string="DB Serial", readonly=True, index=True)
    rec_id = fields.Integer(string="Source Record ID", readonly=True, index=True)
    payload_json = fields.Json(string="Full Source Payload", default=dict, readonly=True)

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Project role mirror must be unique per branch and source record.",
    )
