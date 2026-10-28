import hashlib
import json
import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class NativeSale(models.Model):
    _inherit = 'ab_sales_header'

    status = fields.Selection(selection_add=[('cancelled', 'Cancelled')], ondelete={'cancelled': 'set default'})
    native_backend = fields.Boolean(string='Native Inventory', readonly=True, copy=False, index=True)
    native_submitted = fields.Boolean(string='Submitted to Cashier', readonly=True, copy=False)
    native_posted = fields.Boolean(string='Native Stock Posted', readonly=True, copy=False)
    native_totals = fields.Json(string='Native Totals Snapshot', readonly=True, copy=False)
    native_approval_version = fields.Integer(string='Native Approval Version', readonly=True, copy=False)
    native_request_fingerprint = fields.Char(string='Native Request Fingerprint', readonly=True, copy=False, index=True)
    native_content_fingerprint = fields.Char(string='Native Content Fingerprint', readonly=True, copy=False)
    native_cancel_reason = fields.Text(string='Cancellation Reason', readonly=True, copy=False)
    native_cancelled_by_id = fields.Many2one('res.users', string='Cancelled By', readonly=True, copy=False)
    native_cancelled_at = fields.Datetime(string='Cancelled At', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        managed = {
            'native_backend', 'native_submitted', 'native_posted', 'native_totals',
            'native_approval_version', 'native_request_fingerprint', 'native_content_fingerprint', 'native_cancel_reason',
            'native_cancelled_by_id', 'native_cancelled_at',
        }
        for vals in vals_list:
            if managed & vals.keys():
                raise AccessError(_('Native posting fields are managed by the sales workflow.'))
            vals = dict(vals)
            store_id = vals.get('store_id') or self._default_sales_store_id()
            if self.env['ab_sales_backend']._is_native(store_id):
                store = self.env['ab_sales_backend']._check_store(store_id)
                store.lock_for_update(allow_referencing=True)
                store.with_context(ab_sales_branch_scope=True)._lock_stock_scope()
                if vals.get('status', 'prepending') != 'prepending' or vals.get('eplus_serial'):
                    raise AccessError(_('Native sales must start as unposted documents.'))
                vals['native_backend'] = True
                pos = self.env['ab_sales_pos_api']
                if hasattr(pos, '_validate_pos_hr_payload'):
                    session = pos._validate_pos_hr_payload({
                        'header': vals,
                        'pos_hr_session_token': self.env.context.get('native_pos_hr_token'),
                    })
                    self.env['ab_sales_backend']._check_employee_session(store, 'allow_pos_screen')
                    vals.update(
                        pos_hr_employee_id=session.employee_id.id,
                        pos_hr_profile_id=session._get_pos_profile().id,
                        pos_hr_role_id=session.role_id.id,
                        pos_hr_shift_id=session.shift_id.id,
                        pos_hr_session_id=session.id,
                        pos_hr_service_user_id=session.service_user_id.id,
                        pos_hr_device_uid=session.device_uid or False,
                        pos_hr_device_name=session.device_name or False,
                        pos_hr_device_ip=session.device_ip or False,
                    )
            else:
                self.env['ab_store'].browse(store_id).lock_for_update(allow_referencing=True)
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        managed = {
            'native_backend', 'native_submitted', 'native_posted', 'native_totals',
            'native_approval_version', 'native_request_fingerprint', 'native_content_fingerprint', 'native_cancel_reason',
            'native_cancelled_by_id', 'native_cancelled_at',
        }
        if managed & vals.keys():
            raise AccessError(_('Native posting fields are managed by the sales workflow.'))
        for rec in self.filtered('native_backend'):
            self.env['ab_sales_backend']._check_store(rec.store_id.id)
            rec.lock_for_update(allow_referencing=True)
            rec.invalidate_recordset()
            if rec.native_submitted and all(
                    (rec[key].id if rec._fields[key].type == 'many2one' else rec[key]) == value
                    for key, value in vals.items() if key in rec._fields):
                continue
            if rec.native_submitted or {'store_id', 'eplus_serial', 'status'} & vals.keys():
                raise AccessError(_('Approved native sales are immutable.'))
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
        native = self.filtered(lambda rec: rec.native_backend or self.env['ab_sales_backend']._is_native(rec.store_id.id))
        for rec in native:
            rec.line_ids._recompute_inventory_json()
        return super(NativeSale, self - native)._onchange_store_id()

    def _unavailable_lines_missing_reason(self):
        lines = super()._unavailable_lines_missing_reason()
        return lines.filtered(lambda line: not line.product_id.is_service) if self.native_backend else lines

    def _native_request_signature(self):
        self.ensure_one()
        header = {
            'store_id': self.store_id.id,
            'customer_id': self.customer_id.id,
            'is_delivery': bool(self.is_delivery),
            'employee_delivery_id': self.employee_delivery_id.id,
            'new_customer_name': self.new_customer_name or '',
            'new_customer_phone': self.new_customer_phone or '',
            'new_customer_address': self.new_customer_address or '',
            'description': self.description or '',
            'invoice_address': self.invoice_address or '',
        }
        lines = [{
            'product_id': line.product_id.id,
            'qty_str': (line.qty_str or '').strip(),
            'sell_price': round(float(line.sell_price or 0), 6),
            'target_sell_price': round(float(line.target_sell_price or 0), 6),
            'uom_id': line.uom_id.id,
            'unavailable_reason': line.unavailable_reason or '',
            'unavailable_reason_other': (line.unavailable_reason_other or '').strip(),
        } for line in self.line_ids.sorted('id')]
        programs = sorted(self.applied_program_ids.ids) if 'applied_program_ids' in self._fields else []
        return {'header': header, 'lines': lines, 'applied_program_ids': programs}

    def _native_request_digest(self):
        self.ensure_one()
        value = json.dumps(self._native_request_signature(), sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        return hashlib.sha256(value.encode()).hexdigest()

    def _native_approval_result(self):
        self.ensure_one()
        totals = self.native_totals or {}
        return {
            'id': self.id,
            'invoice_number': 'N-%s' % self.id,
            'status': self.status,
            'eplus_serial': False,
            'native_backend': True,
            'deducted_qty': totals.get('deducted_qty', 0),
            'shortage_qty': totals.get('shortage_qty', 0),
        }

    def _validate_native_approval(self):
        self.ensure_one()
        if not self.native_backend or not self.native_submitted or not self.native_posted:
            raise ValidationError(_('The pending native invoice has no completed stock approval snapshot.'))
        if (self.native_approval_version != 1 or not self.native_totals
                or not self.native_request_fingerprint or not self.native_content_fingerprint):
            raise ValidationError(_('The pending native invoice predates local stock approval and must use the legacy resolution process.'))
        if self._native_request_digest() != self.native_content_fingerprint:
            raise ValidationError(_('The approved native invoice content no longer matches its approval snapshot.'))
        line_context = self.native_totals.get('line_context') or {}
        Allocation = self.env['ab_sales_stock_allocation'].sudo()
        Shortage = self.env['ab_sales_stock_shortage'].sudo()
        for line in self.line_ids:
            snapshot = line_context.get(str(line.id))
            if not snapshot:
                raise ValidationError(_('The pending native invoice has incomplete line approval data.'))
            if snapshot.get('is_service'):
                continue
            allocations = Allocation.search([
                ('sale_line_id', '=', line.id),
                ('return_line_id', '=', False),
            ])
            shortages = Shortage.search([
                ('sale_line_id', '=', line.id),
                ('state', '=', 'open'),
            ])
            allocated = sum(allocations.mapped('qty_smallest'))
            shortage = sum(shortages.mapped('shortage_qty_smallest'))
            if allocated != snapshot.get('deducted_qty') or shortage != snapshot.get('shortage_qty'):
                raise ValidationError(_('The pending native invoice has incomplete stock allocations.'))
            if allocated + shortage != snapshot.get('stock_qty'):
                raise ValidationError(_('The pending native invoice stock approval does not match its sold quantity.'))
            if any(not rec.inventory_movement_id or rec.inventory_movement_id.status != 'saved'
                   or rec.store_id != self.store_id for rec in allocations):
                raise ValidationError(_('The pending native invoice has incomplete inventory movements.'))
        return True

    def action_submit(self, request_token=None):
        self.ensure_one()
        if not self.native_backend:
            return super().action_submit()
        self = self.with_context(ab_sales_branch_scope=True)
        self.check_access('read')
        store = self.env['ab_sales_backend']._check_store(self.store_id.id)
        self.env['ab_sales_backend']._check_employee_session(store, 'allow_pos_screen')
        token = (request_token or self.pos_client_token or '').strip()
        if not token or token != (self.pos_client_token or '').strip():
            raise ValidationError(_('The request token does not match this invoice.'))
        self.lock_for_update(allow_referencing=True)
        store._lock_stock_scope()
        self.invalidate_recordset()
        self.line_ids.invalidate_recordset()
        current_fingerprint = self._native_request_digest()
        candidate_fingerprint = self.env.context.get('native_request_fingerprint')
        request_fingerprint = candidate_fingerprint or current_fingerprint
        if self.native_request_fingerprint and candidate_fingerprint != self.native_request_fingerprint:
            if candidate_fingerprint:
                raise ValidationError(_('The request token is already assigned to different invoice content.'))
        if self.native_content_fingerprint and current_fingerprint != self.native_content_fingerprint:
            raise ValidationError(_('The approved native invoice content no longer matches its approval snapshot.'))
        if self.status in ('pending', 'saved'):
            self._validate_native_approval()
            return self._native_approval_result()
        if self.status == 'cancelled':
            raise ValidationError(_('A cancelled invoice cannot be submitted again.'))
        self.check_access('write')
        if self.status != 'prepending' or not self.line_ids:
            raise ValidationError(_('A native sale requires draft lines before approval.'))
        units = self.line_ids.mapped('uom_id')
        units.lock_for_update(allow_referencing=True)
        totals = self._compute_header_numbers(cur=None)
        if any(not math.isfinite(float(value)) or float(value) < 0 for key, value in totals.items()
               if key in ('total_bill', 'total_bill_after_disc', 'total_bill_net')):
            raise ValidationError(_('Native sale totals must be finite and nonnegative.'))
        for line in self.line_ids:
            if (not line.product_id or line.qty <= 0 or not math.isfinite(line.qty)
                    or not math.isfinite(line.sell_price) or line.sell_price < 0):
                raise ValidationError(_('Native sale lines require a product, positive quantity and valid price.'))
        Allocation = self.env['ab_sales_stock_allocation']
        plans = Allocation._build_sale_plan(self)
        Allocation._validate_shortage_reasons(plans)
        totals['line_context'] = {}
        totals['deducted_qty'] = 0
        totals['shortage_qty'] = 0
        for plan in plans:
            deducted = plan['qty'] - plan['shortage']
            totals['line_context'][str(plan['line'].id)] = {
                'is_service': plan['service'],
                'uom_factor': plan['line'].uom_id.factor,
                'stock_qty': plan['qty'],
                'stock_unit_id': plan['line'].product_id.unit_s_id.id if not plan['service'] else False,
                'deducted_qty': deducted,
                'shortage_qty': plan['shortage'],
            }
            if not plan['service']:
                totals['deducted_qty'] += deducted
                totals['shortage_qty'] += plan['shortage']
        with self.env.cr.savepoint():
            Allocation._post_sale_plan(self, plans)
            super(NativeSale, self.sudo()._submission_records()).write({
                'native_submitted': True,
                'native_posted': True,
                'native_totals': totals,
                'native_approval_version': 1,
                'native_request_fingerprint': request_fingerprint,
                'native_content_fingerprint': current_fingerprint,
                'status': 'pending',
                'push_state': 'success',
                'submission_phase': 'idle',
                **self._get_bill_customer_snapshot_vals(),
            })
        return self._native_approval_result()

    def action_push_to_eplus(self):
        self.ensure_one()
        if not self.native_backend:
            if self.env['ab_sales_backend']._is_native(self.store_id.id):
                raise ValidationError(_('Legacy invoices require their original backend; use the historical review process.'))
            return super().action_push_to_eplus()
        return self.action_submit(request_token=self.pos_client_token)

    def _post_native_stock(self):
        self.ensure_one()
        self._validate_native_approval()
        return True

    def _native_settled(self):
        self.ensure_one()
        self._validate_native_approval()
        super(NativeSale, self.sudo()._submission_records()).write({'status': 'saved'})

    def action_cancel_native(self, reason):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can cancel pending native invoices.'))
        reason = (reason or '').strip()
        if not reason:
            raise ValidationError(_('Enter a cancellation reason.'))
        self = self.with_context(ab_sales_branch_scope=True)
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        if self.status == 'cancelled':
            return {'id': self.id, 'invoice_number': 'N-%s' % self.id, 'status': self.status}
        if not self.native_backend or self.status != 'pending':
            raise ValidationError(_('Only pending native invoices can be cancelled.'))
        self.store_id._lock_stock_scope()
        allocations = self.env['ab_sales_stock_allocation'].sudo().search([
            ('sale_line_id.header_id', '=', self.id),
            ('return_line_id', '=', False),
        ], order='id')
        shortages = self.env['ab_sales_stock_shortage'].sudo().search([
            ('sale_id', '=', self.id),
            ('state', '=', 'open'),
        ])
        payments = self.env['ab_sales_native_payment'].sudo().search_count([
            ('sale_id', '=', self.id),
        ], limit=1)
        if payments:
            raise ValidationError(_('A collected invoice cannot be cancelled. Use the return workflow.'))
        if self.native_posted:
            self._validate_native_approval()
        else:
            stock_evidence = allocations or shortages or any(
                line.native_stock_qty or line.native_requested_stock_qty or line.native_shortage_qty
                or line.native_operation_key or line.native_allocations
                for line in self.line_ids
            )
            if not self.native_submitted or stock_evidence:
                raise ValidationError(_(
                    'This legacy invoice has stock activity that cannot be safely reversed automatically. '
                    'Use historical review.'
                ))
        with self.env.cr.savepoint():
            for allocation in allocations:
                self.env['ab_sales_stock_reversal']._reverse_allocation(allocation)
            shortages._cancel()
            super(NativeSale, self.sudo()._submission_records()).write({
                'status': 'cancelled',
                'native_cancel_reason': reason,
                'native_cancelled_by_id': self.env.uid,
                'native_cancelled_at': fields.Datetime.now(),
            })
        return {
            'id': self.id,
            'invoice_number': 'N-%s' % self.id,
            'status': self.status,
            'reversed_qty': sum(allocations.mapped('qty_smallest')),
        }

    def action_open_native_cancel(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can cancel pending native invoices.'))
        if not self.native_backend or self.status != 'pending':
            raise ValidationError(_('Only pending native invoices can be cancelled.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cancel Pending Native Invoice'),
            'res_model': 'ab_sales_native_cancel_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_id': self.id},
        }

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
            ('native_origin_id', '=', self.id),
            ('status', '=', 'prepending'),
        ], limit=1)
        if not header:
            header = self.env['ab_sales_return_header'].create({
                'store_id': self.store_id.id,
                'native_origin_id': self.id,
                'origin_header_id': self.id,
            })
        header.action_load_lines()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ab_sales_return_header',
            'view_mode': 'form',
            'res_id': header.id,
            'target': 'new',
        }

    def _compute_notice_header_ids(self):
        native = self.filtered('native_backend')
        for rec in native:
            rec.notice_header_ids = self.env['ab_sales_return_header'].search([('native_origin_id', '=', rec.id)])
        super(NativeSale, self - native)._compute_notice_header_ids()


