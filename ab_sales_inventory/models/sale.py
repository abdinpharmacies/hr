import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class NativeSale(models.Model):
    _inherit = 'ab_sales_header'

    native_backend = fields.Boolean(string='Native Inventory', readonly=True, copy=False, index=True)
    native_submitted = fields.Boolean(string='Submitted to Cashier', readonly=True, copy=False)
    native_posted = fields.Boolean(string='Native Stock Posted', readonly=True, copy=False)
    native_totals = fields.Json(string='Native Totals Snapshot', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            if {'native_backend', 'native_submitted', 'native_posted', 'native_totals'} & vals.keys():
                raise AccessError(_('Native posting fields are managed by the sales workflow.'))
            vals = dict(vals)
            store_id = vals.get('store_id') or self._default_sales_store_id()
            self.env['ab_store'].browse(store_id).lock_for_update(allow_referencing=True)
            if self.env['ab_sales_backend']._is_native(store_id):
                store = self.env['ab_sales_backend']._check_store(store_id)
                store._lock_stock_scope()
                if vals.get('status', 'prepending') != 'prepending' or vals.get('eplus_serial'):
                    raise AccessError(_('Native sales must start as unposted documents.'))
                vals.update(native_backend=True, company_id=store.company_id.id)
                pos = self.env['ab_sales_pos_api']
                if hasattr(pos, '_validate_pos_hr_payload'):
                    session = pos._validate_pos_hr_payload({'header': vals,
                        'pos_hr_session_token': self.env.context.get('native_pos_hr_token')})
                    self.env['ab_sales_backend']._check_employee_session(store, 'allow_pos_screen')
                    vals.update(pos_hr_employee_id=session.employee_id.id,
                        pos_hr_profile_id=session._get_pos_profile().id,
                        pos_hr_role_id=session.role_id.id, pos_hr_shift_id=session.shift_id.id,
                        pos_hr_session_id=session.id, pos_hr_service_user_id=session.service_user_id.id,
                        pos_hr_device_uid=session.device_uid or False,
                        pos_hr_device_name=session.device_name or False,
                        pos_hr_device_ip=session.device_ip or False)
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if {'native_backend', 'native_submitted', 'native_posted', 'native_totals'} & vals.keys():
            raise AccessError(_('Native posting fields are managed by the sales workflow.'))
        for rec in self.filtered('native_backend'):
            self.env['ab_sales_backend']._check_store(rec.store_id.id)
            rec.lock_for_update(allow_referencing=True)
            rec.invalidate_recordset()
            if rec.native_submitted and all(
                    (rec[key].id if rec._fields[key].type == 'many2one' else rec[key]) == value
                    for key, value in vals.items() if key in rec._fields):
                continue
            if rec.native_submitted or {'store_id', 'company_id', 'eplus_serial', 'status'} & vals.keys():
                raise AccessError(_('Posted native sales are immutable; use a return.'))
        if self and all(rec.native_submitted and all(
                (rec[key].id if rec._fields[key].type == 'many2one' else rec[key]) == value
                for key, value in vals.items() if key in rec._fields) for rec in self):
            self.check_access('read')
            return True
        return super().write(vals)

    def unlink(self):
        if self.filtered('native_backend'):
            raise AccessError(_('Native sales must be archived instead of deleted.'))
        return super().unlink()

    def get_connection(self):
        if self.filtered('native_backend') or any(self.env['ab_sales_backend']._is_native(rec.store_id.id) for rec in self):
            raise AccessError(_('Native sales cannot connect to E-Plus.'))
        return super().get_connection()

    @api.onchange('store_id')
    def _onchange_store_id(self):
        native = self.filtered(lambda r: r.native_backend or self.env['ab_sales_backend']._is_native(r.store_id.id))
        for rec in native:
            rec.line_ids._recompute_inventory_json()
        return super(NativeSale, self - native)._onchange_store_id()

    def _unavailable_lines_missing_reason(self):
        lines = super()._unavailable_lines_missing_reason()
        return lines.filtered(lambda line: not line.product_id.is_service) if self.native_backend else lines

    def action_push_to_eplus(self):
        self.ensure_one()
        if not self.native_backend:
            if self.env['ab_sales_backend']._is_native(self.store_id.id):
                raise ValidationError(_('Legacy invoices require their original backend; use the historical review process.'))
            return super().action_push_to_eplus()
        self.check_access('read')
        store = self.env['ab_sales_backend']._check_store(self.store_id.id)
        self.env['ab_sales_backend']._check_employee_session(store, 'allow_pos_screen')
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        if self.native_submitted:
            return True
        self.check_access('write')
        if self.status != 'prepending' or not self.line_ids:
            raise ValidationError(_('A native sale requires draft lines before posting.'))
        if self.company_id != store.company_id:
            raise AccessError(_('The sale and store must belong to the same company.'))
        units = self.line_ids.mapped('uom_id')
        units.lock_for_update(allow_referencing=True)
        units.sudo().write({'write_date': fields.Datetime.now()})
        totals = self._compute_header_numbers(cur=None)
        if any(not math.isfinite(float(value)) or float(value) < 0 for key, value in totals.items()
               if key in ('total_bill', 'total_bill_after_disc', 'total_bill_net')):
            raise ValidationError(_('Native sale totals must be finite and nonnegative.'))
        totals['line_context'] = {}
        for line in self.line_ids:
            if not line.product_id or line.qty <= 0 or not math.isfinite(line.qty) or not math.isfinite(line.sell_price) or line.sell_price < 0:
                raise ValidationError(_('Native sale lines require a product, positive quantity and valid price.'))
            service = bool(line.product_id.is_service)
            qty = line.qty if service else line.product_id._to_stock_quantity(line.qty, line.uom_id)
            totals['line_context'][str(line.id)] = {
                'is_service': service, 'uom_factor': line.uom_id.factor,
                'stock_qty': qty, 'stock_unit_id': line.product_id.unit_s_id.id,
            }
        super(NativeSale, self.sudo()._submission_records()).write({
            'native_submitted': True, 'native_totals': totals, 'status': 'pending',
            'push_state': 'success', **self._get_bill_customer_snapshot_vals(),
        })
        return True

    def _post_native_stock(self):
        self.ensure_one()
        store = self.env['ab_sales_backend']._check_store(self.store_id.id, cashier=True)
        self.env['ab_sales_backend']._check_employee_session(store, 'allow_cashier_screen')
        self.check_access('read')
        if self.native_posted:
            return
        if not self.native_backend or not self.native_submitted or self.status != 'pending':
            raise ValidationError(_('Only submitted native bills can post stock at the cashier.'))
        store._lock_stock_scope()
        with self.env.cr.savepoint():
            for line in self.line_ids.sorted('id'):
                snapshot = self.native_totals['line_context'][str(line.id)]
                allocations = [] if snapshot['is_service'] else self.env['ab_sales_stock_allocation']._post_sale(line)
                qty = snapshot['stock_qty']
                super(NativeSaleLine, line.sudo().with_context(self._submission_records().env.context)).write({
                    'native_stock_qty': qty, 'native_unit_factor': qty / line.qty,
                    'native_operation_key': 'sale:%s:line:%s' % (self.id, line.id),
                    'native_allocations': allocations,
                })
            super(NativeSale, self.sudo()._submission_records()).write({'native_posted': True})

    def _native_settled(self):
        self.ensure_one()
        super(NativeSale, self.sudo()._submission_records()).write({'status': 'saved'})

    def action_open_sales_return(self):
        self.ensure_one()
        if not self.native_backend:
            return super().action_open_sales_return()
        self.check_access('read')
        store = self.env['ab_sales_backend']._check_store(self.store_id.id)
        self.env['ab_sales_backend']._check_employee_session(store, 'allow_return_screen')
        if self.status != 'saved':
            raise ValidationError(_('Settle the native invoice before creating a return.'))
        header = self.env['ab_sales_return_header'].search([
            ('native_origin_id', '=', self.id), ('status', '=', 'prepending')], limit=1)
        if not header:
            header = self.env['ab_sales_return_header'].create({
                'store_id': self.store_id.id, 'native_origin_id': self.id, 'origin_header_id': self.id,
            })
        header.action_load_lines()
        return {'type': 'ir.actions.act_window', 'res_model': 'ab_sales_return_header',
                'view_mode': 'form', 'res_id': header.id, 'target': 'new'}

    def _compute_notice_header_ids(self):
        native = self.filtered('native_backend')
        for rec in native:
            rec.notice_header_ids = self.env['ab_sales_return_header'].search([('native_origin_id', '=', rec.id)])
        super(NativeSale, self - native)._compute_notice_header_ids()


class NativeSaleLine(models.Model):
    _inherit = 'ab_sales_line'

    native_stock_qty = fields.Float(string='Posted Stock Quantity', readonly=True, copy=False, digits=(18, 6))
    native_unit_factor = fields.Float(string='Posted Unit Factor', readonly=True, copy=False, digits=(18, 8))
    native_operation_key = fields.Char(string='Stock Operation Key', readonly=True, copy=False, index=True)
    native_allocations = fields.Json(string='Posted Stock Allocations', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(key.startswith('native_') for key in vals):
                raise AccessError(_('Stock allocations are managed by native posting.'))
            header = self.env['ab_sales_header'].browse(vals.get('header_id')).exists()
            if header.native_backend:
                header.check_access('write')
                header.lock_for_update(allow_referencing=True)
                header.invalidate_recordset()
                self.env['ab_sales_backend']._check_store(header.store_id.id)
                if header.native_submitted:
                    raise AccessError(_('Posted native sale lines cannot be changed.'))
                product = self.env['ab_product'].browse(vals.get('product_id')).exists()
                vals['inventory_json'] = {'data': self.env['ab_sales_pos_api']._native_inventory_rows(header.store_id.id, product)}
        return super().create(vals_list)

    def write(self, vals):
        if any(key.startswith('native_') for key in vals):
            raise AccessError(_('Stock allocations are managed by native posting.'))
        headers = self.mapped('header_id')
        if vals.get('header_id'):
            headers |= self.env['ab_sales_header'].browse(vals['header_id'])
        for header in headers.filtered('native_backend'):
            header.lock_for_update(allow_referencing=True)
            header.invalidate_recordset()
            self.env['ab_sales_backend']._check_store(header.store_id.id)
            if header.native_submitted:
                raise AccessError(_('Posted native sale lines cannot be changed.'))
        native = self.filtered(lambda line: line.header_id.native_backend)
        if native and {'product_id', 'sell_price', 'inventory_json'} & vals.keys():
            for line in self:
                values = dict(vals)
                if line.header_id.native_backend:
                    product = self.env['ab_product'].browse(vals.get('product_id') or line.product_id.id)
                    values['inventory_json'] = {'data': self.env['ab_sales_pos_api']._native_inventory_rows(line.header_id.store_id.id, product)}
                super(NativeSaleLine, line).write(values)
            return True
        return super().write(vals)

    def unlink(self):
        headers = self.mapped('header_id').filtered('native_backend')
        headers.lock_for_update(allow_referencing=True)
        headers.invalidate_recordset()
        if self.filtered(lambda line: line.header_id.native_submitted):
            raise AccessError(_('Posted native sale lines cannot be deleted.'))
        return super().unlink()

    def _recompute_inventory_json(self, crx=None):
        native = self.filtered(lambda line: line.header_id.native_backend or
                               self.env['ab_sales_backend']._is_native(line.header_id.store_id.id))
        for line in native:
            if line.header_id.native_submitted:
                continue
            line.inventory_json = {'data': self.env['ab_sales_pos_api']._native_inventory_rows(
                line.header_id.store_id.id, line.product_id)}
        return super(NativeSaleLine, self - native)._recompute_inventory_json(crx=crx) if self - native else None


class NativeSalesUnit(models.Model):
    _inherit = 'ab_product_uom'

    def write(self, vals):
        if {'factor', 'category_id'} & vals.keys():
            self.check_access('write')
            self.lock_for_update(allow_referencing=True)
            if self.env['ab_sales_line'].sudo().search_count([
                    ('header_id.native_submitted', '=', True),
                    ('uom_id.category_id', 'in', self.mapped('category_id').ids)]):
                raise ValidationError(_('Units used by posted native sales cannot change their factors or categories.'))
        return super().write(vals)
