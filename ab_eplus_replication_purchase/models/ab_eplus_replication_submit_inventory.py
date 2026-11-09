from time import perf_counter

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class AbEplusReplication(models.AbstractModel):
    _name = 'ab_eplus_replication'
    _inherit = 'ab_eplus_replication'

    def submit_purchases_in_inventory(self):
        for i in range(500):
            purchases = self.env['ab_purchase_header'].sudo().search([('status', '=', 'prepending')], limit=100)
            if not purchases:
                break

            res = self._submit_inventory(purchases)

    def submit_purchase_returns_in_inventory(self):
        for i in range(500):
            purchases = self.env['ab_purchase_notice_header'].sudo().search([('status', '=', 'pending')], limit=100)
            if not purchases:
                break

            res = self._submit_inventory(purchases)

    def _submit_inventory(self, purchases, msg="Submit In Inventory ..."):
        if purchases._name == 'ab_purchase_header':
            msg = 'Submit PURCHASES In Inventory'
        elif purchases._name == 'ab_purchase_notice_header':
            msg = 'Submit NOTICES In Inventory'

        cr = self.env.cr
        res = ""
        for pur in self.web_progress_iter(purchases, msg=msg):
            try:
                pur.btn_submit_inventory()

            except ValidationError as ve:
                res = str(ve) + f",  {msg} -- Pur ID: {pur.id}"
                _logger.warning(res)
                raise ValidationError(res)

        cr.commit()

        return res
        # self.flush_model()
        # self.clear_caches()
