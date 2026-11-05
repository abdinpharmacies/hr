"""Capture native lifecycle events; replay through the same business methods."""
import math
import requests
import uuid
from contextvars import ContextVar

REPLAY_ORIGIN = ContextVar("central_sync_origin", default=None)

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

HEADER = ('customer_id', 'employee_id', 'employee_delivery_id', 'contract_id', 'doctor_id',
          'is_delivery', 'description', 'invoice_address', 'bill_customer_name', 'bill_customer_phone',
          'bill_customer_address', 'customer_insurance_name', 'customer_insurance_number', 'total_invoice_discount')
AMOUNTS = ('ab_contract_net_amount', 'ab_customer_amount', 'ab_company_amount', 'promo_discount_amount')
LINE = ('product_id', 'qty_str', 'sell_price', 'target_sell_price', 'unavailable_reason', 'unavailable_reason_other')


def allocation_snapshot(document):
    rows = document.env['ab_sales_stock_allocation'].sudo().search(fields.Domain([('sale_line_id.header_id', '=', document.id), ('return_line_id', '=', False)]))
    return [{'line': str(row.sale_line_id.id), 'source': reference(row.source_id), 'quantity': row.qty_smallest, 'price': row.unit_price, 'cost': row.unit_cost} for row in rows]


def reference(record):
    if not record:
        return False
    for key in ('eplus_serial', 'code', 'accid'):
        if key in record._fields and record[key]:
            return {key: record[key]}
    xmlid = record.get_external_id().get(record.id)
    if xmlid:
        return {'xmlid': xmlid}
    raise ValidationError(_('A synchronized master record requires a stable code or external reference.'))


def snapshot(record, names):
    result = {}
    for name in names:
        if name not in record._fields:
            continue
        value = record[name]
        result[name] = reference(value) if record._fields[name].type == 'many2one' else value
    return result


class Sale(models.Model):
    _inherit = 'ab_sales_header'


    inventory_sync_state = fields.Selection([
        ('pending', 'Inventory pending synchronization'), ('checking', 'Checking central confirmation'),
        ('posted', 'Posted centrally'), ('rejected', 'Inventory rejected')],
        string='Inventory Synchronization', compute='_compute_inventory_sync')
    central_bill_id = fields.Integer(string='Central Bill Reference', compute='_compute_inventory_sync')
    inventory_sync_message = fields.Text(string='Inventory Synchronization Details', compute='_compute_inventory_sync')

    def _compute_inventory_sync(self):
        operations = self.env['ab_branch_sync_operation'].sudo().with_context(active_test=False).search(
            fields.Domain('document_model', '=', self._name) & fields.Domain('document_id', 'in', self.ids)
            & fields.Domain('kind', '=', 'sale') & fields.Domain('direction', '=', 'out'))
        by_document = {op.document_id: op for op in operations}
        for sale in self:
            op = by_document.get(sale.id)
            sale.inventory_sync_state = ({'accepted': 'posted', 'rejected': 'rejected', 'uncertain': 'checking'}.get(op.state, 'pending') if op else False)
            sale.central_bill_id = ((op.result or {}).get('result') or {}).get('id', 0) if op else 0
            sale.inventory_sync_message = op.error if op else False

    def _central_snapshot(self):
        self.ensure_one()
        return {'stock_basis': 'product_uom_reference', 'header': snapshot(self, HEADER), 'lines': [dict(snapshot(line, LINE),
            source_line=str(line.id), uom_factor=line.uom_id.factor,
            product_uom={'name': line.uom_id.name, 'type': line.uom_id.uom_type},
            amounts={name: line[name] for name in AMOUNTS if name in line._fields}) for line in self.line_ids.sorted('id')],
            'allocations': allocation_snapshot(self),
            'promotions': [reference(p) for p in self.applied_program_ids],
            'totals': {key: value for key, value in self.native_totals.items() if type(value) in (int, float)},
            'created_at': fields.Datetime.to_string(self.create_date),
            'net': self.native_totals.get('total_bill_net'), 'source_document': str(self.id)}

    def action_submit(self, request_token=None):
        was_submitted = self.native_submitted if len(self) == 1 else False
        journal = self.env['ab_branch_sync_operation']
        if len(self) == 1 and not was_submitted and journal._uses_central(self.store_id):
            # Refresh before approval when reachable; only transport outages permit fallback.
            codes = self.line_ids.product_id.mapped('code')
            try:
                info = journal._request('connection', {'origin': self.env['ir.config_parameter'].sudo().get_param('database.uuid')})
                if info.get('inventory_protocol') != 3:
                    raise ValidationError(_('Upgrade central to inventory protocol 3 before selling.'))
                for offset in range(0, len(codes), 200):
                    journal._refresh_snapshots(store_ids=self.store_id.ids, product_codes=codes[offset:offset + 200])
            except requests.HTTPError as error:
                if error.response is None or error.response.status_code < 500:
                    raise ValidationError(_('Central rejected the synchronization request.')) from error
            except requests.RequestException:
                pass
        result = super().action_submit(request_token=request_token)
        journal = self.env['ab_branch_sync_operation']
        if journal._uses_central(self.store_id, 'branch') and self.native_backend and not was_submitted and self.native_submitted:
            journal._enqueue(self, 'sale', self._central_snapshot())
        return result

    def _native_settled(self):
        pending = self.filtered(lambda sale: sale.status != 'saved')
        result = super()._native_settled()
        for sale in pending:
            self.env['ab_branch_sync_operation']._enqueue(sale, 'sale_settle', {'source_document': str(sale.id)})
        return result

    def action_cancel_native(self, reason):
        was_cancelled = self.status == 'cancelled'
        result = super().action_cancel_native(reason)
        if not was_cancelled:
            self.env['ab_branch_sync_operation']._enqueue(self, 'sale_cancel',
                {'source_document': str(self.id), 'reason': reason})
        return result


