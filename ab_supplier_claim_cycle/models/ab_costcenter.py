from odoo import api, models, _
from odoo.exceptions import UserError


class AbCostCenter(models.Model):
    _inherit = 'ab_costcenter'

    @api.ondelete(at_uninstall=True)
    def _prevent_costcenter_deletion(self):
        raise UserError(_('Archive cost centers instead of deleting them.'))
