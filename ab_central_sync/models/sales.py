"""Capture native lifecycle events; replay through the same business methods."""
import math
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

    def _promotion_eligibility_replica(self, program):
        origin = REPLAY_ORIGIN.get()
        if origin:
            replica = self.env['ab_replica_db'].sudo().search(fields.Domain([('db_serial', '=', origin.get('promotion_replica_serial') or origin['replica_serial']), ('active', '=', True)]), limit=2)
            if len(replica) != 1:
                raise ValidationError(_('The originating replica must be configured on central.'))
            return replica
        return super()._promotion_eligibility_replica(program)


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


class Replay(models.Model):
    _inherit = 'ab_central_sync_operation'

    def _check_sale_reconciliation(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can reconcile rejected sales.'))
        self.check_access('write')
        if (self._param('role') != 'central' or self.direction != 'in'
                or self.kind != 'sale' or self.state != 'rejected'):
            raise ValidationError(_('Select a rejected incoming sale on central.'))

    def action_open_sale_reconciliation(self):
        self._check_sale_reconciliation()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reconcile Rejected Sale'),
            'res_model': 'ab_central_sync_sale_reconciliation',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_operation_id': self.id},
        }

    def _reconcile_posted_sale(self, sale, reason):
        """Bind reviewed posting evidence without replaying or skipping stock.

        Batch sources/costs may differ from the offline reservation, but the
        customer's agreement and per-line stock quantities must still match.
        The replacement must be pending so queued settlement/cancellation keeps
        its original actor and exactly-once business behavior.
        """
        self._check_sale_reconciliation()
        sale.ensure_one()
        sale.check_access('read')
        reason = (reason or '').strip()
        if not reason or len(reason) > 2000:
            raise ValidationError(_('Enter a reconciliation reason of at most 2,000 characters.'))
        self.store_id._lock_stock_scope()
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        self._check_sale_reconciliation()
        sale.lock_for_update(allow_referencing=True)
        sale.invalidate_recordset()
        sale.line_ids.invalidate_recordset()
        if (sale.store_id != self.store_id or not sale.native_backend
                or not sale.native_submitted or not sale.native_posted or sale.status != 'pending'):
            raise ValidationError(_('Select a posted, unsettled native sale in the same store.'))
        journal = self.sudo().with_context(active_test=False)
        previous = journal.search_count(fields.Domain('direction', '=', 'in')
            & fields.Domain('origin', '=', self.origin) & fields.Domain('store_id', '=', self.store_id.id)
            & fields.Domain('serial', '<', self.serial) & fields.Domain('state', '=', 'accepted'))
        if self.payload.get('version') != 3 and previous != self.serial - 1:
            raise ValidationError(_('Earlier process serials must be accepted first.'))
        if journal.search_count(fields.Domain('direction', '=', 'in')
                & fields.Domain('kind', '=', 'sale') & fields.Domain('document_model', '=', sale._name)
                & fields.Domain('document_id', '=', sale.id), limit=1):
            raise ValidationError(_('This central sale already belongs to a synchronization operation.'))
        if (self.env['ab_sales_native_payment'].sudo().search_count(fields.Domain('sale_id', '=', sale.id), limit=1)
                or self.env['ab_sales_return_header'].sudo().with_context(active_test=False).search_count(
                    fields.Domain('native_origin_id', '=', sale.id), limit=1)):
            raise ValidationError(_('The reconciliation sale must have no payments or returns.'))
        sale._validate_native_approval()
        mapping = self._match_reconciliation_sale(sale)
        now = fields.Datetime.now()
        allocations = self.env['ab_sales_stock_allocation'].sudo().search(
            fields.Domain('sale_line_id.header_id', '=', sale.id) & fields.Domain('return_line_id', '=', False))
        self.sudo().write({
            'state': 'accepted', 'accepted_at': now, 'error': False,
            'document_model': sale._name, 'document_id': sale.id,
            'result': {'model': sale._name, 'id': sale.id, 'lines': mapping, 'reconciled': True},
            'resolution_reason': reason, 'resolved_by_id': self.env.uid, 'resolved_at': now,
            'resolution_evidence': {
                'payload_hash': self.payload_hash, 'previous_error': self.error,
                'branch_reservations': self.payload['cache_reservations'],
                'central_allocations': [{'line': a.sale_line_id.id, 'source_id': a.source_id.id,
                    'qty': a.qty_smallest, 'price': a.source_unit_price, 'cost': a.unit_cost,
                    'movement_id': a.inventory_movement_id.id} for a in allocations],
            },
            'history': ((self.history or []) + [{'at': str(now), 'state': 'accepted',
                'resolution': 'posted_sale', 'user_id': self.env.uid, 'sale_id': sale.id}])[-50:],
        })
        return True

    def _match_reconciliation_sale(self, sale):
        payload = self.payload

        def matches(actual, expected):
            if type(expected) in (int, float):
                return (type(actual) in (int, float) and math.isfinite(actual)
                        and math.isfinite(expected) and abs(actual - expected) <= 0.0001)
            return (actual or False) == (expected or False)

        def check_values(record, values):
            return all(matches(record[name].id if record._fields[name].type == 'many2one'
                               else record[name], value) for name, value in values.items())

        header = self._values('ab_sales_header', payload['header'], HEADER)
        programs = [self._resolve('ab_promo_program', ref) for ref in payload['promotions']]
        if not check_values(sale, header) or set(sale.applied_program_ids.ids) != set(programs):
            raise ValidationError(_('The reconciliation sale must match the original customer, header and promotions.'))
        lines = sale.line_ids.sorted('id')
        source_lines = payload['lines']
        reservations = {item['source_line']: item['batches'] for item in payload['cache_reservations']}
        if (len(lines) != len(source_lines) or len({item['source_line'] for item in source_lines}) != len(lines)
                or set(reservations) != {item['source_line'] for item in source_lines}):
            raise ValidationError(_('The reconciliation sale must contain the original lines in the original order.'))
        mapping = {}
        for line, item in zip(lines, source_lines):
            values = self._values('ab_sales_line', {k: v for k, v in item.items() if k in LINE}, LINE)
            if (not check_values(line, values) or not matches(line.uom_id.factor, item['uom_factor'])
                    or any(not matches(line[name], amount) for name, amount in item['amounts'].items() if name in AMOUNTS)
                    or (not line.product_id.is_service and not matches(line.native_stock_qty,
                        sum(batch['qty'] for batch in reservations[item['source_line']])))):
                raise ValidationError(_('Reconciled lines must preserve products, units, quantities, prices, discounts and stock deductions.'))
            mapping[item['source_line']] = line.id
        totals = {key: value for key, value in sale.native_totals.items() if type(value) in (int, float)}
        if (totals.keys() != payload['totals'].keys()
                or any(not matches(totals[key], value) for key, value in payload['totals'].items())
                or not matches(sale.native_totals['total_bill_net'], payload['net'])):
            raise ValidationError(_('Central totals differ from the agreed branch totals.'))
        return mapping

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

    def _dependency_pending(self):
        self.ensure_one()
        if self.kind == 'sale':
            return False
        kind = 'return' if self.kind == 'return_settle' else 'sale'
        source = self.payload.get('source_sale') if self.kind == 'return' else self.payload.get('source_document')
        try:
            self._parent(kind, source)
            if self.kind == 'return':
                self._parent('sale_settle', source)
        except ValidationError:
            return True
        return False

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
                unit_domain = fields.Domain('category_id', '=', product.uom_category_id.id) & fields.Domain('factor', '=', item['uom_factor'])
                if item.get('product_uom'):
                    identity = item['product_uom']
                    if not isinstance(identity, dict) or set(identity) != {'name', 'type'}:
                        raise ValidationError(_('Invalid product unit identity.'))
                    unit_domain &= fields.Domain('name', '=', identity['name']) & fields.Domain('uom_type', '=', identity['type'])
                unit = env['ab_product_uom'].search(unit_domain, limit=2)
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
            expected = sorted((mapping[item['source_line']], batch['source_id'], batch['qty'],
                               round(batch['price'], 6), round(batch['cost'], 6))
                              for item in payload['cache_reservations'] for batch in item['batches'])
            actual = env['ab_sales_stock_allocation'].sudo().search(fields.Domain([('sale_line_id.header_id', '=', sale.id), ('return_line_id', '=', False)]))
            observed = sorted((a.sale_line_id.id, a.source_id.id, a.qty_smallest,
                               round(a.source_unit_price, 6), round(a.unit_cost, 6)) for a in actual)
            if payload.get('version') == 3:
                expected = sorted((mapping[item['source_line']], sum(batch['qty'] for batch in item['batches']))
                                  for item in payload['cache_reservations'])
                observed = sorted((line_id, sum(a.qty_smallest for a in actual if a.sale_line_id.id == line_id))
                                  for line_id in mapping.values())
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
            document._native_settled() if payload.get('version') == 3 else env['ab_sales_native_payment']._settle(document)
        elif self.kind == 'return_settle':
            document._native_settled() if payload.get('version') == 3 else env['ab_sales_native_payment']._settle(document.native_origin_id, document)
        else:
            raise ValidationError(_('Unsupported synchronization operation.'))
        return {'model': document._name, 'id': document.id}
