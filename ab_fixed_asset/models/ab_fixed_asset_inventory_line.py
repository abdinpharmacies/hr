from odoo import api, fields, models, _


class AbFixedAssetCurrInvInventory(models.Model):
    _name = 'ab_fixed_asset_inventory_line'
    _description = 'ab_fixed_asset_inventory_line'

    fixed_asset_header_id = fields.Many2one('ab_fixed_asset_assets_inventory', required=True)
    name = fields.Char()
    qty = fields.Integer()
    price = fields.Float(default=0.0, digits=(18, 2))
    total_price = fields.Float(compute='_compute_total_price')

    @api.depends('qty', 'price')
    def _compute_total_price(self):
        for rec in self:
            rec.total_price = rec.qty * rec.price

    def action_save(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f"{rec.name}:: {rec.qty}"))
        return res

    @api.depends('name', 'qty')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)
