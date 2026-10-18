import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class NativeReturn(models.Model):
    _inherit = 'ab_sales_return_header'

    native_origin_id = fields.Many2one('ab_sales_header', string='Original Native Invoice',
                                       readonly=True, copy=False, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='store_id.company_id', store=True)
    native_posted = fields.Boolean(string='Native Stock Returned', readonly=True, copy=False)
    native_refund = fields.Float(string='Native Refund Amount', readonly=True, copy=False, digits=(18, 4))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if {'native_posted', 'native_refund'} & vals.keys():
                raise AccessError(_('Native return values are maintained by posting.'))
            store_id = vals.get('store_id') or self._default_sales_store_id()
            if vals.get('native_origin_id') or self.env['ab_sales_backend']._is_native(store_id):
                store = self.env['ab_sales_backend']._check_store(store_id)
                store._lock_stock_scope()
                self.env['ab_sales_backend']._check_employee_session(store, 'allow_return_screen')
                origin = self.env['ab_sales_header'].browse(vals.get('native_origin_id')).exists()
                origin.check_access('read')
                if not origin or not origin.native_posted or origin.status != 'saved' or origin.store_id.id != store_id:
                    raise ValidationError(_('A native return requires its settled original invoice and allocations. Use historical review for missing originals.'))
                if vals.get('status', 'prepending') != 'prepending':
                    raise AccessError(_('Native returns must start as drafts.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'native_origin_id', 'native_posted', 'native_refund'} & vals.keys():
            raise AccessError(_('Native return values are maintained by posting.'))
        for rec in self.filtered('native_origin_id'):
            rec.lock_for_update(allow_referencing=True)
            rec.invalidate_recordset()
            self.env['ab_sales_backend']._check_store(rec.store_id.id)
            if rec.status != 'prepending' or {'store_id', 'origin_header_id', 'status'} & vals.keys():
                raise AccessError(_('Submitted native returns cannot be changed.'))
        return super().write(vals)

    def unlink(self):
        if self.filtered('native_origin_id'):
            raise AccessError(_('Native returns cannot be deleted.'))
        return super().unlink()

    def get_connection(self):
        if self.filtered('native_origin_id') or any(self.env['ab_sales_backend']._is_native(r.store_id.id) for r in self):
            raise AccessError(_('Native returns cannot connect to E-Plus.'))
        return super().get_connection()

    def _return_router_get_source_header(self):
        self.ensure_one()
        return self.native_origin_id or super()._return_router_get_source_header()

    def _promo_return_get_source_header(self):
        self.ensure_one()
        if self.native_origin_id:
            return self.native_origin_id
        parent = super()
        return parent._promo_return_get_source_header() if hasattr(parent, '_promo_return_get_source_header') else self.env['ab_sales_header']

    def _contract_return_get_source_header(self):
        self.ensure_one()
        if self.native_origin_id:
            return self.native_origin_id
        parent = super()
        return parent._contract_return_get_source_header() if hasattr(parent, '_contract_return_get_source_header') else self.env['ab_sales_header']

    def action_load_lines(self):
        self.ensure_one()
        if not self.native_origin_id:
            if self.env['ab_sales_backend']._is_native(self.store_id.id):
                raise ValidationError(_('Historical returns require a reviewed original transaction import.'))
            return super().action_load_lines()
        self.check_access('write')
        store = self.env['ab_sales_backend']._check_store(self.store_id.id)
        self.env['ab_sales_backend']._check_employee_session(store, 'allow_return_screen')
        if self.status != 'prepending':
            raise ValidationError(_('Only draft native returns can reload lines.'))
        self._validate_invoice_return_window(self.native_origin_id.id, self.native_origin_id.create_date)
        self.line_ids.unlink()
        values = []
        for line in self.native_origin_id.line_ids:
            returned = self.env['ab_sales_return_line'].search([
                ('native_origin_line_id', '=', line.id), ('header_id.native_posted', '=', True)])
            remaining = line.native_stock_qty - sum(returned.mapped('native_stock_qty'))
            factor = line.native_unit_factor
            if remaining <= 0:
                continue
            values.append({
                'header_id': self.id, 'native_origin_line_id': line.id, 'sale_line_id': line.id,
                'product_id': line.product_id.id, 'uom_id': line.uom_id.id, 'qty_str': '0',
                'qty_sold': line.qty, 'qty_sold_source': line.qty,
                'max_returnable_qty': remaining / factor, 'max_returnable_source': remaining / factor,
                'sell_price': line.sell_price, 'source_uom_factor': line.uom_id.factor,
                'item_unit1_unit3': line.product_id.uom_id.factor,
            })
        self.env['ab_sales_return_line'].create(values)
        super(NativeReturn, self).write({'total_sales_net': self.native_origin_id.native_totals['total_bill_net']})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new'}

    def _native_refund_amount(self):
        self.ensure_one()
        sale = self.native_origin_id
        totals = sale.native_totals
        mode, unused = self._return_router_mode(sale)
        if mode == 'contract' and hasattr(self, '_contract_return_reprice_values'):
            amount = self._contract_return_reprice_values()['refund_net']
        elif mode == 'promo' and hasattr(self, '_promo_return_reprice_values'):
            amount = self._promo_return_reprice_values()['refund_total']
        else:
            gross = float(totals['total_bill'])
            returned_gross = sum(line.qty * line.sell_price for line in self.line_ids)
            amount = returned_gross * totals['total_bill_net'] / gross if gross else 0.0
        previous = self.env['ab_sales_return_header'].search([
            ('native_origin_id', '=', sale.id), ('native_posted', '=', True), ('id', '!=', self.id)])
        available = max(0.0, float(totals['total_bill_net']) - sum(previous.mapped('native_refund')))
        if not math.isfinite(amount) or amount < 0:
            raise ValidationError(_('The native refund amount is invalid.'))
        return round(min(amount, available), 4)

    def action_set_pending(self):
        native = self.filtered('native_origin_id')
        for rec in native:
            rec.check_access('write')
            store = self.env['ab_sales_backend']._check_store(rec.store_id.id)
            self.env['ab_sales_backend']._check_employee_session(store, 'allow_return')
            rec.lock_for_update(allow_referencing=True)
            rec.invalidate_recordset()
            if rec.status == 'pending':
                continue
            if rec.status != 'prepending' or not any(line.qty > 0 for line in rec.line_ids):
                raise ValidationError(_('Select positive quantities on a draft native return.'))
            rec._validate_invoice_return_window(rec.native_origin_id.id, rec.native_origin_id.create_date)
            for line in rec.line_ids:
                if line.qty < 0 or not math.isfinite(line.qty):
                    raise ValidationError(_('Native return quantities must be nonnegative.'))
            super(NativeReturn, rec).write({'status': 'pending'})
        if self - native:
            super(NativeReturn, self - native).action_set_pending()
        return True

    def _post_native_return(self):
        self.ensure_one()
        self.env['ab_sales_backend']._check_store(self.store_id.id, cashier=True)
        self.check_access('read')
        origin = self.native_origin_id
        origin.lock_for_update(allow_referencing=True)
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        if self.native_posted:
            return True
        if self.status != 'pending' or not origin or origin.store_id != self.store_id:
            raise ValidationError(_('Only pending native returns with an original invoice can be posted.'))
        with self.env.cr.savepoint():
            for line in self.line_ids:
                original = line.native_origin_line_id
                previous = self.env['ab_sales_return_line'].search([
                    ('native_origin_line_id', '=', original.id), ('header_id.native_posted', '=', True)])
                remaining = original.native_stock_qty - sum(previous.mapped('native_stock_qty'))
                super(NativeReturnLine, line.sudo()).write({
                    'max_returnable_qty': remaining / (original.native_unit_factor * line.uom_id.factor / original.uom_id.factor),
                    'max_returnable_source': remaining / original.native_unit_factor,
                })
            for line in self.line_ids.filtered(lambda item: item.qty > 0):
                original = line.native_origin_line_id
                if original.header_id != origin or line.product_id != original.product_id or line.uom_id.category_id != original.uom_id.category_id:
                    raise ValidationError(_('Return lines must retain the original product and unit.'))
                qty = line._native_stock_quantity()
                if original.header_id.native_totals['line_context'][str(original.id)]['is_service']:
                    previous = self.env['ab_sales_return_line'].search([
                        ('native_origin_line_id', '=', original.id), ('header_id.native_posted', '=', True)])
                    if qty + sum(previous.mapped('native_stock_qty')) > original.native_stock_qty:
                        raise ValidationError(_('The return exceeds the original sold quantity.'))
                else:
                    self.env['ab_inventory_process'].return_allocations(
                        self.store_id.id, 'return:%s:line:%s' % (self.id, line.id), original.native_operation_key,
                        qty, line._name, line.id)
                super(NativeReturnLine, line.sudo()).write({'native_stock_qty': qty})
            super(NativeReturn, self.sudo()).write({'native_posted': True, 'native_refund': self._native_refund_amount()})
        return True

    def action_push_to_eplus_return(self):
        self.ensure_one()
        if not self.native_origin_id:
            return super().action_push_to_eplus_return()
        self.env['ab_sales_backend']._check_store(self.store_id.id, cashier=True)
        with self.env.cr.savepoint():
            self.env['ab_sales_native_payment']._settle(self.native_origin_id, self)
        return True

    def _native_settled(self):
        self.ensure_one()
        super(NativeReturn, self.sudo()).write({'status': 'saved'})


class NativeReturnLine(models.Model):
    _inherit = 'ab_sales_return_line'

    native_origin_line_id = fields.Many2one('ab_sales_line', string='Original Native Sale Line',
                                           readonly=True, copy=False, ondelete='restrict', index=True)
    native_stock_qty = fields.Float(string='Returned Stock Quantity', readonly=True, copy=False, digits=(18, 6))
    _native_original_unique = models.Constraint('UNIQUE(header_id, native_origin_line_id)',
        'Each native original line can occur only once per return.')

    def _native_stock_quantity(self):
        self.ensure_one()
        original = self.native_origin_line_id
        qty = self.qty * original.native_unit_factor * self.uom_id.factor / original.uom_id.factor
        return qty if original.header_id.native_totals['line_context'][str(original.id)]['is_service'] else original.product_id._validate_stock_quantity(qty)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'native_stock_qty' in vals:
                raise AccessError(_('Returned stock quantities are maintained by posting.'))
            header = self.env['ab_sales_return_header'].browse(vals.get('header_id')).exists()
            if header.native_origin_id:
                self.env['ab_sales_backend']._check_store(header.store_id.id)
                header.check_access('write')
                if header.status != 'prepending':
                    raise AccessError(_('Submitted native return lines cannot be changed.'))
                original = self.env['ab_sales_line'].browse(vals.get('native_origin_line_id')).exists()
                if not original or original.header_id != header.native_origin_id:
                    raise ValidationError(_('The original sale line must belong to this return invoice.'))
                previous = self.search([('native_origin_line_id', '=', original.id), ('header_id.native_posted', '=', True)])
                remaining = original.native_stock_qty - sum(previous.mapped('native_stock_qty'))
                vals.update(product_id=original.product_id.id, uom_id=original.uom_id.id,
                    sell_price=original.sell_price, source_uom_factor=original.uom_id.factor,
                    qty_sold=original.qty, qty_sold_source=original.qty,
                    max_returnable_qty=remaining / original.native_unit_factor,
                    max_returnable_source=remaining / original.native_unit_factor)
            elif vals.get('native_origin_line_id'):
                raise AccessError(_('A native original line requires a native return header.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'native_origin_line_id', 'native_stock_qty'} & vals.keys():
            raise AccessError(_('Native original allocations cannot be changed.'))
        for line in self.filtered('native_origin_line_id'):
            line.header_id.lock_for_update(allow_referencing=True)
            line.header_id.invalidate_recordset()
            self.env['ab_sales_backend']._check_store(line.header_id.store_id.id)
            if line.header_id.status != 'prepending':
                raise AccessError(_('Submitted native return lines and original economics cannot be changed.'))
        native = self.filtered('native_origin_line_id')
        if native:
            allowed = {'qty_str'}
            if 'uom_id' in vals:
                allowed |= {'uom_id', 'qty_sold', 'max_returnable_qty', 'sell_price', 'cost'}
            if vals.keys() - allowed:
                raise AccessError(_('Only the quantity and compatible display unit can change on a native return.'))
            for line in native:
                values = {'qty_str': vals.get('qty_str', line.qty_str)}
                if 'uom_id' in vals:
                    unit = self.env['ab_product_uom'].browse(vals['uom_id']).exists()
                    original = line.native_origin_line_id
                    if not unit or unit.category_id != original.uom_id.category_id:
                        raise ValidationError(_('Select a unit from the original product category.'))
                    ratio = unit.factor / original.uom_id.factor
                    values.update(uom_id=unit.id, sell_price=original.sell_price * ratio,
                        qty_sold=original.qty / ratio,
                        max_returnable_qty=line.max_returnable_source / ratio)
                super(NativeReturnLine, line).write(values)
            if self - native:
                super(NativeReturnLine, self - native).write(vals)
            return True
        return super().write(vals)

    def unlink(self):
        headers = self.filtered('native_origin_line_id').mapped('header_id')
        headers.lock_for_update(allow_referencing=True)
        headers.invalidate_recordset()
        if self.filtered(lambda line: line.native_origin_line_id and line.header_id.status != 'prepending'):
            raise AccessError(_('Submitted native return lines cannot be deleted.'))
        return super().unlink()


class NativeReturnUI(models.TransientModel):
    _inherit = 'ab_sales_return_ui_api'

    @api.model
    def _action_payload(self, return_header_id):
        result = super()._action_payload(return_header_id)
        if self.env['ab_sales_return_header'].browse(return_header_id).native_origin_id:
            result['tag'] = 'ab_sales_inventory.return_ui'
        return result

    @api.model
    def open_from_sale_header(self, sale_header_id, **kwargs):
        sale = self.env['ab_sales_header'].browse(int(sale_header_id)).exists()
        sale.check_access('read')
        if sale.native_backend:
            action = sale.with_context(ab_return_session_token=kwargs.get('session_token') or self.env.context.get('ab_return_session_token')).action_open_sales_return()
            return self._action_payload(action['res_id'])
        return super().open_from_sale_header(sale_header_id, **kwargs)
