"""Optional central-inventory adapter; the API remains independent of central sync."""
import hashlib
import json
import math
from contextlib import contextmanager

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .routing import api_request, request_store, STORE_UNSET


class CentralInventoryAPI(models.AbstractModel):
    _inherit = 'ab_branch_api'

    def _uses_central_inventory(self, store):
        return ('ab_branch_sync_operation' in self.env.registry
                and self.env['ab_branch_sync_operation']._uses_central(store))

    @api.model
    def get_capabilities(self, db_serial, *, store_eplus_serial=STORE_UNSET):
        result = super().get_capabilities(db_serial, store_eplus_serial=store_eplus_serial)
        store = self.env['ab_store'].browse(result.get('branch_store_id'))
        if self._uses_central_inventory(store):
            result['central_inventory'] = 2
            result['methods'] += ['get_native_return_invoice', 'submit_native_return']
        return result

    @contextmanager
    def _central_employee(self, store, reference):
        # Called only inside an authenticated, store-scoped API request.
        employee = self._resolve('ab_hr_employee', reference) if reference else self.env['ab_hr_employee']
        employee.check_access('read')
        if not employee or not employee.active:
            raise AccessError(_('A replicated active employee is required.'))
        profile = self.env['ab_employee_access'].sudo().search(fields.Domain('employee_id', '=', employee.id)
            & fields.Domain('pos_allow_login', '=', True), limit=2)
        if len(profile) != 1 or not profile._is_store_allowed_for_pos(store):
            raise AccessError(_('The employee is not authorized for this store.'))
        self.env['ab_sales_backend']._check_store(store.id)
        self.env['ab_employee_access_sales_pos_api']._check_service_user(store)
        session = self.env['ab_employee_access_sales_pos_session'].sudo().create({
            'employee_id': employee.id, 'profile_id': profile.id, 'role_id': profile.pos_role_id.id,
            'service_user_id': self.env.uid, 'store_id': store.id,
            'device_uid': 'callcenter-api', 'device_name': _('Callcenter API'),
        })
        try:
            yield self.with_context(**{name: session.session_token for name in
                ('native_pos_hr_token', 'ab_return_session_token', 'native_cashier_session_token')})
        finally:
            if session.exists():
                session.close_session()

    def _submit_guarded_sale(self, db_serial, token, payload, revision, push):
        store = request_store(self)
        if not self._uses_central_inventory(store):
            return super()._submit_guarded_sale(db_serial, token, payload, revision, push)
        self._business_permissions('sale', post=True)
        if push is not True or type(revision) is not int or revision < 1 or not isinstance(payload, dict):
            raise UserError(_('Invalid sale payload.'))
        self._sale_source_identity(payload)
        fingerprint = hashlib.sha256(json.dumps({'payload': payload, 'push': True}, sort_keys=True, allow_nan=False).encode()).hexdigest()
        operation = self._operation(store, token, 'sale')
        previous = operation.payload_hash
        changed = bool(previous and previous != fingerprint)
        if (previous and revision == operation.request_revision and changed
                or previous and revision != operation.request_revision and (
                    revision != operation.request_revision + 1 or not changed or operation.state != 'rejected')
                or not previous and revision != 1):
            raise UserError(_('The request token was already used with different data.'))
        if operation.state == 'done':
            return self._guarded_sale_result(operation)
        history = list(operation.attempt_history or [])
        if changed:
            history.append({'revision': operation.request_revision, 'payload_hash': previous,
                            'state': operation.state, 'message': operation.message or ''})
        operation.write({'sale_guard_version': 1, 'request_revision': revision,
            'request_payload': payload, 'payload_hash': fingerprint, 'state': 'processing',
            'message': '', 'attempt_history': history})
        try:
            with self.env.cr.savepoint():
                source = payload.get('header', {})
                with self._central_employee(store, source.get('pos_hr_employee_id') or source.get('employee_id')) as actor:
                    header = actor._operation_header(operation, access='read') if operation.record_id else False
                    header = actor._prepare_sale_header(operation, payload, header=header)
                    header._backend_submit()
                    operation.write({'sale_prepared_revision': revision, 'state': 'done'})
        except (AccessError, UserError, ValidationError) as error:
            operation.invalidate_recordset()
            operation.write({'state': 'rejected', 'message': str(error)})
        result = self._guarded_sale_result(operation)
        operation.write({'result': result})
        return result

    def _guarded_sale_result(self, operation):
        result = super()._guarded_sale_result(operation)
        header = self._operation_header(operation, access='read') if operation.record_id else False
        if header and self._uses_central_inventory(header.store_id) and 'native_backend' in header._fields and header.native_backend:
            result.update(inventory_backend='central', native_invoice_id=header.id, eplus_serial=0)
            operation = self.env['ab_branch_sync_operation'].sudo().with_context(active_test=False).search(
                fields.Domain('direction', '=', 'out') & fields.Domain('kind', '=', 'sale')
                & fields.Domain('store_id', '=', header.store_id.id) & fields.Domain('document_id', '=', header.id), limit=1)
            result.update(sync_token=operation.token or False, sync_state=operation.state or False,
                          sync_message=_('Central synchronization needs attention.') if operation.error else '')
        return result

    def _native_return_header(self, store, operation, invoice):
        if not self._uses_central_inventory(store) or type(invoice) is not int or invoice <= 0:
            raise AccessError(_('Invalid native invoice reference.'))
        sale = self.env['ab_sales_header'].browse(invoice).exists()
        sale.check_access('read')
        if not sale or sale.store_id != store or not sale.native_backend or sale.status != 'saved':
            raise AccessError(_('The settled native invoice must belong to this store.'))
        header = self.env['ab_sales_return_header'].browse(operation.record_id).exists()
        if header:
            header.check_access('write')
            if header.native_origin_id != sale or header.store_id != store or not header.is_callcenter_order:
                raise AccessError(_('Return invoice does not match the request.'))
        else:
            header = self.env['ab_sales_return_header']._create_callcenter_order({'store_id': store.id, 'native_origin_id': sale.id})
            operation.record_id = header.id
            header.action_load_lines()
        return header

    def _native_return_snapshot(self, header, db_serial):
        lines = []
        for line in header.line_ids:
            original = line.native_origin_line_id
            lines.append({'std_id': original.id, 'sth_id': header.native_origin_id.id,
                'sto_id': header.store_id.eplus_serial, 'itm_eplus_id': line.product_id.eplus_serial,
                'source_itm_unit': 3, 'source_uom_factor': line.uom_id.factor,
                'item_unit1_unit2': 1, 'item_unit1_unit3': 1, 'c_id': 0, 'itm_nexist': 0,
                'qty_sold_source': line.qty_sold, 'max_returnable_source': line.max_returnable_qty,
                'qty_sold': line.qty_sold, 'max_returnable_qty': line.max_returnable_qty,
                'sell_price': line.sell_price, 'cost': line.cost, 'uom_factor': line.uom_id.factor,
                'selected_qty_source': line.qty})
        payment = self.env['ab_sales_native_payment'].sudo().search(fields.Domain('return_id', '=', header.id), limit=1)
        return {**self._identity(header.store_id, db_serial), 'inventory_backend': 'central',
            'native_invoice_id': header.native_origin_id.id, 'invoice': header.native_origin_id.id,
            'branch_return_id': header.id, 'native_return_id': header.id, 'native_payment_id': payment.id or 0,
            'status': header.status, 'sales_return_id': 0, 'f_transaction_id': 0,
            'total_sales_net': header.native_origin_id.native_totals['total_bill_net'],
            'total_return_value': header.native_refund if header.native_posted else header._native_refund_amount(), 'lines': lines}

    def _native_selections(self, header, selections):
        by_id = {line.native_origin_line_id.id: line for line in header.line_ids}
        seen = set()
        header.line_ids.write({'qty_str': '0'})
        for selection in selections:
            line = by_id.get(selection.get('std_id'))
            qty = selection.get('qty_source')
            if (not line or line.id in seen or selection.get('product_serial') != line.product_id.eplus_serial
                    or type(qty) not in (int, float) or not math.isfinite(qty) or qty < 0):
                raise UserError(_('Invalid return line or quantity.'))
            seen.add(line.id)
            # Existing native return validation checks finite quantities and limits.
            line.qty_str = str(qty)

    @api.model
    @api_request
    def get_native_return_invoice(self, db_serial, invoice, token, selections=False, employee_ref=False, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('return', post=True)
        operation = self._operation(store, token, 'return')
        with self._central_employee(store, employee_ref) as actor:
            header = actor._native_return_header(store, operation, invoice)
            if header.status == 'prepending' and selections is not False:
                actor._native_selections(header, selections)
            return actor._native_return_snapshot(header, db_serial)

    @api.model
    @api_request
    def submit_native_return(self, db_serial, invoice, token, lines, notes='', employee_ref=False, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('return', post=True)
        operation = self._operation(store, token, 'return')
        with self._central_employee(store, employee_ref) as actor:
            header = actor._native_return_header(store, operation, invoice)
            payload = {'native_invoice_id': invoice, 'lines': lines, 'notes': str(notes), 'employee_ref': employee_ref}
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
            if operation.payload_hash and operation.payload_hash != fingerprint:
                raise UserError(_('The request token was already used with different data.'))
            if operation.state == 'done':
                return actor._native_return_snapshot(header, db_serial)
            # Native records and the API result share one PostgreSQL transaction.
            if header.status == 'prepending':
                actor._native_selections(header, lines)
                header.notes = str(notes)
                header.action_set_pending()
            result = actor._native_return_snapshot(header, db_serial)
            operation.write({'state': 'done', 'payload_hash': fingerprint, 'request_payload': payload,
                             'result': result, 'message': '', 'reservation_key': False})
            return result

    @api.model
    @api_request
    def create_customer(self, db_serial, token, phone, name, address, *, store_eplus_serial=STORE_UNSET):
        if self._uses_central_inventory(request_store(self)):
            raise UserError(_('Synchronize the customer catalog before creating sales for this customer.'))
        return super().create_customer(db_serial, token, phone, name, address, store_eplus_serial=store_eplus_serial)
