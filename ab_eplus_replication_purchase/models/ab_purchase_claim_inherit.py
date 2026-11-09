from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbPurchaseClaim(models.Model):
    _name = 'ab_purchase_claim'
    _inherit = 'ab_purchase_claim'

    def btn_confirm_replication(self):
        if self.je_line_ids:
            eplus_serials_set = set(self.je_line_ids.mapped('je_eplus_serial'))
            # remove eplus_serial=0 (when not (invoice or notice))
            eplus_serials = list(eplus_serials_set - {0})
            if eplus_serials:
                self.env['ab_eplus_replication'].replicate_ab_purchase_confirm(eplus_serials=eplus_serials)
        else:
            raise UserError("Add JE lines to claim to confirm their replication")
