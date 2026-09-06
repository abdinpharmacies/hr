from odoo import fields, models


class AbOdooSyncPassiveMirrorMixin(models.AbstractModel):
    _name = "ab_odoo_sync_passive_mirror_mixin"
    _description = "AB Odoo Sync Passive Mirror Metadata Mixin"

    db_serial = fields.Integer(string="DB Serial", readonly=True, index=True)
    rec_id = fields.Integer(string="Source Record ID", readonly=True, index=True)
    payload_json = fields.Json(string="Full Source Payload", default=dict, readonly=True)
    create_uid = fields.Many2one("ab_users", string="Created by", readonly=True, index=True)
    create_date = fields.Datetime(string="Created on", readonly=True)
    write_uid = fields.Many2one("ab_users", string="Last Updated by", readonly=True, index=True)
    write_date = fields.Datetime(string="Last Updated on", readonly=True)
