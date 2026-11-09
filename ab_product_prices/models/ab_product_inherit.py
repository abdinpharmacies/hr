from odoo import api, fields, models, _


class AbProductSource(models.Model):
    _name = 'ab_product_source'
    _inherit = 'ab_product_source'

    def name_get(self):
        res = super().name_get()
        if self.env.context.get('show_price_only'):
            res = []
            for rec in self:
                res.append((rec.id, f"{rec.price:.2f}"))
        return res

    @api.depends('price')
    @api.depends_context('show_price_only')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)
