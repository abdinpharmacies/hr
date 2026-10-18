from odoo import Command, fields, models, _


class AbInventoryBalanceReport(models.TransientModel):
    _name = 'ab_inventory_balance_report'
    _description = 'Current Stock Balance Report'

    store_id = fields.Many2one(
        'ab_store', string='Store', required=True,
        default=lambda self: self.env.user.inventory_store_ids[:1].id,
    )
    product_id = fields.Many2one('ab_product', string='Item')
    include_zero = fields.Boolean(string='Include Zero Balances')
    generated_at = fields.Datetime(string='Calculated At', readonly=True)
    line_ids = fields.One2many(
        'ab_inventory_balance_report_line', 'report_id', readonly=True,
    )

    def action_generate(self):
        self.ensure_one()
        process = self.env['ab_inventory_process']
        store = process._check_store(self.store_id.id)
        rows = process._balances(store, product_id=self.product_id.id or None)
        balances = {}
        for row in rows:
            key = (row.product_id.id, row.source_id.id)
            balances[key] = balances.get(key, 0) + row.on_hand
        self.write({
            'generated_at': fields.Datetime.now(),
            'line_ids': [Command.clear()] + [
                Command.create({'product_id': product_id, 'source_id': source_id, 'balance_qty': qty})
                for (product_id, source_id), qty in balances.items() if qty or self.include_zero
            ],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Current Stock Balance'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class AbInventoryBalanceReportLine(models.TransientModel):
    _name = 'ab_inventory_balance_report_line'
    _description = 'Current Stock Balance Line'
    _order = 'source_id'

    report_id = fields.Many2one('ab_inventory_balance_report', required=True, ondelete='cascade')
    source_id = fields.Many2one('ab_product_source', string='Batch / Source', readonly=True)
    product_id = fields.Many2one('ab_product', string='Item', readonly=True)
    balance_qty = fields.Float(digits=(20, 6), string='Balance (Smallest Unit)', readonly=True)