class NativeSaleLine(models.Model):
    _inherit = 'ab_sales_line'

    native_stock_qty = fields.Float(string='Deducted Stock Quantity', readonly=True, copy=False, digits=(18, 6))
    native_requested_stock_qty = fields.Float(string='Requested Stock Quantity', readonly=True, copy=False, digits=(18, 6))
    native_shortage_qty = fields.Float(string='Stock Shortage Quantity', readonly=True, copy=False, digits=(18, 6))
    native_unit_factor = fields.Float(string='Posted Unit Factor', readonly=True, copy=False, digits=(18, 8))
    native_operation_key = fields.Char(string='Stock Operation Key', readonly=True, copy=False, index=True)
    native_allocations = fields.Json(string='Posted Stock Allocations', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(key.startswith('native_') for key in vals):
                raise AccessError(_('Stock allocations are managed by native approval.'))
            header = self.env['ab_sales_header'].browse(vals.get('header_id')).exists()
            if header.native_backend:
                header.check_access('write')
                header.lock_for_update(allow_referencing=True)
                header.invalidate_recordset()
                self.env['ab_sales_backend']._check_store(header.store_id.id)
                if header.native_submitted:
                    raise AccessError(_('Approved native sale lines cannot be changed.'))
                product = self.env['ab_product'].browse(vals.get('product_id')).exists()
                vals['inventory_json'] = {'data': self.env['ab_sales_pos_api']._native_inventory_rows(header.store_id.id, product)}
        return super().create(vals_list)

    def write(self, vals):
        if any(key.startswith('native_') for key in vals):
            raise AccessError(_('Stock allocations are managed by native approval.'))
        headers = self.mapped('header_id')
        if vals.get('header_id'):
            headers |= self.env['ab_sales_header'].browse(vals['header_id'])
        for header in headers.filtered('native_backend'):
            header.lock_for_update(allow_referencing=True)
            header.invalidate_recordset()
            self.env['ab_sales_backend']._check_store(header.store_id.id)
            if header.native_submitted:
                raise AccessError(_('Approved native sale lines cannot be changed.'))
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
            raise AccessError(_('Approved native sale lines cannot be deleted.'))
        return super().unlink()

    def _set_native_stock_snapshot(self, plan, allocations):
        self.ensure_one()
        deducted = plan['qty'] - plan['shortage']
        super(NativeSaleLine, self.sudo().with_context(self.header_id._submission_records().env.context)).write({
            'native_requested_stock_qty': plan['qty'],
            'native_stock_qty': deducted,
            'native_shortage_qty': plan['shortage'],
            'native_unit_factor': plan['factor'],
            'native_operation_key': 'sale:%s:line:%s' % (self.header_id.id, self.id),
            'native_allocations': allocations,
        })

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
                raise ValidationError(_('Units used by approved native sales cannot change their factors or categories.'))
        return super().write(vals)
