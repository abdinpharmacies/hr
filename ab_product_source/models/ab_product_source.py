import re
import math
import uuid
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class AbdinProductsSource(models.Model):
    _name = 'ab_product_source'
    _inherit = ['ab_product_template']
    _description = 'Products Source For Purchasing And Opening Balance'
    _rec_name = 'product_id'

    source_identity = fields.Char(readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    store_id = fields.Many2one('ab_store', ondelete='restrict', index=True, copy=False)
    source_type = fields.Selection([
        ('purchase', 'Purchase'), ('opening', 'Opening Stock'), ('other', 'Other Receipt'),
        ('transfer', 'Transfer'), ('adjustment', 'Adjustment'), ('legacy', 'Legacy Import'),
    ], copy=False)
    origin_model = fields.Char(readonly=True, copy=False, index=True)
    origin_res_id = fields.Integer(readonly=True, copy=False)
    origin_database = fields.Char(readonly=True, copy=False)
    parent_source_id = fields.Many2one('ab_product_source', ondelete='restrict', copy=False)
    legacy_reference = fields.Char(copy=False, index=True)
    lot_id = fields.Many2one('ab_product_lot', ondelete='restrict', index=True, copy=False)
    tax_policy_id = fields.Many2one('ab_purchase_tax_policy', ondelete='restrict')
    exp_date = fields.Date()
    no_expiry = fields.Boolean(string='No Expiry')
    price = fields.Float(digits=(16, 3), required=True)

    purchase_price = fields.Float(required=True, digits=(16, 3))

    extra_discount_percentage = fields.Float(digits=(5, 3))

    bonus = fields.Integer()

    product_code = fields.Char(related='product_id.code')

    taxes_ids = fields.Many2many(comodel_name='ab_taxes', relation='ab_product_source_tax_rel',
                                 column1='source_id', column2='tax_id', string="Taxes", ondelete='restrict',
                                 required=True)

    unit_taxes_value = fields.Float(digits=(10, 3), compute='_compute_unit_taxes_value')

    unit_cost = fields.Float(digits=(16, 3), compute='_compute_unit_cost')

    source_model = fields.Char(index=True)

    _source_identity_unique = models.Constraint(
        'UNIQUE(source_identity)', 'Source identities must be unique.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('source_identity') for vals in vals_list):
            raise ValidationError(_('Source identity is assigned automatically and cannot be changed.'))
        if any(set(vals) & {'origin_model', 'origin_res_id', 'origin_database'} for vals in vals_list):
            raise AccessError(_('Source origins are assigned only by their business document.'))
        store_ids = [vals.get('store_id', self.env.context.get('default_store_id')) for vals in vals_list]
        stores = self.env['ab_store'].browse([store_id for store_id in store_ids if store_id]).exists().sorted('id')
        stores.check_access('read')
        stores._lock_stock_scope()
        records = super().create([
            dict(vals, source_identity=str(uuid.uuid4())) for vals in vals_list
        ])
        records._check_source_scope()
        return records

    def write(self, vals):
        if 'source_identity' in vals:
            raise ValidationError(_('Source identity is assigned automatically and cannot be changed.'))
        if {'origin_model', 'origin_res_id', 'origin_database'} & vals.keys():
            raise AccessError(_('Source origins are assigned only by their business document.'))
        self.check_access('write')
        self._lock_source_scope([vals['store_id']] if vals.get('store_id') else [])
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        immutable = {'company_id', 'store_id', 'source_type', 'parent_source_id', 'legacy_reference', 'source_model'}
        if immutable & vals.keys() and any(self.mapped('origin_model')):
            raise ValidationError(_('The origin and scope of a bound source cannot be changed.'))
        prices = {rec.id: {name: rec[name] for name in ('price', 'purchase_price') if name in vals} for rec in self}
        result = super().write(vals)
        self._check_source_scope()
        for source in self:
            self.env['ab_product_price_history']._record_changes(source, prices[source.id])
        return result

    def _lock_source_scope(self, extra_store_ids=None):
        stores = (self.mapped('store_id') | self.env['ab_store'].browse(extra_store_ids or [])).sorted('id')
        stores.check_access('read')
        stores._lock_stock_scope()

    def _check_source_scope(self):
        for source in self:
            source.env.user._check_source_store(source.store_id, source.company_id)
            if source.lot_id and (source.lot_id.company_id != source.company_id
                                 or source.lot_id.store_id != source.store_id
                                 or source.lot_id.product_id != source.product_id
                                 or source.lot_id.exp_date != source.exp_date
                                 or source.lot_id.no_expiry != source.no_expiry):
                raise ValidationError(_('The source and physical lot must have the same product, branch and expiry.'))
            if source.parent_source_id and (source.parent_source_id.product_id != source.product_id or source.parent_source_id.company_id != source.company_id):
                raise ValidationError(_('A source and its parent must refer to the same product and company.'))

    @api.constrains('company_id', 'store_id', 'product_id', 'lot_id', 'exp_date', 'no_expiry', 'parent_source_id')
    def _check_scope_constraints(self):
        self._check_source_scope()
        if self._has_cycle('parent_source_id'):
            raise ValidationError(_('Source provenance cannot contain a cycle.'))

    def _bind_origin(self, store, document_model, document_id, source_type):
        self.check_access('write')
        self._lock_source_scope(store.ids)
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        self.env.user._check_source_store(store, store.company_id)
        if not store or document_model not in self.env or not document_id:
            raise ValidationError(_('A source origin requires a valid branch and business document.'))
        document = self.env[document_model].browse(document_id).exists()
        document.check_access('read')
        if not document or ('store_id' in document._fields and document.store_id != store):
            raise ValidationError(_('The source branch must match its business document.'))
        for source in self:
            if source.origin_model:
                if (source.origin_model, source.origin_res_id, source.store_id, source.source_type) != (
                        document_model, document_id, store, source_type):
                    raise ValidationError(_('A source is already assigned to another business origin.'))
                continue
            if source.store_id and source.store_id != store:
                raise ValidationError(_('A source cannot be assigned to another branch.'))
            super(AbdinProductsSource, source).write({
                'company_id': store.company_id.id, 'store_id': store.id, 'source_type': source_type,
                'origin_model': document_model, 'origin_res_id': document_id,
                'origin_database': self.env.cr.dbname,
            })
        self._check_source_scope()
        return True

    def _check_posting_identity(self):
        for source in self:
            source._check_source_scope()
            if not source.source_identity or not source.store_id or not source.origin_model or not source.source_type:
                raise ValidationError(_('Assign the source branch and business origin before posting stock.'))
            if not source.exp_date and not source.no_expiry:
                raise ValidationError(_('Enter an expiry date or select No Expiry before posting stock.'))
            if source.no_expiry and not source.product_id.no_expiry_allowed:
                raise ValidationError(_('This product is not configured to allow stock without an expiry date.'))
            source._check_expiry_choice()
        return True

    def _ensure_physical_lot(self):
        self.ensure_one()
        self.check_access('write')
        self._lock_source_scope()
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        self._check_posting_identity()
        if not self.lot_id:
            lot = self.env['ab_product_lot'].create({
                'name': self.source_identity,
                'product_id': self.product_id.id,
                'company_id': self.company_id.id,
                'store_id': self.store_id.id,
                'exp_date': self.exp_date,
                'no_expiry': self.no_expiry,
            })
            super(AbdinProductsSource, self).write({'lot_id': lot.id})
        return self.lot_id

    def _get_purchase_tax_values(self, qty=None, bonus=None):
        self.ensure_one()
        snapshot = self._get_posting_snapshot() if 'posting_snapshot' in self._fields else False
        frozen = snapshot.get('tax_calculation') if snapshot else False
        if frozen and qty is None and bonus is None:
            return deepcopy(frozen)
        quantity = self.qty if qty is None else qty
        bonus_quantity = self.bonus if bonus is None else bonus
        if not frozen:
            return self.taxes_ids.with_company(self.company_id)._compute_purchase_values(
                self.purchase_price, quantity, bonus_quantity, self.extra_discount_percentage,
                policy=self.tax_policy_id or None,
            )
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
               for value in (quantity, bonus_quantity)):
            raise ValidationError(_('Tax calculation quantities must be finite and non-negative.'))
        values = deepcopy(frozen)
        quantum = Decimal(1).scaleb(-values['policy']['rounding_digits'])
        def rounded(value):
            return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))
        taxable_quantity = quantity + bonus_quantity if values['policy']['tax_bonus'] else quantity
        for component in values['components']:
            component['amount'] = rounded(component['unit_amount'] * taxable_quantity)
        raw_untaxed = self.purchase_price * quantity * (1 - self.extra_discount_percentage / 100)
        values['untaxed'] = rounded(raw_untaxed)
        values['total_tax'] = rounded(sum(component['amount'] for component in values['components']))
        values['inventory_tax'] = rounded(sum(component['amount'] for component in values['components'] if component['inventory_cost']))
        values['separate_tax'] = rounded(values['total_tax'] - values['inventory_tax'])
        values['total'] = rounded(values['untaxed'] + values['total_tax'])
        values['rounding'] = rounded(values['untaxed'] + values['total_tax'] - raw_untaxed - sum(component['unit_amount'] * taxable_quantity for component in values['components']))
        total_quantity = quantity + bonus_quantity
        values['stock_unit_cost'] = (values['untaxed'] + values['inventory_tax']) / total_quantity if total_quantity else 0
        return values

    def _to_stock_quantity(self, qty):
        self.ensure_one()
        basis = self._get_conversion_basis()
        if not isinstance(qty, (int, float)) or isinstance(qty, bool) or not math.isfinite(qty):
            raise ValidationError(_('Stock quantities must be finite numbers.'))
        numerator, denominator = basis.get('small'), basis.get(basis.get('source_unit'))
        if any(not value or not math.isfinite(value) or value <= 0 for value in (numerator, denominator)):
            raise ValidationError(_('Configure positive unit conversion factors before converting source amounts.'))
        return self.product_id._validate_stock_quantity(qty * numerator / denominator)

    def _from_stock_quantity(self, qty):
        self.ensure_one()
        self.product_id._validate_stock_quantity(qty)
        basis = self._get_conversion_basis()
        numerator, denominator = basis.get(basis.get('source_unit')), basis.get('small')
        if any(not value or not math.isfinite(value) or value <= 0 for value in (numerator, denominator)):
            raise ValidationError(_('Configure positive unit conversion factors before converting source amounts.'))
        return qty * numerator / denominator

    @api.constrains('exp_date', 'no_expiry')
    def _check_expiry_choice(self):
        if any(source.exp_date and source.no_expiry for source in self):
            raise ValidationError(_('Select an expiry date or No Expiry, not both.'))

    @api.onchange('no_expiry')
    def _onchange_no_expiry(self):
        if self.no_expiry:
            self.exp_date = False

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.product_id.display_name} [{rec.id}]"

    def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None):
        domain = fields.Domain(domain or [])
        pattern = r"\*|  "
        new_name = re.sub(pattern, "%", name) + '%'
        name_domain = fields.Domain('product_id.name', '=ilike', new_name)
        if name:
            product_domain = (
                fields.Domain('product_id.barcode_ids', '=ilike', name)
                | fields.Domain('product_id.code', '=ilike', name)
            )
            product_ids = self.search(product_domain)
            if product_ids:
                name_domain = fields.Domain('id', 'in', product_ids.ids)
        return self._search(domain & name_domain, limit=limit, order=order)

    @api.depends('purchase_price', 'extra_discount_percentage', 'unit_taxes_value', 'tax_policy_id.tax_bonus', 'tax_policy_id.discount_timing', 'tax_policy_id.rounding_digits', 'taxes_ids.inventory_cost')
    def _compute_unit_cost(self):
        for rec in self:
            rec.unit_cost = rec.taxes_ids.with_company(rec.company_id)._compute_purchase_values(
                rec.purchase_price, 1, 0, rec.extra_discount_percentage,
                policy=rec.tax_policy_id or None,
            )['unit_cost']

    @api.constrains('price')
    def constrains_price_cost(self):
        if self.env.context.get('eplus_replication'):
            return
        for rec in self:
            if rec.price < rec.unit_cost:
                raise ValidationError(
                    _('%s -- The cost of the product must be less than the selling price') % rec.product_id.display_name)

    @api.depends('purchase_price', 'taxes_ids.percentage', 'taxes_ids.apply_on_total', 'extra_discount_percentage', 'tax_policy_id.tax_bonus', 'tax_policy_id.discount_timing', 'tax_policy_id.rounding_digits')
    def _compute_unit_taxes_value(self):
        for rec in self:
            rec.unit_taxes_value = rec.taxes_ids.with_company(rec.company_id)._compute_purchase_values(
                rec.purchase_price, 1, 0, rec.extra_discount_percentage,
                policy=rec.tax_policy_id or None,
            )['unit_tax']

    def convert_price(self, unit_size):
        self.ensure_one()
        return self._convert_source_amount(self.price, unit_size)

    def convert_cost(self, unit_size):
        self.ensure_one()
        return self._convert_source_amount(self.unit_cost, unit_size)

    def _get_conversion_basis(self):
        self.ensure_one()
        if not self.product_id or not self.uom_id or self.uom_id not in self.product_id.uom_ids:
            raise ValidationError(_('The source unit must be one of the product units.'))
        return {
            'source_unit': self.uom_id.unit_size,
            'large': 1,
            'medium': self.product_id.unit_m_id.unit_no,
            'small': self.product_id.unit_s_id.unit_no,
        }

    def _convert_source_amount(self, amount, unit_size):
        basis = self._get_conversion_basis()
        factors = (basis.get(basis['source_unit']), basis.get(unit_size))
        if any(not factor or not math.isfinite(factor) or factor <= 0 for factor in factors):
            raise ValidationError(_('Configure positive unit conversion factors before converting source amounts.'))
        return amount * factors[0] / factors[1]
