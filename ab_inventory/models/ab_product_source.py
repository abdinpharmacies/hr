from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbProductSource(models.Model):
    _inherit = 'ab_product_source'

    posting_snapshot = fields.Json(
        string='Posted Source Snapshot', readonly=True, copy=False,
        groups='base.group_system,ab_inventory.group_inventory_manager',
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('posting_snapshot') for vals in vals_list):
            raise ValidationError(_('Source snapshots are created only by inventory posting.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'posting_snapshot' in vals:
            raise ValidationError(_('Source snapshots are created only by inventory posting.'))
        protected = {'product_id', 'uom_id', 'qty', 'bonus', 'price', 'purchase_price',
                     'extra_discount_percentage', 'taxes_ids', 'tax_policy_id', 'lot_id', 'exp_date', 'no_expiry'}
        if protected & vals.keys():
            self.check_access('write')
            self._lock_source_scope()
            self.lock_for_update(allow_referencing=True)
            self.invalidate_recordset()
            has_saved = self.env['ab_inventory'].sudo().search_count([
                ('source_id', 'in', self.ids), ('status', '=', 'saved'),
            ])
            if has_saved or any(source._get_posting_snapshot() for source in self):
                raise ValidationError(_(
                    "Posted source quantities, prices, taxes, units and expiry cannot be changed."
                ))
        return super().write(vals)

    def unlink(self):
        self.check_access('unlink')
        self.lock_for_update(allow_referencing=True)
        if any(source._get_posting_snapshot() for source in self) or self.env['ab_inventory'].sudo().search_count([
            ('source_id', 'in', self.ids), ('status', '=', 'saved'),
        ]):
            raise ValidationError(_('Posted product sources cannot be deleted.'))
        return super().unlink()

    def _get_posting_snapshot(self):
        self.ensure_one()
        self.check_access('read')
        return self.sudo().posting_snapshot

    @api.depends('qty', 'uom_id', 'product_id', 'posting_snapshot')
    def _compute_qty_large(self):
        frozen = self.filtered(lambda source: source._get_posting_snapshot())
        super(AbProductSource, self - frozen)._compute_qty_large()
        for source in frozen:
            basis = source._get_conversion_basis()
            source.qty_large = source.qty / basis[basis['source_unit']]

    @api.depends('purchase_price', 'extra_discount_percentage', 'unit_taxes_value', 'posting_snapshot')
    def _compute_unit_cost(self):
        draft = self.filtered(lambda source: not source._get_posting_snapshot())
        super(AbProductSource, draft)._compute_unit_cost()
        for source in self:
            snapshot = source._get_posting_snapshot()
            if snapshot:
                source.unit_cost = snapshot['unit_cost']

    @api.depends('purchase_price', 'taxes_ids.percentage', 'taxes_ids.apply_on_total',
                 'extra_discount_percentage', 'posting_snapshot')
    def _compute_unit_taxes_value(self):
        draft = self.filtered(lambda source: not source._get_posting_snapshot())
        super(AbProductSource, draft)._compute_unit_taxes_value()
        for source in self:
            snapshot = source._get_posting_snapshot()
            if snapshot:
                source.unit_taxes_value = snapshot['unit_tax']

    def _get_conversion_basis(self):
        self.ensure_one()
        snapshot = self._get_posting_snapshot()
        if snapshot:
            return snapshot['conversion']
        return super()._get_conversion_basis()

    def _lock_inventory_inputs(self):
        products = self.mapped('product_id').sorted('id')
        products.lock_for_update(allow_referencing=True)
        products.invalidate_recordset()
        if products:
            products.sudo().write({'write_date': fields.Datetime.now()})
        units = (self.mapped('uom_id') | products.mapped('unit_m_id')
                 | products.mapped('unit_s_id')).sorted('id')
        units.lock_for_update(allow_referencing=True)
        units.invalidate_recordset()
        if units:
            units.sudo().write({'write_date': fields.Datetime.now()})
        stock_units = products.mapped('stock_uom_id').sorted('id')
        stock_units.lock_for_update(allow_referencing=True)
        stock_units.invalidate_recordset()
        if stock_units:
            stock_units.sudo().write({'write_date': fields.Datetime.now()})
        policies = self.mapped('tax_policy_id').sorted('id')
        policies.lock_for_update(allow_referencing=True)
        policies.invalidate_recordset()
        if policies:
            policies.sudo().write({'write_date': fields.Datetime.now()})
        taxes = self.mapped('taxes_ids').sorted('id')
        taxes.lock_for_update(allow_referencing=True)
        taxes.invalidate_recordset()
        if taxes:
            taxes.sudo().write({'write_date': fields.Datetime.now()})
        self.invalidate_recordset()

    def _freeze_for_inventory(self, movement):
        self.ensure_one()
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        if self._get_posting_snapshot():
            return
        if self.env['ab_inventory'].sudo().search_count([
            ('source_id', '=', self.id), ('status', '=', 'saved'),
        ]):
            raise ValidationError(_(
                'This source has saved stock without a posting snapshot. Review its historical values before posting again.'
            ))
        if not self.exp_date and not self.no_expiry:
            raise ValidationError(_('Enter an expiry date or select No Expiry before posting stock.'))
        self._check_posting_identity()
        self._ensure_physical_lot()
        self._check_expiry_choice()
        self.convert_cost('small')
        snapshot = {
            'source_identity': self.source_identity,
            'lot_id': self.lot_id.id,
            'tax_calculation': self._get_purchase_tax_values(),
            'database': self.env.cr.dbname,
            'store_code': movement.store_id.code,
            'document_model': movement.model_ref,
            'document_id': movement.res_id,
            'quantity': self.qty, 'bonus': self.bonus,
            'selling_price': self.price, 'purchase_price': self.purchase_price,
            'discount_percentage': self.extra_discount_percentage,
            'expiry': str(self.exp_date) if self.exp_date else False,
            'no_expiry': self.no_expiry,
            'unit_cost': self.unit_cost,
            'unit_tax': self.unit_taxes_value,
            'conversion': self._get_conversion_basis(),
            'taxes': [{'id': tax.id, 'name': tax.name, 'percentage': tax.percentage,
                       'apply_on_total': tax.apply_on_total} for tax in self.taxes_ids.sorted('id')],
            'posted_by': self.env.uid,
            'posted_at': str(fields.Datetime.now()),
        }
        super(AbProductSource, self.sudo()).write({'posting_snapshot': snapshot})
