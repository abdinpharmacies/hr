"""Versioned branch boundary. Only the branch executes E-Plus business writes."""
from contextvars import ContextVar
import hashlib
import json
import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import config

from .routing import api_request, request_store, selected_server, STORE_UNSET


_return_employee = ContextVar('branch_api_return_employee', default=None)


class BranchApiOperation(models.Model):
    _name = 'ab_branch_api_operation'
    _description = 'Branch API Operation'
    _rec_name = 'token'
    _order = 'id desc'

    active = fields.Boolean(default=True)
    token = fields.Char(required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    kind = fields.Selection([('sale', 'Sale'), ('return', 'Return')], required=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('processing', 'Processing'), ('done', 'Done'),
        ('uncertain', 'Needs Reconciliation'), ('retryable', 'Ready to Retry'),
    ], default='draft', required=True)
    recovery_enabled = fields.Boolean(readonly=True)
    commit_evidence = fields.Json(readonly=True)
    payload_hash = fields.Char(readonly=True)
    reservation_key = fields.Char(readonly=True, index=True)
    _unique_reservation = models.Constraint('UNIQUE(reservation_key)', 'Another return for this invoice needs completion or reconciliation.')
    record_id = fields.Integer(readonly=True)
    result = fields.Json(readonly=True)
    message = fields.Text(readonly=True)
    _unique_token = models.Constraint('UNIQUE(token)', 'Request token already exists.')


