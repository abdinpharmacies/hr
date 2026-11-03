"""Capture native lifecycle events; replay through the same business methods."""
import uuid
from contextvars import ContextVar

REPLAY_ORIGIN = ContextVar("central_sync_origin", default=None)

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

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

    def _promotion_eligibility_replica(self, program):
        origin = REPLAY_ORIGIN.get()
        if origin:
            replica = self.env['ab_replica_db'].sudo().search(fields.Domain([('db_serial', '=', origin['replica_serial']), ('active', '=', True)]), limit=2)
            if len(replica) != 1:
                raise ValidationError(_('The originating replica must be configured on central.'))
            return replica
        return super()._promotion_eligibility_replica(program)

    def _central_snapshot(self):
        self.ensure_one()
        return {'header': snapshot(self, HEADER), 'lines': [dict(snapshot(line, LINE),
            source_line=str(line.id), uom_factor=line.uom_id.factor,
            amounts={name: line[name] for name in AMOUNTS if name in line._fields}) for line in self.line_ids.sorted('id')],
            'allocations': allocation_snapshot(self),
            'promotions': [reference(p) for p in self.applied_program_ids],
            'totals': {key: value for key, value in self.native_totals.items() if type(value) in (int, float)},
            'created_at': fields.Datetime.to_string(self.create_date),
            'net': self.native_totals.get('total_bill_net'), 'source_document': str(self.id)}

    def action_submit(self, request_token=None):
        was_submitted = self.native_submitted if len(self) == 1 else False
        result = super().action_submit(request_token=request_token)
        journal = self.env['ab_central_sync_operation']
        if journal._param('role') == 'branch' and self.native_backend and not was_submitted and self.native_submitted:
            journal._enqueue(self, 'sale', self._central_snapshot())
        return result

    def _native_settled(self):
        pending = self.filtered(lambda sale: sale.status != 'saved')
        result = super()._native_settled()
        for sale in pending:
            self.env['ab_central_sync_operation']._enqueue(sale, 'sale_settle', {'source_document': str(sale.id)})
        return result

    def action_cancel_native(self, reason):
        was_cancelled = self.status == 'cancelled'
        result = super().action_cancel_native(reason)
        if not was_cancelled:
            self.env['ab_central_sync_operation']._enqueue(self, 'sale_cancel',
                {'source_document': str(self.id), 'reason': reason})
        return result


class Return(models.Model):
    _inherit = 'ab_sales_return_header'

    def _validate_invoice_return_window(self, sth_id, sec_insert_date=None):
        origin = REPLAY_ORIGIN.get()
        if not origin:
            return super()._validate_invoice_return_window(sth_id, sec_insert_date)
        self.ensure_one()
        parent = self.env['ab_central_sync_operation'].sudo().with_context(active_test=False).search(fields.Domain([
            ('direction', '=', 'in'), ('origin', '=', origin['origin']),
            ('store_id', '=', self.store_id.id), ('kind', '=', 'sale'),
            ('document_id', '=', self.native_origin_id.id), ('state', '=', 'accepted')]), limit=1)
        replica = self.env['ab_replica_db'].sudo().search(fields.Domain([('db_serial', '=', origin['replica_serial']), ('active', '=', True)]), limit=2)
        if not parent or len(replica) != 1:
            raise ValidationError(_('The original sale and originating replica must be available.'))
        if replica._is_invoice_excluded_from_return_window(int(parent.payload['source_document'])):
            return
        created = fields.Datetime.to_datetime(parent.payload['created_at'])
        occurred = fields.Datetime.to_datetime(origin['occurred_at'])
        age = (fields.Datetime.context_timestamp(self, occurred).date() - fields.Datetime.context_timestamp(self, created).date()).days
        if age < 0 or age > max(1, int(replica.return_allowed_days or 14)):
            raise ValidationError(_('The return exceeds the originating branch return period.'))


    def action_set_pending(self):
        pending = self.filtered(lambda rec: rec.native_origin_id and rec.status == 'prepending')
        result = super().action_set_pending()
        journal = self.env['ab_central_sync_operation']
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
            self.env['ab_central_sync_operation']._enqueue(rec, 'return_settle', {'source_document': str(rec.id)})
        return result


