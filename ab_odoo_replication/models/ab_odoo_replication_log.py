from odoo import api, fields, models
from odoo.tools.translate import _


class AbOdooReplicationLog(models.Model):
    _name = 'ab_odoo_replication_log'
    _description = 'ab_odoo_replication_log'

    model_name = fields.Char(required=True, index=True)
    last_write_date = fields.Datetime()
    last_id = fields.Integer()
    last_run = fields.Datetime()

    # _sql_constraints = [
    #     ('model_name_uniq', 'unique(model_name)', 'Each model must have a single replication cursor record.')
    # ]
