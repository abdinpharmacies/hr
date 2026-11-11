from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _get_invalidation_fields(self):
        return super()._get_invalidation_fields() | {'inventory_store_ids'}