class Replay(models.Model):
    _inherit = 'ab_central_sync_operation'

    @api.model
    def _resolve(self, model, value):
        if not value:
            return False
        if not isinstance(value, dict) or len(value) != 1:
            raise ValidationError(_('Invalid master reference.'))
        key, identifier = next(iter(value.items()))
        Model = self.env[model]
        if key == 'xmlid':
            module, name = identifier.split('.', 1)
            records = self.env['ir.model.data'].sudo().search(fields.Domain([('module', '=', module), ('name', '=', name), ('model', '=', model)]), limit=2)
            record = Model.browse(records.res_id) if len(records) == 1 else Model.browse()
        elif key in ('eplus_serial', 'code', 'accid') and key in Model._fields:
            record = Model.search(fields.Domain([(key, '=', identifier)]), limit=2)
        else:
            raise ValidationError(_('Unsupported master reference.'))
        if len(record) != 1:
            raise ValidationError(_('Master reference is missing or ambiguous.'))
        record.check_access('read')
        return record.id

    @api.model
    def _values(self, model, source, allowed):
        if not isinstance(source, dict) or set(source) - set(allowed):
            raise ValidationError(_('Unsupported synchronized fields.'))
        result = {}
        for name, value in source.items():
            field = self.env[model]._fields[name]
            result[name] = self._resolve(field.comodel_name, value) if field.type == 'many2one' else value
        return result

    def _parent(self, kind, source):
        candidates = self.sudo().with_context(active_test=False).search(fields.Domain([('direction', '=', 'in'), ('origin', '=', self.origin),
            ('store_id', '=', self.store_id.id), ('kind', '=', kind), ('state', '=', 'accepted'),
            ('source_document', '=', source)]), limit=2)
        parent = candidates
        if len(parent) != 1:
            raise ValidationError(_('The original operation must be accepted first.'))
        return parent

    def _apply(self, actor):
        self.ensure_one()
        payload = self.payload
        env = actor.env
        if not env['ab_sales_backend']._is_native(self.store_id.id):
            raise ValidationError(_('Central synchronization requires native inventory for this store.'))
        if self.kind == 'sale':
            vals = self.with_env(env)._values('ab_sales_header', payload['header'], HEADER)
            central_token = str(uuid.uuid5(uuid.UUID(self.origin), self.token))
            vals.update(store_id=self.store_id.id, pos_client_token=central_token)
            sale = env['ab_sales_header'].create(vals)
            mapping = {}
            if not payload['lines'] or len({item['source_line'] for item in payload['lines']}) != len(payload['lines']):
                raise ValidationError(_('Synchronized sale lines must have distinct original references.'))
            for item in payload['lines']:
                vals = self.with_env(env)._values('ab_sales_line', {k: v for k, v in item.items() if k in LINE}, LINE)
                product = env['ab_product'].browse(vals['product_id'])
                unit = env['ab_product_uom'].search(fields.Domain([('category_id', '=', product.uom_category_id.id), ('factor', '=', item['uom_factor'])]), limit=2)
                if len(unit) != 1:
                    raise ValidationError(_('The synchronized unit is missing or ambiguous.'))
                vals.update(header_id=sale.id, uom_id=unit.id)
                env['ab_sales_pos_api']._pos_fill_inventory_json_for_price_validation(sale, vals)
                line = env['ab_sales_line'].create(vals)
                mapping[item['source_line']] = line.id
            programs = [self.with_env(env)._resolve('ab_promo_program', ref) for ref in payload['promotions']]
            if programs:
                sale.applied_program_ids = [fields.Command.set(programs)]
                sale.btn_apply_promotion()
                if set(sale.applied_program_ids.ids) != set(programs):
                    raise ValidationError(_('The agreed promotion is no longer eligible.'))
            sale.action_submit(request_token=central_token)
            expected = sorted((mapping[a['line']], self.with_env(env)._resolve('ab_product_source', a['source']), a['quantity'], round(a['price'], 6), round(a['cost'], 6)) for a in payload['allocations'])
            actual = env['ab_sales_stock_allocation'].sudo().search(fields.Domain([('sale_line_id.header_id', '=', sale.id), ('return_line_id', '=', False)]))
            observed = sorted((a.sale_line_id.id, a.source_id.id, a.qty_smallest, round(a.unit_price, 6), round(a.unit_cost, 6)) for a in actual)
            if expected != observed:
                raise ValidationError(_('Central allocations differ from the original branch allocations.'))
            for item in payload['lines']:
                line = env['ab_sales_line'].browse(mapping[item['source_line']])
                if (line.qty_str != item['qty_str'] or abs(line.sell_price - item['sell_price']) > 0.0001
                        or any(abs(line[name] - amount) > 0.0001 for name, amount in item['amounts'].items() if name in AMOUNTS)):
                    raise ValidationError(_('Central sale lines differ from the agreed branch sale.'))
            totals = {key: value for key, value in sale.native_totals.items() if type(value) in (int, float)}
            if (totals.keys() != payload['totals'].keys() or any(abs(totals[key] - value) > 0.0001 for key, value in payload['totals'].items())
                    or abs(sale.native_totals['total_bill_net'] - payload['net']) > 0.0001):
                raise ValidationError(_('Central totals differ from the agreed branch totals.'))
            return {'model': sale._name, 'id': sale.id, 'lines': mapping}
        if self.kind == 'return':
            parent = self._parent('sale', payload['source_sale'])
            sale = env['ab_sales_header'].browse(parent.result['id'])
            ret = env['ab_sales_return_header'].create({'store_id': sale.store_id.id, 'native_origin_id': sale.id})
            ret.action_load_lines()
            for item in payload['lines']:
                original_id = parent.result['lines'].get(item['source_line'])
                line = ret.line_ids.filtered(lambda line: line.native_origin_line_id.id == original_id)
                if len(line) != 1 or line.uom_id.factor != item['uom_factor']:
                    raise ValidationError(_('Return allocation or unit does not match the original sale.'))
                line.qty_str = item['qty_str']
            ret.action_set_pending()
            if abs(ret.native_refund - payload['net']) > 0.0001:
                raise ValidationError(_('Central refund differs from the agreed branch refund.'))
            return {'model': ret._name, 'id': ret.id}
        kind = 'return' if self.kind == 'return_settle' else 'sale'
        parent = self._parent(kind, payload['source_document'])
        document = env[parent.result['model']].browse(parent.result['id'])
        if self.kind == 'sale_cancel':
            document.action_cancel_native(payload['reason'])
        elif self.kind == 'sale_settle':
            env['ab_sales_native_payment']._settle(document)
        elif self.kind == 'return_settle':
            env['ab_sales_native_payment']._settle(document.native_origin_id, document)
        else:
            raise ValidationError(_('Unsupported synchronization operation.'))
        return {'model': document._name, 'id': document.id}