class Return(models.Model):
    _inherit = 'ab_sales_return_header'

    def _validate_invoice_return_window(self, sth_id, sec_insert_date=None):
        journal = self.env['ab_branch_sync_operation']
        if journal._uses_central(self.store_id, 'branch') and self.native_origin_id:
            parent = journal.sudo().with_context(active_test=False).search(
                fields.Domain('direction', '=', 'out') & fields.Domain('kind', '=', 'sale')
                & fields.Domain('store_id', '=', self.store_id.id)
                & fields.Domain('document_id', '=', self.native_origin_id.id)
                & fields.Domain('origin', '=', self.env['ir.config_parameter'].sudo().get_param('database.uuid')), limit=1)
            if not parent:
                raise ValidationError(_('Historical returns require a reviewed original transaction import.'))
        return super()._validate_invoice_return_window(sth_id, sec_insert_date)


    def action_set_pending(self):
        pending = self.filtered(lambda rec: rec.native_origin_id and rec.status == 'prepending')
        result = super().action_set_pending()
        journal = self.env['ab_branch_sync_operation']
        if journal._param('role') == 'branch':
            for rec in pending:
                journal._enqueue(rec, 'return', {'source_document': str(rec.id),
                    'source_sale': str(rec.native_origin_id.id), 'net': rec.native_refund,
                    'lines': [{'source_line': str(line.native_origin_line_id.id), 'qty_str': line.qty_str,
                               'uom_factor': line.uom_id.factor} for line in rec.line_ids if line.qty > 0]})
        return result

    def _native_settled(self):
        pending = self.filtered(lambda rec: rec.status != 'saved')
        result = super()._native_settled()
        for rec in pending:
            self.env['ab_branch_sync_operation']._enqueue(rec, 'return_settle', {'source_document': str(rec.id)})
        return result


class POSInventoryStatus(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    def _branch_stock_feedback(self, header):
        if (not header.native_submitted or header.status not in ('pending', 'saved')
                or not self.env['ab_branch_sync_operation']._uses_central(header.store_id)):
            return {}
        # Read the snapshot minus durable local reservations after enqueueing.
        # No central request: this must also work while central is offline.
        return {'branch_stock': {
            'store_id': header.store_id.id,
            'balances': self.pos_refresh_pos_balances(
                header.store_id.id, header.line_ids.product_id.ids,
                include_sync_metadata=True),
        }}

    @api.model
    def _pos_submit_response(self, header, apply_submit=True):
        result = super()._pos_submit_response(header, apply_submit=apply_submit)
        if isinstance(result, dict):
            result.update(self._branch_stock_feedback(header))
        return result

    @api.model
    def _pos_submission_payload(self, header):
        result = super()._pos_submission_payload(header)
        if self.env['ab_branch_sync_operation']._uses_central(header.store_id):
            result.update(inventory_sync_state=header.inventory_sync_state,
                          central_bill_id=header.central_bill_id,
                          inventory_sync_message=header.inventory_sync_message or '')
            result.update(self._branch_stock_feedback(header))
        return result
