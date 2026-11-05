from odoo import fields, models


class SaleReconciliation(models.TransientModel):
    _name = 'ab_central_sync_sale_reconciliation'
    _description = 'Reconcile Rejected Sale'

    operation_id = fields.Many2one('ab_central_sync_operation', string='Rejected Operation', required=True, readonly=True)
    store_id = fields.Many2one(related='operation_id.store_id', readonly=True)
    sale_id = fields.Many2one('ab_sales_header', string='Posted Central Sale', required=True)
    reason = fields.Text(string='Reconciliation Reason', required=True)

    def action_reconcile(self):
        self.ensure_one()
        self.check_access('write')
        self.operation_id._reconcile_posted_sale(self.sale_id, self.reason)
        return {'type': 'ir.actions.act_window_close'}
