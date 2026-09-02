from odoo import fields, models


class ProjectRole(models.Model):
    _inherit = "project.role"

    name = fields.Char(required=False, translate=True)
    db_serial = fields.Integer(string="DB Serial", readonly=True, index=True)
    rec_id = fields.Integer(string="Source Record ID", readonly=True, index=True)
    payload_json = fields.Json(string="Full Source Payload", default=dict, readonly=True)

    _uniq_branch_source = models.Constraint(
        "UNIQUE(db_serial, rec_id)",
        "Project role mirror must be unique per branch and source record.",
    )
