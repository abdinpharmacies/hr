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
        balances = self.env['ab_inventory_process'].get_source_balances(
            self.store_id.id, product_id=self.product_id.id or None,
            include_zero=self.include_zero,
        )
        self.write({
            'generated_at': fields.Datetime.now(),
            'line_ids': [Command.clear()] + [
                Command.create({'source_id': source_id,
                                'balance_qty': balances[source_id]})
                for source_id in sorted(balances)
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
    product_id = fields.Many2one('ab_product', related='source_id.product_id', string='Item')
    balance_qty = fields.Integer(string='Balance (Smallest Unit)', readonly=True)
