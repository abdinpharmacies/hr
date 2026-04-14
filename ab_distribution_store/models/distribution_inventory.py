from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class DistributionStoreInventory(models.Model):
    _name = 'ab_distribution_store_inventory'
    _description = 'Distribution Store Inventory'
    _order = 'product_id, expiry_date, batch_number'

    product_id = fields.Many2one('ab_distribution_store_product', required=True, index=True)
    balance = fields.Float(default=0.0)
    pharma_price = fields.Float(digits=(16, 2))
    customer_price = fields.Float(digits=(16, 2))
    batch_number = fields.Char()
    expiry_date = fields.Date()

    @api.constrains('balance')
    def _check_balance(self):
        for rec in self:
            if rec.balance < 0:
                raise ValidationError(_("Balance cannot be negative."))

    @api.model
    def load(self, fields, data):
        mapped_fields = [
            'product_id/id' if field == 'product_id.id' else field
            for field in fields
        ]
        return super().load(mapped_fields, data)

    @api.depends('product_id', 'product_id.code', 'batch_number', 'expiry_date')
    def _compute_display_name(self):
        for rec in self:
            code = rec.product_id.code or ''
            name = rec.product_id.display_name or rec.product_id.name or ''
            product_label = " - ".join([part for part in [code, name] if part])
            parts = [product_label or name or code or '']
            if rec.batch_number:
                parts.append(rec.batch_number)
            if rec.expiry_date:
                parts.append(str(rec.expiry_date))
            rec.display_name = " / ".join([part for part in parts if part]) or str(rec.id)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = [
                '|', '|',
                ('batch_number', operator, name),
                ('product_id.name', operator, name),
                ('product_id.code', operator, name),
            ]
        records = self.search(domain + args, limit=limit)
        return [(rec.id, rec.display_name) for rec in records]
