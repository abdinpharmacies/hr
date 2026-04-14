from odoo import api, fields, models
from odoo.tools.translate import _


class InheritAbdinInventory(models.Model):
    _inherit = 'ab_inventory'

    no_delete = fields.Boolean(default=True)


class AbInventoryHeader(models.Model):
    _name = 'ab_inventory_header'
    _inherit = 'ab_inventory_header'

    no_delete = fields.Boolean(default=True)
