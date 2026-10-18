from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class ProductPriceHistory(models.Model):
    _name = 'ab_product_price_history'
    _description = 'Product Price Change History'
    _order = 'changed_at desc, id desc'

    product_id = fields.Many2one('ab_product', required=True, ondelete='restrict', index=True)
    source_id = fields.Many2one('ab_product_source', ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    store_id = fields.Many2one('ab_store', ondelete='restrict', index=True)
    field_name = fields.Char(required=True)
    old_price = fields.Float(digits=(16, 6), required=True)
    new_price = fields.Float(digits=(16, 6), required=True)
    changed_by = fields.Many2one('res.users', required=True, ondelete='restrict')
    changed_at = fields.Datetime(required=True)

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Price history is created only by audited price changes.'))

    def write(self, vals):
        raise AccessError(_('Price history cannot be changed or deleted.'))

    def unlink(self):
        raise AccessError(_('Price history cannot be changed or deleted.'))

    def _record_changes(self, record, before):
        record.ensure_one()
        source = record if record._name == 'ab_product_source' else False
        values = [dict(
            product_id=source.product_id.id if source else record.id,
            source_id=source.id if source else False,
            company_id=source.company_id.id if source else self.env.company.id,
            store_id=source.store_id.id if source else False,
            field_name=name, old_price=value, new_price=record[name],
            changed_by=self.env.uid, changed_at=fields.Datetime.now(),
        ) for name, value in before.items() if value != record[name]]
        if values:
            super(ProductPriceHistory, self.sudo()).create(values)
        return True
