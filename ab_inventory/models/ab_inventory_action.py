from odoo import api, fields, models
from odoo.tools.translate import _


class InventoryAction(models.Model):
    _name = 'ab_inventory_action'
    _description = 'ab_inventory_action'

    name = fields.Char()
    set_status = fields.Selection(
        selection=[('pending_store', 'Pending Store'),
                   ('pending_main', 'Pending Main'),
                   ('saved', 'Saved Store'),
                   ], required=True)

    store_direction = fields.Selection(
        selection=[('store', 'From Store'),
                   ('to_store', 'To Store'),
                   ], required=True)

    active = fields.Boolean(default=True)
