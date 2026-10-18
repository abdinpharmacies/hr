import json

from odoo import fields, models


class InventoryIntegrityReview(models.TransientModel):
    _name = 'ab_inventory_integrity_review'
    _description = 'Inventory Integrity Review'

    store_id = fields.Many2one('ab_store', required=True)
    reason = fields.Char()
    result = fields.Text(readonly=True)

    def action_check(self):
        self.ensure_one()
        result = self.env['ab_inventory_process'].check_integrity(self.store_id.id)
        self.result = json.dumps(result, ensure_ascii=False, indent=2)
        return self._reopen()

    def action_rebuild(self):
        self.ensure_one()
        result = self.env['ab_inventory_process'].rebuild_projection(self.store_id.id, self.reason)
        self.result = json.dumps(result, ensure_ascii=False, indent=2)
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}
