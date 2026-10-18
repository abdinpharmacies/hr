import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Store(models.Model):
    _inherit = 'ab_store'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)

    def _lock_stock_scope(self):
        stores = self.sorted('id')
        stores.check_access('read')
        stores.lock_for_update(allow_referencing=True)
        stores.invalidate_recordset()
        if stores:
            super(Store, stores.sudo()).write({'write_date': fields.Datetime.now()})

    def write(self, vals):
        if 'company_id' in vals:
            if not self.env.is_system():
                raise AccessError(_('Only administrators can change a branch company.'))
            self.check_access('write')
            self._lock_stock_scope()
            changed = self.filtered(lambda store: store.company_id.id != vals['company_id'])
            for model in ('ab_product_source', 'ab_inventory', 'ab_inventory_reservation',
                          'ab_sales_header', 'ab_sales_return_header', 'ab_sales_native_payment'):
                if changed and model in self.env and self.env[model].sudo().search_count([('store_id', 'in', changed.ids)], limit=1):
                    raise ValidationError(_('The company of a branch with stock or sales history cannot change.'))
        return super().write(vals)


class Users(models.Model):
    _inherit = 'res.users'

    source_store_ids = fields.Many2many('ab_store', 'ab_source_user_store_rel', 'user_id', 'store_id', string='Product Source Stores')

    @api.model_create_multi
    def create(self, vals_list):
        if any('source_store_ids' in vals for vals in vals_list) and not self.env.is_system():
            raise AccessError(_('Only administrators can assign product source stores.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'source_store_ids' in vals and not self.env.is_system():
            raise AccessError(_('Only administrators can assign product source stores.'))
        result = super().write(vals)
        if {'source_store_ids', 'inventory_store_ids'} & vals.keys():
            self.env.registry.clear_cache()
        return result

    def _source_is_manager(self):
        self.ensure_one()
        return self.has_group('base.group_system') or self.has_group('ab_product_source.group_source_manager')

    def _source_access_store_ids(self):
        self.ensure_one()
        stores = self.source_store_ids
        if 'inventory_store_ids' in self._fields:
            stores |= self.inventory_store_ids
        return stores.ids

    def _check_source_store(self, store, company):
        self.ensure_one()
        if company not in self.env.companies or (store and store.company_id != company):
            raise AccessError(_('Product sources must belong to an allowed company and its branch.'))
        if store and not self._source_is_manager() and store.id not in self._source_access_store_ids():
            raise AccessError(_('You are not assigned to this product source branch.'))
        if store:
            store.check_access('read')
        return True


class Product(models.Model):
    _inherit = 'ab_product'

    no_expiry_allowed = fields.Boolean(string='Allow Stock Without Expiry', default=False)
    stock_rounding = fields.Float(string='Stock Quantity Increment', default=1, required=True, digits=(16, 6))
    stock_uom_id = fields.Many2one('ab_product_uom', string='Smallest Stock Unit', ondelete='restrict', domain="[('category_id', '=', uom_category_id)]")

    @api.constrains('stock_rounding', 'stock_uom_id', 'uom_category_id', 'allow_sell_fraction')
    def _check_stock_configuration(self):
        for product in self:
            if not math.isfinite(product.stock_rounding) or product.stock_rounding <= 0:
                raise ValidationError(_('The stock quantity increment must be finite and positive.'))
            if not product.allow_sell_fraction and not float(product.stock_rounding).is_integer():
                raise ValidationError(_('Fractional stock increments require the product to allow fractions.'))
            if product.stock_uom_id and (not product.uom_category_id or product.stock_uom_id.category_id != product.uom_category_id):
                raise ValidationError(_('The smallest stock unit must belong to the product unit category.'))

    def _validate_stock_quantity(self, qty):
        self.ensure_one()
        if not isinstance(qty, (int, float)) or isinstance(qty, bool) or not math.isfinite(qty):
            raise ValidationError(_('Stock quantities must be finite numbers.'))
        rounding = self.stock_rounding
        if not rounding or not math.isfinite(rounding) or rounding <= 0:
            raise ValidationError(_('The stock quantity increment must be finite and positive.'))
        if not self.allow_sell_fraction and not math.isclose(qty, round(qty), rel_tol=0, abs_tol=1e-7):
            raise ValidationError(_('This product does not allow fractional stock quantities.'))
        nearest = round(qty / rounding) * rounding
        if (qty and not nearest) or not math.isclose(qty, nearest, rel_tol=0, abs_tol=min(1e-7, rounding * 1e-7)):
            raise ValidationError(_('The quantity does not match the configured stock increment.'))
        return float(nearest)

    def _native_stock_factor(self, uom):
        self.ensure_one()
        uom.ensure_one()
        stock_uom = self.stock_uom_id
        if not stock_uom or not self.uom_category_id or uom.category_id != self.uom_category_id or stock_uom.category_id != uom.category_id:
            raise ValidationError(_('Configure compatible product and smallest stock units before converting quantities.'))
        if any(not factor or not math.isfinite(factor) or factor <= 0 for factor in (uom.factor, stock_uom.factor)):
            raise ValidationError(_('Unit conversion factors must be finite and positive.'))
        return uom.factor / stock_uom.factor

    def _to_stock_quantity(self, qty, uom):
        self.ensure_one()
        if not isinstance(qty, (int, float)) or isinstance(qty, bool) or not math.isfinite(qty):
            raise ValidationError(_('Stock quantities must be finite numbers.'))
        return self._validate_stock_quantity(qty * self._native_stock_factor(uom))

    def _from_stock_quantity(self, qty, uom):
        self.ensure_one()
        normalized = self._native_stock_factor(uom)
        if not normalized:
            raise ValidationError(_('Unit conversion factors must be finite and positive.'))
        return self._validate_stock_quantity(qty) / normalized

    def write(self, vals):
        protected = {'code', 'barcode_ids', 'external_reference', 'no_expiry_allowed', 'stock_uom_id', 'stock_rounding'}
        if protected & vals.keys() and not self.env.is_system():
            manager = self.env.ref('ab_inventory.group_inventory_manager', raise_if_not_found=False)
            if not manager or not self.env.user.has_group('ab_inventory.group_inventory_manager'):
                raise AccessError(_('Only Inventory Managers or administrators can change product identity and stock configuration.'))
        if {'stock_rounding', 'stock_uom_id', 'uom_category_id', 'allow_sell_fraction', 'is_service'} & vals.keys():
            self.lock_for_update(allow_referencing=True)
            self.invalidate_recordset()
            sources = self.env['ab_product_source'].sudo().search([('product_id', 'in', self.ids), ('origin_model', '!=', False)])
            if 'posting_snapshot' in sources._fields and any(sources.mapped('posting_snapshot')):
                raise ValidationError(_('Stock unit and precision configuration cannot change after stock has been posted.'))
        self.check_access('write')
        if {'default_price', 'default_cost'} & vals.keys():
            self.lock_for_update(allow_referencing=True)
            self.invalidate_recordset()
        prices = {rec.id: {name: rec[name] for name in ('default_price', 'default_cost') if name in vals} for rec in self}
        result = super().write(vals)
        for product in self:
            self.env['ab_product_price_history']._record_changes(product, prices[product.id])
        return result


class NativeUnit(models.Model):
    _inherit = 'ab_product_uom'

    @api.constrains('factor', 'rounding')
    def _check_positive_conversion(self):
        if any(not math.isfinite(value) or value <= 0 for unit in self for value in (unit.factor, unit.rounding)):
            raise ValidationError(_('Unit conversion factors and rounding must be finite and positive.'))

    def write(self, vals):
        if {'factor', 'category_id'} & vals.keys():
            self.check_access('write')
            self.lock_for_update(allow_referencing=True)
            products = self.env['ab_product'].sudo().search([('stock_uom_id', 'in', self.ids)])
            sources = self.env['ab_product_source'].sudo().search([('product_id', 'in', products.ids)])
            if 'posting_snapshot' in sources._fields and any(sources.mapped('posting_snapshot')):
                raise ValidationError(_('The smallest stock unit cannot change after stock has been posted.'))
        return super().write(vals)


class ProductCard(models.Model):
    _inherit = 'ab_product_card'

    def write(self, vals):
        if 'is_service' in vals:
            self.check_access('write')
            products = self.env['ab_product'].sudo().search([('product_card_id', 'in', self.ids)])
            products.lock_for_update(allow_referencing=True)
            sources = self.env['ab_product_source'].sudo().search([('product_id', 'in', products.ids)])
            if 'posting_snapshot' in sources._fields and any(sources.mapped('posting_snapshot')):
                raise ValidationError(_('The service classification cannot change after stock has been posted.'))
        return super().write(vals)