class BranchApi(models.AbstractModel):
    _name = 'ab_branch_api'
    _description = 'Branch API'
    _inherit = ['ab_eplus_connect']

    @api.private
    def decrypt_password(self):
        return super().decrypt_password()

    @api.model
    def _authenticate_replica(self, db_serial):
        self._authenticate_bearer()
        if type(db_serial) is not int or db_serial <= 0:
            raise UserError(_('DB serial must be a positive integer.'))
        try:
            configured_serial = int(config.get('db_serial', 0) or 0)
        except (TypeError, ValueError):
            configured_serial = 0
        if db_serial != configured_serial:
            raise AccessError(_('DB serial does not match this branch server.'))
        replica = self.env['ab_replica_db'].sudo().search(
            fields.Domain('db_serial', '=', db_serial) & fields.Domain('active', '=', True), limit=2)
        if len(replica) != 1:
            raise UserError(_('An active replica is required for this DB serial.'))
        return replica

    @api.model
    def _resolve_store(self, replica, store_eplus_serial=STORE_UNSET, required=True):
        if store_eplus_serial is STORE_UNSET:
            default = replica.default_sales_store_id
            if not default:
                if required:
                    raise UserError(_('Select a store or configure a default sales store for this operation.'))
                return self.env['ab_store']
            store_eplus_serial = default.eplus_serial
        else:
            default = False
        if type(store_eplus_serial) is not int or store_eplus_serial <= 0:
            raise UserError(_('Store E-Plus serial must be a positive integer.'))
        store = self.env['ab_store'].sudo().search(
            fields.Domain('eplus_serial', '=', store_eplus_serial)
            & fields.Domain('active', '=', True) & fields.Domain('allow_sale', '=', True), limit=2)
        if len(store) != 1 or (default and store != default):
            raise UserError(_('An unambiguous active sales store is required for this E-Plus serial.'))
        if not replica.allowed_sales_store_ids or store not in replica.allowed_sales_store_ids:
            raise AccessError(_('The selected store is not in the replica Allowed Sales Stores.'))
        # Metadata lookup is privileged; business records retain the caller's environment.
        store = self.env['ab_store'].browse(store.id)
        store.check_access('read')
        return store

    @api.model
    def _business_permissions(self, kind, post=False, raise_exception=True):
        names = ['ab_sales_header', 'ab_sales_line', 'ab_product', 'ab_product_uom']
        if kind == 'return':
            names += ['ab_sales_return_header', 'ab_sales_return_line']
        for name in names:
            operations = ['read']
            if post and name in (('ab_sales_return_header', 'ab_sales_return_line')
                                 if kind == 'return' else ('ab_sales_header', 'ab_sales_line')):
                operations += ['create', 'write']
            for operation in operations:
                model = self.env[name]
                if raise_exception:
                    model.check_access(operation)
                elif not model.has_access(operation):
                    return False
        return True

    @api.model
    @api_request
    def get_capabilities(self, db_serial, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self, required=False)
        self._business_permissions('sale')
        can_post = all(self._business_permissions(kind, post=True, raise_exception=False)
                       for kind in ('sale', 'return'))
        return {'version': 1, **self._identity(store, db_serial),
                'store_name': store.display_name or '', 'branch_store_id': store.id, 'can_post': can_post,
                'methods': ['get_capabilities', 'get_connection_status', 'search_products',
                            'get_stock_lines', 'submit_sale', 'get_return_invoice',
                            'submit_return', 'get_operation_status', 'reconcile_operation']}

    @api.model
    def _identity(self, store, db_serial):
        return {'db_serial': db_serial, 'store_eplus_serial': int(store.eplus_serial) if store else False}

    @api.model
    def _resolve(self, model, ref):
        if not isinstance(ref, dict) or len(ref) != 1:
            raise UserError(_('A stable record reference is required.'))
        key, value = next(iter(ref.items()))
        if key == 'xmlid':
            records = self.env[model].search(fields.Domain('id', 'in',
                self.env['ir.model.data'].sudo().search(
                    fields.Domain('module', '=', str(value).split('.', 1)[0])
                    & fields.Domain('name', '=', str(value).split('.', 1)[-1])
                    & fields.Domain('model', '=', model)).mapped('res_id')), limit=2)
        elif model == 'ab_hr_employee' and key == 'costcenter_code':
            records = self.env[model].search(fields.Domain('costcenter_id.code', '=', str(value)), limit=2)
        elif key in ('eplus_serial', 'code') and key in self.env[model]._fields:
            records = self.env[model].search(fields.Domain(key, '=', value), limit=2)
        else:
            raise UserError(_('Unsupported record reference.'))
        if len(records) != 1:
            raise UserError(_('Branch reference is missing or ambiguous: %s') % model)
        return records

    @api.model
    @api_request
    def search_products(self, db_serial, query='', limit=60, offset=0, *, store_eplus_serial=STORE_UNSET):
        self._business_permissions('sale')
        domain = fields.Domain('active', '=', True)
        if query:
            domain &= fields.Domain('name', 'ilike', str(query)[:120]) | fields.Domain('code', 'ilike', str(query)[:120])
        products = self.env['ab_product'].search(domain, limit=min(max(int(limit), 1), 120),
                                                  offset=max(int(offset), 0), order='name, id')
        return [{'product_serial': int(p.eplus_serial or 0), 'code': p.code or '',
                 'name': p.display_name} for p in products if p.eplus_serial]

    @api.model
    @api_request
    def get_stock_lines(self, db_serial, product_serials, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('sale')
        return self._stock_lines(store, db_serial, product_serials)

    @api.model
    def _stock_lines(self, store, db_serial, product_serials):
        serials = sorted({int(s) for s in product_serials if int(s) > 0})
        if len(serials) > 200:
            raise UserError(_('At most 200 products may be requested.'))
        if not serials:
            return {**self._identity(store, db_serial), 'data': []}
        products = self.env['ab_product'].search(fields.Domain('eplus_serial', 'in', serials))
        if set(products.mapped('eplus_serial')) != set(serials):
            raise AccessError(_('Requested products are not accessible.'))
        rows = self.env['ab_sales_header']._read_store_stock(store, serials)
        return {**self._identity(store, db_serial),
                'data': [dict(row, db_serial=db_serial) for row in rows]}

    @api.model
    def _operation(self, store, token, kind):
        if not isinstance(token, str) or not 16 <= len(token) <= 128:
            raise UserError(_('A request token between 16 and 128 characters is required.'))
        self._lock_operation(token)
        Operation = self.env['ab_branch_api_operation'].sudo()
        operation = Operation.search(fields.Domain('token', '=', token), limit=1)
        if not operation:
            # A unique constraint arbitrates concurrent first submissions; a retry sees the winner.
            operation = Operation.create({'user_id': self.env.uid, 'store_id': store.id,
                                          'token': token, 'kind': kind})
        if operation.user_id.id != self.env.uid or operation.store_id != store or operation.kind != kind:
            raise AccessError(_('Request token belongs to another operation.'))
        return operation

    @api.model
    @api_request
    def get_operation_status(self, db_serial, token, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('sale')
        operation = self.env['ab_branch_api_operation'].sudo().search(
            fields.Domain('user_id', '=', self.env.uid) & fields.Domain('token', '=', token)
            & fields.Domain('store_id', '=', store.id), limit=1)
        if not operation:
            return {**self._identity(store, db_serial), 'state': 'not_found'}
        self._business_permissions(operation.kind)
        if operation.record_id:
            if operation.kind in ('sale', 'return'):
                model = 'ab_sales_header' if operation.kind == 'sale' else 'ab_sales_return_header'
                self.env[model].browse(operation.record_id).check_access('read')
        return {**self._identity(store, db_serial), 'state': operation.state,
                'result': ({**operation.result, **self._identity(store, db_serial)} if operation.result else {}),
                'message': operation.message or ''}

    @api.model
    def _assert_invoice_branch(self, store, invoice, require_saved=False):
        server = selected_server(self, store)
        if not server:
            raise UserError(_('The branch E-Plus server is not configured.'))
        with self.connect_eplus(server=server, autocommit=False, charset='UTF-8', param_str='?') as conn:
            cur = conn.cursor()
            cur.execute('SELECT sth_id, sth_flag, sec_insert_date FROM sales_trans_h WHERE sth_id = ? AND sto_id = ?',
                        (int(invoice), int(store.eplus_serial)))
            source = cur.fetchone()
            if not source:
                raise UserError(_('Invoice does not belong to this branch.'))
            if require_saved and source[1] != 'C':
                raise UserError(_('Source invoice must be saved before posting a return.'))
            return source[2]

    @api.model
    def _return_header(self, store, operation, invoice):
        source = self.env['ab_sales_header'].search(
            fields.Domain('store_id', '=', store.id)
            & fields.Domain('eplus_serial', '=', int(invoice))
            & fields.Domain('is_callcenter_order', '=', True), limit=1)
        if not source or int(invoice) <= 0:
            raise AccessError(_('Only call-center invoices can be returned.'))
        header = self.env['ab_sales_return_header'].browse(operation.record_id).exists()
        if header:
            header.check_access('write')
            header.line_ids.check_access('write')
            if (header.store_id != store or header.origin_header_id != int(invoice)
                    or not header.is_callcenter_order):
                raise AccessError(_('Return invoice does not match the request.'))
        else:
            self._assert_invoice_branch(store, invoice)
            header = self.env['ab_sales_return_header']._create_callcenter_order({
                'store_id': store.id, 'origin_header_id': int(invoice)})
            operation.record_id = header.id
        return header

    @api.model
    def _return_snapshot(self, header, db_serial):
        names = ['source_itm_unit', 'source_uom_factor', 'item_unit1_unit2', 'item_unit1_unit3',
                 'qty_sold_source', 'max_returnable_source', 'qty_sold', 'max_returnable_qty',
                 'sell_price', 'cost', 'itm_eplus_id', 'sth_id', 'sto_id', 'c_id', 'std_id', 'itm_nexist']
        lines = []
        for line in header.line_ids:
            values = {name: line[name] for name in names}
            values['uom_factor'] = float(line.uom_id.factor or line.source_uom_factor or 1)
            values['selected_qty_source'] = float(line._qty_to_source_unit())
            lines.append(values)
        return {**self._identity(header.store_id, db_serial), 'invoice': int(header.origin_header_id),
                'branch_return_id': header.id, 'status': header.status,
                'sales_return_id': int(header.sales_return_id or 0),
                'f_transaction_id': int(header.f_transaction_id or 0),
                'total_sales_net': float(header.total_sales_net),
                'total_return_value': float(header.total_return_value), 'lines': lines}

    @api.model
    @api_request
    def get_return_invoice(self, db_serial, invoice, token, selections=False, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('return', post=True)
        operation = self._operation(store, token, 'return')
        if operation.state in ('processing', 'uncertain'):
            self._reconcile_post(operation)
        header = self._return_header(store, operation, invoice)
        if header.status != 'saved':
            self._assert_invoice_branch(store, invoice)
            header.action_load_lines()
            if selections is not False:
                self._apply_return_lines(header, selections)
        return self._return_snapshot(header, db_serial)

    @api.model
    def _run_post(self, operation, payload, callback, failure_snapshot=None):
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        if operation.payload_hash and operation.payload_hash != digest:
            raise UserError(_('The request token was already used with different data.'))
        if operation.state not in ('draft', 'retryable'):
            if operation.payload_hash != digest:
                raise UserError(_('The request token was already used with different data.'))
            if operation.state == 'done':
                return {**(operation.result or {}),
                        **self._identity(request_store(self), int(config.get('db_serial')))}
            raise UserError(_('Operation outcome needs reconciliation. Check the branch before retrying.'))
        operation.write({'state': 'processing', 'payload_hash': digest,
                         'recovery_enabled': operation.kind in ('sale', 'return'),
                         'commit_evidence': False})
        # Durably reserve before crossing the SQL Server/PostgreSQL transaction boundary.
        # Concurrent updates conflict under Odoo repeatable-read; no automatic external retry.
        self.env.cr.commit()
        try:
            with self._posting_scope(operation):
                result = callback()
        except Exception as error:
            partial = {}
            if failure_snapshot:
                try:
                    partial = failure_snapshot()
                except Exception:
                    pass
            self.env.cr.rollback()
            operation.invalidate_recordset()
            operation.write({'state': 'uncertain', 'message': str(error), 'result': partial})
            self.env.cr.commit()
            raise
        operation.write({'state': 'done', 'result': result, 'message': '', 'reservation_key': False})
        self.env.cr.commit()
        return result

    @api.model
    def _apply_return_lines(self, header, lines):
        header.check_access('write')
        header.line_ids.check_access('write')
        by_id = {int(line.std_id): line for line in header.line_ids}
        seen = set()
        header.line_ids.write({'qty_str': '0'})
        for selected in lines:
            source_id = int(selected['std_id'])
            qty = float(selected['qty_source'])
            if source_id in seen or source_id not in by_id or not math.isfinite(qty) or qty < 0:
                raise UserError(_('Invalid return line or quantity.'))
            seen.add(source_id)
            line = by_id[source_id]
            if int(selected['product_serial']) != line.itm_eplus_id:
                raise UserError(_('Return product does not match the original invoice line.'))
            factor = float(line.uom_id.factor or line.source_uom_factor or 1)
            line.qty_str = str(qty * float(line.source_uom_factor or 1) / factor)

    @api.model
    def _validate_return_employee(self, employee_ref):
        if not employee_ref:
            raise UserError(_('A return employee is required. Log in to the callcenter POS or select a return employee in the Administrator return form.'))
        try:
            employee = self.with_context(active_test=False)._resolve('ab_hr_employee', employee_ref)
        except UserError as error:
            raise UserError(_('The return employee is missing or ambiguous on this branch. Check the employee cost center code.')) from error
        employee.check_access('read')
        costcenter = employee.costcenter_id
        costcenter.check_access('read')
        if not employee.active or not costcenter or not costcenter.active:
            raise UserError(_('The return employee and employee cost center must be active on this branch.'))
        if costcenter.eplus_serial <= 0:
            raise UserError(_('The return employee has no valid E-Plus mapping on this branch. Configure the employee cost center E-Plus serial before retrying.'))
        return employee

    @api.model
    @api_request
    def submit_return(self, db_serial, invoice, token, lines, notes='', employee_ref=False, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('return', post=True)
        operation = self._operation(store, token, 'return')
        payload = {'invoice': int(invoice), 'lines': lines, 'notes': str(notes), 'employee_ref': employee_ref}
        self._prepare_post(operation, payload)
        if operation.state == 'done':
            self._return_header(store, operation, invoice)
            return self._run_post(operation, payload, lambda: {})
        employee = self._validate_return_employee(employee_ref)
        header = self._return_header(store, operation, invoice)
        invoice_date = self._assert_invoice_branch(store, invoice, require_saved=True)
        header._validate_invoice_return_window(sth_id=int(invoice), sec_insert_date=invoice_date)
        header.action_load_lines()
        self._apply_return_lines(header, lines)
        header.notes = str(notes)
        header._validate_return()
        operation.reservation_key = 'return:%s:%s' % (store.id, int(invoice))

        def post():
            actor_token = _return_employee.set(employee.id if employee else None)
            try:
                header.action_push_to_eplus_return()
                return self._return_snapshot(header, db_serial)
            finally:
                _return_employee.reset(actor_token)
        return self._run_post(operation, payload, post, lambda: {
            **self._identity(store, db_serial),
            'branch_return_id': header.id, 'sales_return_id': int(header.sales_return_id or 0),
            'f_transaction_id': int(header.f_transaction_id or 0), 'status': header.status})

    @api.model
    @api_request
    def submit_sale(self, db_serial, token, payload, push_to_eplus=True, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('sale', post=True)
        operation = self._operation(store, token, 'sale')
        request = {'payload': payload, 'push': bool(push_to_eplus)}
        self._prepare_post(operation, request)
        if operation.state == 'done':
            self.env['ab_sales_header'].browse(operation.record_id).check_access('read')
            return self._run_post(operation, request, lambda: {})
        header = self._operation_header(operation) if operation.record_id else False
        if not header:
            Pos = self.env['ab_sales_pos_api']
            header_model = self.env['ab_sales_header']
            allowed = {'customer_id', 'employee_id', 'employee_delivery_id', 'contract_id', 'doctor_id',
                       'is_delivery', 'description', 'invoice_address', 'new_customer_name',
                       'new_customer_phone', 'new_customer_address', 'customer_insurance_name',
                       'customer_insurance_number', 'total_invoice_discount', 'is_doctor_prescription',
                       'bill_customer_name', 'bill_customer_phone', 'bill_customer_address',
                       'pos_hr_employee_id', 'pos_hr_device_uid', 'pos_hr_device_name', 'pos_hr_device_ip'}
            values = self._sale_values(header_model, payload.get('header', {}), allowed)
            values.update({'store_id': store.id, 'pos_client_token': token, 'status': 'prepending'})
            header_model.new(values)._validate_new_customer()
            header = header_model._create_callcenter_order(values)
            operation.record_id = header.id
            Line = self.env['ab_sales_line']
            line_values = []
            for source in payload.get('lines', []):
                line_source = {key: value for key, value in source.items() if key != 'uom_factor'}
                vals = self._sale_values(Line, line_source, {'product_id', 'qty_str', 'sell_price',
                    'unavailable_reason', 'unavailable_reason_other', 'target_sell_price', 'is_doctor_prescription_product', 'uom_factor'})
                product = self.env['ab_product'].browse(vals.get('product_id')).exists()
                if not product:
                    raise UserError(_('Product is required.'))
                factor = float(source.get('uom_factor') or product.uom_id.factor)
                uom = self.env['ab_product_uom'].search(fields.Domain('category_id', '=', product.uom_category_id.id)
                                                       & fields.Domain('factor', '=', factor), limit=2)
                if len(uom) != 1:
                    raise UserError(_('Branch product unit is missing or ambiguous.'))
                vals.update({'uom_id': Pos._pos_line_uom_id(product, uom.id), 'header_id': header.id})
                Pos._pos_fill_inventory_json_for_price_validation(header, vals)
                line_values.append(vals)
            Line.create(line_values)
            if payload.get('promotion'):
                program = self._resolve('ab_promo_program', payload['promotion'])
                header.applied_program_ids = [fields.Command.set(program.ids)]
                header.btn_apply_promotion()
            Pos._fill_lines_balance_from_offline(header)
        header.check_access('write')
        header.line_ids.check_access('write')

        def post():
            if push_to_eplus:
                header.with_context(pos_submit=True).action_push_to_eplus()
                if not header.eplus_serial or header.status not in ('pending', 'saved'):
                    raise UserError(_('Branch sale was not pushed to E-Plus.'))
            return {**self._identity(store, db_serial), 'remote_callcenter': True, 'branch_header_id': header.id,
                    'remote_header_id': header.id, 'status': header.status,
                    'eplus_serial': int(header.eplus_serial or 0), 'pos_header_id': False,
                    'message': _('Branch sale submitted.')}
        return self._run_post(operation, request, post, lambda: {
            **self._identity(store, db_serial),
            'branch_header_id': header.id, 'eplus_serial': int(header.eplus_serial or 0), 'status': header.status})

    @api.model
    def _sale_values(self, model, source, allowed):
        values = {}
        for key, value in source.items():
            if key not in allowed:
                raise UserError(_('Unsupported sale field: %s') % key)
            if key not in model._fields:
                if value:
                    raise UserError(_('Branch module does not support field: %s') % key)
                continue
            field = model._fields[key]
            if field.type == 'many2one':
                values[key] = self._resolve(field.comodel_name, value).id if value else False
            else:
                values[key] = value
        return values


class BranchReturnEmployee(models.Model):
    _inherit = 'ab_sales_header'

    @api.model
    def _get_eplus_emp_id(self, employee=False):
        actor = _return_employee.get()
        if not employee and actor:
            employee = self.env['ab_hr_employee'].browse(actor)
        return super()._get_eplus_emp_id(employee=employee)
