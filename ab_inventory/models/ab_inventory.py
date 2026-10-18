import math

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .stock_state import LOCATIONS


class AbInventory(models.Model):
    _name = 'ab_inventory'
    _description = 'Inventory Movement'
    _rec_name = 'id'
    _order = 'posting_sequence desc, id desc'

    company_id = fields.Many2one('res.company', related='store_id.company_id', store=True, index=True)
    store_id = fields.Many2one('ab_store', string='Store', required=True, index=True, ondelete='restrict')
    source_id = fields.Many2one('ab_product_source', string='Batch / Source', index=True, ondelete='restrict')
    product_id = fields.Many2one('ab_product', string='Item', required=True, index=True, ondelete='restrict')
    location = fields.Selection(LOCATIONS, default='saleable', required=True, index=True)
    qty = fields.Float(string='Quantity Change', required=True, digits=(20, 6))
    incoming_qty = fields.Float(string='Incoming', compute='_compute_direction_quantities', digits=(20, 6))
    outgoing_qty = fields.Float(string='Outgoing', compute='_compute_direction_quantities', digits=(20, 6))
    ending_balance = fields.Float(string='Ending Balance', readonly=True, copy=False, digits=(20, 6))
    closing_balance = fields.Float(string='Closing Balance', related='ending_balance', store=True, digits=(20, 6))
    balance_id = fields.Many2one('ab_inventory_balance', readonly=True, copy=False, index=True, ondelete='restrict')
    posting_sequence = fields.Integer(readonly=True, copy=False, index=True)
    unit_cost = fields.Float(readonly=True, copy=False, digits=(20, 6))
    valuation = fields.Float(readonly=True, copy=False, digits=(20, 6))
    conversion_snapshot = fields.Json(readonly=True, copy=False)
    operation_key = fields.Char(index=True, copy=False)
    business_date = fields.Date(default=fields.Date.context_today, required=True)
    status = fields.Selection([('pending', 'Pending'), ('saved', 'Saved')], string='Status', default='pending', required=True, readonly=True, copy=False, index=True)
    saved_at = fields.Datetime(string='Saved At', readonly=True, copy=False, index=True)
    model_ref = fields.Selection([('manual', 'Manual'), ('opening', 'Opening Balance'), ('native', 'Native Sale'), ('native_return', 'Native Return'), ('shortage', 'Shortage Settlement'), ('location', 'Location Transfer')], default='manual', required=True, string='Source Type', index=True)
    res_id = fields.Integer(string='Source Record ID', readonly=True, copy=False, index=True)
    document_model = fields.Char(readonly=True, copy=False)

    _operation_unique = models.Constraint('UNIQUE(company_id,store_id,operation_key)', 'Inventory operation keys must be unique per store.')
    _sequence_unique = models.UniqueIndex("(store_id,posting_sequence) WHERE status = 'saved'")
    _latest_saved_balance_idx = models.Index('(store_id, source_id, saved_at DESC, id DESC) WHERE status = \'saved\'')

    @api.depends('store_id', 'product_id')
    def _compute_display_name(self):
        for rec in self:
            label = (_('Movement #%s') % rec.id) if isinstance(rec.id, int) else _('Inventory Movement')
            rec.display_name = ' / '.join(filter(None, [label, rec.product_id.display_name, rec.store_id.display_name]))

    @api.depends('qty')
    def _compute_direction_quantities(self):
        for rec in self:
            rec.incoming_qty = max(rec.qty, 0)
            rec.outgoing_qty = max(-rec.qty, 0)

    @api.model
    def _validate_quantity_value(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not value:
            raise ValidationError(_('Quantity change must be finite and non-zero in stock units.'))

    @api.constrains('qty', 'product_id', 'source_id', 'store_id')
    def _check_quantity(self):
        for rec in self:
            self._validate_quantity_value(rec.qty)
            rec.product_id._validate_stock_quantity(abs(rec.qty))
            if rec.source_id and (rec.product_id != rec.source_id.product_id or (rec.source_id.store_id and rec.source_id.store_id != rec.store_id) or rec.source_id.company_id != rec.company_id):
                raise ValidationError(_('The stock source must match the movement product, store and company.'))

    @api.model_create_multi
    def create(self, vals_list):
        process = self.env['ab_inventory_process']
        process._require_manager()
        clean = []
        for vals in vals_list:
            vals = dict(vals)
            self._validate_quantity_value(vals.get('qty'))
            if any(key in vals for key in ('incoming_qty', 'outgoing_qty', 'ending_balance', 'closing_balance', 'posting_sequence', 'balance_id', 'unit_cost', 'valuation', 'conversion_snapshot', 'saved_at', 'operation_key', 'document_model')) or vals.get('status', 'pending') != 'pending':
                raise ValidationError(_('Post movements through the inventory business actions.'))
            store = process._check_store(vals.get('store_id'))
            source = self.env['ab_product_source'].browse(vals.get('source_id')).exists()
            if not source:
                raise ValidationError(_('Manual stock movements require an existing source.'))
            source.check_access('read')
            vals['product_id'] = source.product_id.id
            if vals.get('res_id') or vals.get('model_ref', 'manual') != 'manual':
                raise ValidationError(_('Linked movements must be created through their business document.'))
            clean.append(vals)
        records = super().create(clean)
        for record in records:
            if not record.source_id.origin_model:
                record.source_id._bind_origin(record.store_id, 'ab_inventory', record.id, 'adjustment')
        return records

    def write(self, vals):
        self.check_access('write')
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        if any(rec.status == 'saved' for rec in self):
            raise ValidationError(_('Saved movements cannot be edited.'))
        process = self.env['ab_inventory_process']
        process._require_manager()
        for store in self.mapped('store_id'):
            process._check_store(store.id)
        if vals == {'status': 'saved'}:
            if any(self.mapped('res_id')):
                raise ValidationError(_('Linked movements must be saved through their business document.'))
            return process._post(self)
        allowed = {'qty', 'source_id', 'store_id', 'location', 'business_date'}
        if set(vals) - allowed or any(self.mapped('res_id')):
            raise ValidationError(_('Use the originating business document to change this movement.'))
        if 'store_id' in vals:
            process._check_store(vals['store_id'])
        if 'source_id' in vals:
            source = self.env['ab_product_source'].browse(vals['source_id'])
            source.check_access('read')
            vals = dict(vals, product_id=source.product_id.id)
        return super().write(vals)

    def unlink(self):
        raise ValidationError(_('Inventory movements cannot be deleted.'))

    def action_post(self):
        return self.write({'status': 'saved'})
