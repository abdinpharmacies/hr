from odoo import fields, models, _
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    inventory_store_ids = fields.Many2many(
        'ab_store',
        'ab_inventory_user_store_rel',
        'user_id',
        'store_id',
        string='Inventory Stores',
    )

    def write(self, vals):
        if 'inventory_store_ids' in vals and not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Only administrators can assign inventory stores."))
        return super().write(vals)
