import hashlib
import json
import math
from decimal import Decimal

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from .ab_inventory import AbInventory
from .stock_state import LOCATIONS


def add_qty(left, right):
    return float(Decimal(str(left)) + Decimal(str(right)))


class InventoryProcess(models.AbstractModel):
    _name = 'ab_inventory_process'
    _description = 'Inventory Integration Helper'

    def _is_manager(self):
        return self.env.user.has_group('base.group_system') or self.env.user.has_group('ab_inventory.group_inventory_manager')

    def _require_manager(self):
        if not self._is_manager():
            raise AccessError(_('Only inventory managers can post movements.'))

    def _require_operator(self):
        if not (self._is_manager() or self.env.user.has_group('ab_inventory.group_inventory_operator')):
            raise AccessError(_('Inventory operation access is required.'))

    def _check_store(self, store_id):
        if isinstance(store_id, bool) or not isinstance(store_id, int):
            raise ValidationError(_('Select a valid store.'))
        store = self.env['ab_store'].browse(store_id).exists()
        store.check_access('read')
        if not store or not store.active:
            raise ValidationError(_('Select a valid store.'))
        if store.company_id not in self.env.companies:
            raise AccessError(_('The store belongs to a company outside your allowed companies.'))
        if not self._is_manager() and store not in self.env.user.inventory_store_ids:
            raise AccessError(_("You are not allowed to access this store's inventory."))
        return store

    def _lock_store(self, store):
        store._lock_stock_scope()

    def _key(self, key):
        if not isinstance(key, str) or not key.strip() or len(key) > 200:
            raise ValidationError(_('Provide a non-empty operation key of at most 200 characters.'))
        return key

    def _positive_quantity(self, qty):
        if isinstance(qty, bool) or not isinstance(qty, (int, float)) or not math.isfinite(qty) or qty <= 0:
            raise ValidationError(_('Stock operation quantities must be finite and positive.'))
        return float(qty)

    def _product(self, product_id, qty=None):
        product = self.env['ab_product'].browse(product_id).exists()
        product.check_access('read')
        if not product or not product.active:
            raise ValidationError(_('Select an active stock product.'))
        if qty is not None:
            product._validate_stock_quantity(qty)
        return product

    def _balances(self, store, product_id=None, source_id=None, location=None):
        domain = [('store_id', '=', store.id), ('company_id', '=', store.company_id.id)]
        if product_id:
            domain.append(('product_id', '=', product_id))
        if source_id:
            domain.append(('source_id', '=', source_id))
        if location:
            domain.append(('location', '=', location))
        return self.env['ab_inventory_balance'].search(domain)

    def get_balance(self, store_id, product_id=None, source_id=None, before=None):
        store = self._check_store(store_id)
        if before:
            domain = [('store_id', '=', store.id), ('status', '=', 'saved'), ('saved_at', '<', before)]
            if product_id:
                domain.append(('product_id', '=', product_id))
            if source_id:
                domain.append(('source_id', '=', source_id))
            return sum(row[0] for row in self.env['ab_inventory']._read_group(domain, [], ['qty:sum']))
        return sum(self._balances(store, product_id, source_id).mapped('on_hand'))

    def get_source_balances(self, store_id, product_id=None, before=None, include_zero=False):
        store = self._check_store(store_id)
        domain = [('store_id', '=', store.id), ('source_id', '!=', False)]
        if product_id:
            domain.append(('product_id', '=', product_id))
        if before:
            domain.extend([('status', '=', 'saved'), ('saved_at', '<', before)])
            rows = self.env['ab_inventory']._read_group(domain, ['source_id'], ['qty:sum'])
        else:
            rows = self.env['ab_inventory_balance']._read_group(domain, ['source_id'], ['on_hand:sum'])
        return {source.id: qty for source, qty in rows if qty or include_zero}

    def _latest_movements_by_source(self, store_id, product_id=None, before=None, source_ids=None):
        store = self._check_store(store_id)
        domain = [('store_id', '=', store.id), ('status', '=', 'saved')]
        if product_id:
            domain.append(('product_id', '=', product_id))
        if source_ids is not None:
            domain.append(('source_id', 'in', source_ids))
        if before:
            domain.append(('saved_at', '<', before))
        seen = set()
        ids = []
        for movement in self.env['ab_inventory'].search(domain, order='posting_sequence desc'):
            if movement.source_id.id not in seen:
                seen.add(movement.source_id.id)
                ids.append(movement.id)
        return self.env['ab_inventory'].browse(ids)

    def _smallest_unit_qty(self, rec, qty, sign):
        if isinstance(sign, bool) or sign not in (-1, 1):
            raise ValidationError(_('Inventory direction must be +1 or -1.'))
        if isinstance(qty, bool) or not isinstance(qty, (int, float)) or not math.isfinite(qty) or qty <= 0:
            raise ValidationError(_('Inventory quantity must be positive.'))
        return sign * rec.source_id._to_stock_quantity(qty)

    @api.private
    def inventory_write(self, rec, qty, store_id, inventory_line=None, status='saved', sign=1):
        self._require_manager()
        if not isinstance(rec, models.BaseModel) or len(rec) != 1 or not isinstance(rec.id, int):
            raise ValidationError(_('Provide one saved business line for inventory.'))
        if rec._name not in ('ab_purchase_line', 'ab_purchase_notice_line', 'ab_purchase_ob_line'):
            raise ValidationError(_('Unsupported inventory business document.'))
        if status not in ('pending', 'saved'):
            raise ValidationError(_('Inventory status must be Pending or Saved.'))
        rec.check_access('read')
        store = self._check_store(store_id)
        if rec.header_id.store_id != store:
            raise ValidationError(_('The business document and inventory store must match.'))
        source = rec.source_id
        source.check_access('read')
        with self.env.cr.savepoint():
            self._lock_store(store)
            source.lock_for_update(allow_referencing=True)
            source.invalidate_recordset()
            if not source.store_id:
                source._bind_origin(store, rec._name, rec.id, 'purchase' if rec._name == 'ab_purchase_line' else 'opening' if rec._name == 'ab_purchase_ob_line' else 'adjustment')
            if source.store_id != store or source.company_id != store.company_id:
                raise ValidationError(_('The stock source must match the movement product, store and company.'))
            source._lock_inventory_inputs()
            movement_qty = self._smallest_unit_qty(rec, qty, sign)
            key = '%s:%s' % (rec._name, rec.id)
            movement = self.env['ab_inventory'].sudo().search([('store_id', '=', store.id), ('operation_key', '=', key)], limit=1)
            if inventory_line and inventory_line.id != movement.id:
                raise ValidationError(_('The inventory line does not match the business line.'))
            values = {'store_id': store.id, 'source_id': source.id, 'product_id': source.product_id.id,
                      'qty': movement_qty, 'model_ref': rec._name, 'res_id': rec.id,
                      'document_model': rec._name, 'operation_key': key,
                      'business_date': rec.header_id.doc_date or fields.Date.context_today(self)}
            if movement.status == 'saved':
                if movement.qty != movement_qty or movement.source_id != source or status != 'saved':
                    raise ValidationError(_('A repeated stock operation must have identical inputs.'))
                return movement.with_env(self.env)
            if movement:
                super(AbInventory, movement).write(values)
            else:
                movement = super(AbInventory, self.env['ab_inventory'].sudo()).create(values)
            if status == 'saved':
                self._post(movement, require_manager=False)
            return movement.with_env(self.env)

    def _balance_for(self, store, product, source=None, location='saleable'):
        source = source or self.env['ab_product_source']
        key = source.source_identity if source else 'shortage'
        if not key:
            raise ValidationError(_('A stable source identity is required before posting stock.'))
        model = self.env['ab_inventory_balance']
        row = model.sudo().search([('store_id', '=', store.id), ('company_id', '=', store.company_id.id), ('product_id', '=', product.id), ('location', '=', location), ('layer_key', '=', key)], limit=1)
        if not row:
            row = model._create_state({'store_id': store.id, 'company_id': store.company_id.id, 'product_id': product.id, 'source_id': source.id or False, 'location': location, 'layer_key': key})
        row.invalidate_recordset()
        return row

    def _next_sequence(self, store):
        model = self.env['ab_inventory_posting_sequence']
        seq = model.sudo().search([('store_id', '=', store.id), ('company_id', '=', store.company_id.id)], limit=1)
        if not seq:
            seq = model._create_state({'store_id': store.id, 'company_id': store.company_id.id})
        seq.invalidate_recordset()
        revision = seq.revision + 1
        seq._write_state({'revision': revision})
        return revision

    def _post(self, movements, require_manager=True, reconcile=True):
        if require_manager:
            self._require_manager()
        with self.env.cr.savepoint():
            for store in movements.mapped('store_id').sorted('id'):
                self._check_store(store.id)
                self._lock_store(store)
            movements.lock_for_update(allow_referencing=True)
            movements.invalidate_recordset()
            if any(rec.status != 'pending' for rec in movements):
                raise ValidationError(_('Only pending movements can be saved.'))
            sources = movements.mapped('source_id').sorted('id')
            sources.lock_for_update(allow_referencing=True)
            sources._lock_inventory_inputs()
            for rec in movements.sorted('id'):
                normalized_qty = rec.product_id._validate_stock_quantity(rec.qty)
                if normalized_qty != rec.qty:
                    super(AbInventory, rec).write({'qty': normalized_qty})
                source = rec.source_id
                if source:
                    source._check_posting_identity()
                    if source.store_id != rec.store_id or source.company_id != rec.company_id:
                        raise ValidationError(_('The stock source must match the movement product, store and company.'))
                    source._freeze_for_inventory(rec)
                row = self._balance_for(rec.store_id, rec.product_id, source, rec.location)
                closing = add_qty(row.on_hand, rec.qty)
                if source and closing < row.reserved - 0.000000001:
                    raise ValidationError(_('Posting would consume reserved stock or create negative physical stock.'))
                cost = source._convert_source_amount(source._get_purchase_tax_values()['stock_unit_cost'], 'small') if source else rec.unit_cost
                revision = self._next_sequence(rec.store_id)
                super(AbInventory, rec).write({'status': 'saved', 'saved_at': fields.Datetime.now(), 'ending_balance': closing,
                    'balance_id': row.id, 'posting_sequence': revision, 'unit_cost': cost, 'valuation': rec.qty * cost,
                    'conversion_snapshot': source._get_conversion_basis() if source else {}})
                row._write_state({'on_hand': closing, 'revision': revision, 'last_movement_id': rec.id})
                if reconcile and source and rec.qty > 0 and rec.location == 'saleable':
                    self._reconcile_shortages(rec)
        return True

    def _stock_change(self, store, product, source, qty, key, model_ref, document_model, document_id, location='saleable', unit_cost=0, reconcile=False):
        key = self._key(key)
        old = self.env['ab_inventory'].sudo().search([('store_id', '=', store.id), ('operation_key', '=', key)], limit=1)
        if old:
            if old.qty != qty or old.source_id != source or old.product_id != product or old.location != location or old.document_model != document_model or old.res_id != document_id or old.model_ref != model_ref:
                raise ValidationError(_('A repeated stock operation must have identical inputs.'))
            return old
        rec = super(AbInventory, self.env['ab_inventory'].sudo()).create({
            'store_id': store.id, 'product_id': product.id, 'source_id': source.id or False,
            'qty': qty, 'operation_key': key, 'model_ref': model_ref, 'document_model': document_model,
            'res_id': document_id, 'location': location, 'unit_cost': unit_cost,
        })
        self._post(rec, require_manager=False, reconcile=reconcile)
        return rec

    def source_stock(self, store_id, product_ids):
        store = self._check_store(store_id)
        products = self.env['ab_product'].browse(product_ids).exists()
        products.check_access('read')
        result = {product.id: [] for product in products}
        rows = self.env['ab_inventory_balance'].search([('store_id', '=', store.id), ('product_id', 'in', products.ids), ('location', '=', 'saleable'), ('source_id', '!=', False), ('on_hand', '>', 0)])
        today = fields.Date.context_today(self)
        for row in rows:
            source = row.source_id
            if not source.no_expiry and (not source.exp_date or source.exp_date < today):
                continue
            if row.available <= 0:
                continue
            result[row.product_id.id].append({'source_id': source.id, 'source_identity': source.source_identity,
                'qty': row.available, 'on_hand': row.on_hand, 'reserved': row.reserved,
                'price': source.convert_price('small'), 'cost': source._convert_source_amount(source._get_purchase_tax_values()['stock_unit_cost'], 'small'),
                'expiry': str(source.exp_date) if source.exp_date else False, 'no_expiry': source.no_expiry,
                'location': row.location})
        return result

    def available_stock(self, store_id, product_ids):
        store = self._check_store(store_id)
        result = {product: sum(row['qty'] for row in rows) for product, rows in self.source_stock(store.id, product_ids).items()}
        for row in self.env['ab_inventory_balance'].search([('store_id', '=', store.id), ('product_id', 'in', product_ids), ('source_id', '=', False), ('location', '=', 'saleable')]):
            result[row.product_id.id] = add_qty(result.get(row.product_id.id, 0), row.available)
        return result

    def reserve_stock(self, store_id, product_id, qty, operation_key, preferred_price=None, allow_shortage=False, reason=None):
        self._require_operator()
        qty = self._positive_quantity(qty)
        store = self._check_store(store_id)
        product = self._product(product_id, qty)
        qty = product._validate_stock_quantity(qty)
        operation_key = self._key(operation_key)
        if preferred_price is not None and (isinstance(preferred_price, bool) or not isinstance(preferred_price, (int, float)) or not math.isfinite(preferred_price) or preferred_price < 0):
            raise ValidationError(_('The requested stock price must be finite and non-negative.'))
        if allow_shortage and (not self._is_manager() and not self.env.user.has_group('ab_inventory.group_inventory_shortage')):
            raise AccessError(_('Shortage sales require explicit shortage authorization.'))
        if allow_shortage and not str(reason or '').strip():
            raise ValidationError(_('A shortage reason is required.'))
        fingerprint = hashlib.sha256(json.dumps([product.id, float(qty), float(preferred_price) if preferred_price is not None else None, bool(allow_shortage), reason or ''], sort_keys=True).encode()).hexdigest()
        with self.env.cr.savepoint():
            self._lock_store(store)
            model = self.env['ab_inventory_reservation']
            existing = model.search([('store_id', '=', store.id), ('operation_key', '=', operation_key)], limit=1)
            if existing:
                if existing.actor_id != self.env.user and not self._is_manager():
                    raise AccessError(_('Only the reservation owner or an inventory manager can change it.'))
                if existing.request_fingerprint != fingerprint or existing.state == 'released':
                    raise ValidationError(_('A repeated stock operation must have identical inputs.'))
                return existing
            options = self.source_stock(store.id, product.ids)[product.id]
            options.sort(key=lambda row: (preferred_price is not None and abs(row['price'] - preferred_price) > 0.000001, row['price'], row['expiry'] or '9999-12-31', row['source_id']))
            remaining = qty
            allocations = []
            for option in options:
                take = min(remaining, option['qty'])
                if take <= 0:
                    continue
                source = self.env['ab_product_source'].browse(option['source_id'])
                row = self._balance_for(store, product, source)
                row._write_state({'reserved': add_qty(row.reserved, take)})
                allocations.append({'source_id': source.id, 'qty': take, 'unit_cost': option['cost'], 'unit_price': option['price']})
                remaining = add_qty(remaining, -take)
                if remaining <= 0.000000001:
                    break
            if remaining > 0.000000001:
                if not allow_shortage:
                    raise ValidationError(_('There is not enough available saleable stock.'))
                price = preferred_price
                if price is None:
                    price = product.default_price / (product.unit_s_id.unit_no or 1)
                row = self._balance_for(store, product)
                row._write_state({'reserved': add_qty(row.reserved, remaining)})
                allocations.append({'source_id': False, 'qty': remaining, 'unit_cost': price * 0.85, 'unit_price': price, 'reason': str(reason)})
            reservation = model._create_state({'company_id': store.company_id.id, 'store_id': store.id, 'product_id': product.id,
                'operation_key': operation_key, 'request_fingerprint': fingerprint, 'qty': qty,
                'allocations': allocations, 'actor_id': self.env.uid})
            return reservation.with_env(self.env)

    def _reservation(self, store, operation_key, owner=True):
        reservation = self.env['ab_inventory_reservation'].search([('store_id', '=', store.id), ('operation_key', '=', self._key(operation_key))], limit=1)
        if not reservation:
            raise ValidationError(_('The stock reservation does not exist.'))
        if owner and reservation.actor_id != self.env.user and not self._is_manager():
            raise AccessError(_('Only the reservation owner or an inventory manager can change it.'))
        return reservation

    def release_reservation(self, operation_key, store_id):
        self._require_operator()
        store = self._check_store(store_id)
        with self.env.cr.savepoint():
            self._lock_store(store)
            reservation = self._reservation(store, operation_key)
            if reservation.state == 'released':
                return True
            if reservation.state != 'held':
                raise ValidationError(_('Posted stock reservations cannot be released.'))
            for allocation in reservation.allocations:
                row = self._balance_for(store, reservation.product_id, self.env['ab_product_source'].browse(allocation['source_id']))
                row._write_state({'reserved': add_qty(row.reserved, -allocation['qty'])})
            reservation._write_state({'state': 'released'})
        return True

    def _check_document(self, store, document_model, document_id, returning=False):
        names = ('ab_sales_return_line', 'ab_sales_return_header') if returning else ('ab_sales_line', 'ab_sales_header')
        if document_model not in names or document_model not in self.env:
            raise ValidationError(_('Unsupported native stock document.'))
        document = self.env[document_model].browse(document_id).exists()
        document.check_access('read')
        header = document.header_id if 'header_id' in document._fields else document
        if not document or header.store_id != store:
            raise ValidationError(_('The business document and inventory store must match.'))
        return document

    @api.private
    def post_reserved(self, operation_key, store_id, document_model, document_id):
        self._require_operator()
        store = self._check_store(store_id)
        document = self._check_document(store, document_model, document_id)
        with self.env.cr.savepoint():
            self._lock_store(store)
            reservation = self._reservation(store, operation_key)
            if 'product_id' in document._fields and document.product_id != reservation.product_id:
                raise ValidationError(_('The reserved product must match the business document.'))
            if reservation.state == 'posted':
                if reservation.document_model != document_model or reservation.document_id != document_id:
                    raise ValidationError(_('A repeated stock operation must have identical inputs.'))
                return reservation
            if reservation.state != 'held':
                raise ValidationError(_('Only held reservations can be posted.'))
            for index, allocation in enumerate(reservation.allocations):
                source = self.env['ab_product_source'].browse(allocation['source_id'])
                row = self._balance_for(store, reservation.product_id, source)
                if source and not source.no_expiry and source.exp_date < fields.Date.context_today(self):
                    raise ValidationError(_('Reserved stock has expired; release and allocate it again.'))
                row._write_state({'reserved': add_qty(row.reserved, -allocation['qty'])})
                self._stock_change(store, reservation.product_id, source, -allocation['qty'], operation_key + ':post:' + str(index), 'native', document_model, document_id, unit_cost=allocation['unit_cost'])
                if not source:
                    self.env['ab_inventory_shortage']._create_state({'company_id': store.company_id.id, 'store_id': store.id,
                        'product_id': reservation.product_id.id, 'reservation_id': reservation.id, 'quantity': allocation['qty'],
                        'remaining_qty': allocation['qty'], 'provisional_unit_cost': allocation['unit_cost'], 'reason': allocation['reason']})
            reservation._write_state({'state': 'posted', 'document_model': document_model, 'document_id': document_id})
            rows = self._balances(store, reservation.product_id.id).filtered(lambda row: row.source_id and row.location == 'saleable' and row.available > 0)
            for row in rows.sorted(lambda row: row.source_id.id):
                self._reconcile_shortages(row.last_movement_id, available_limit=row.available)
            return reservation

    def _reconcile_shortages(self, receipt, available_limit=None):
        store, source, product = receipt.store_id, receipt.source_id, receipt.product_id
        if not source.no_expiry and source.exp_date < fields.Date.context_today(self):
            return
        physical = self._balance_for(store, product, source)
        available = min(physical.available, receipt.qty if available_limit is None else available_limit)
        shortages = self.env['ab_inventory_shortage'].sudo().search([('store_id', '=', store.id), ('product_id', '=', product.id), ('remaining_qty', '>', 0)], order='id')
        for shortage in shortages:
            quantity = min(available, shortage.remaining_qty)
            if quantity <= 0.000000001:
                break
            cost = source._convert_source_amount(source._get_purchase_tax_values()['stock_unit_cost'], 'small')
            correction = self.env['ab_inventory_cost_correction']._create_state({
                'company_id': store.company_id.id, 'store_id': store.id, 'shortage_id': shortage.id,
                'source_id': source.id, 'receipt_movement_id': receipt.id, 'quantity': quantity,
                'provisional_unit_cost': shortage.provisional_unit_cost, 'actual_unit_cost': cost,
                'correction_amount': quantity * (cost - shortage.provisional_unit_cost),
            })
            key = 'shortage-settlement:%s' % correction.id
            self._stock_change(store, product, source, -quantity, key + ':physical', 'shortage', shortage._name, shortage.id)
            self._stock_change(store, product, self.env['ab_product_source'], quantity, key + ':deficit', 'shortage', shortage._name, shortage.id, unit_cost=shortage.provisional_unit_cost)
            shortage._write_state({'remaining_qty': add_qty(shortage.remaining_qty, -quantity)})
            available = add_qty(available, -quantity)

    def _restore_shortage(self, reservation, quantity):
        shortage = self.env['ab_inventory_shortage'].sudo().search([('reservation_id', '=', reservation.id)], limit=1)
        if not shortage:
            raise ValidationError(_('The original shortage allocation is missing.'))
        allocations = []
        pending = min(quantity, shortage.remaining_qty)
        if pending:
            allocations.append({'source_id': False, 'qty': pending, 'unit_cost': shortage.provisional_unit_cost})
            shortage._write_state({'remaining_qty': add_qty(shortage.remaining_qty, -pending)})
            quantity = add_qty(quantity, -pending)
        for correction in self.env['ab_inventory_cost_correction'].sudo().search([('shortage_id', '=', shortage.id)], order='id'):
            take = min(quantity, add_qty(correction.quantity, -correction.returned_qty))
            if take > 0:
                allocations.append({'source_id': correction.source_id.id, 'qty': take, 'unit_cost': correction.actual_unit_cost})
                correction._write_state({'returned_qty': add_qty(correction.returned_qty, take)})
                quantity = add_qty(quantity, -take)
            if quantity <= 0.000000001:
                break
        if quantity > 0.000000001:
            raise ValidationError(_('The original shortage allocation cannot cover this return.'))
        return allocations

    @api.private
    def return_allocations(self, store_id, operation_key, original_key, qty, document_model, document_id):
        qty = self._positive_quantity(qty)
        self._require_operator()
        store = self._check_store(store_id)
        document = self._check_document(store, document_model, document_id, returning=True)
        operation_key = self._key(operation_key)
        with self.env.cr.savepoint():
            self._lock_store(store)
            reservation = self._reservation(store, original_key, owner=False)
            if 'product_id' in document._fields and document.product_id != reservation.product_id:
                raise ValidationError(_('The reserved product must match the business document.'))
            qty = reservation.product_id._validate_stock_quantity(qty)
            model = self.env['ab_inventory_return_event']
            existing = model.search([('store_id', '=', store.id), ('operation_key', '=', operation_key)], limit=1)
            if existing:
                if existing.qty != qty or existing.reservation_id != reservation or existing.document_model != document_model or existing.document_id != document_id:
                    raise ValidationError(_('A repeated stock operation must have identical inputs.'))
                return existing
            if reservation.state != 'posted' or qty > add_qty(reservation.qty, -reservation.returned_qty) + 0.000000001:
                raise ValidationError(_('Returns cannot exceed the unreturned original stock allocation.'))
            skip = reservation.returned_qty
            remaining = qty
            allocations = []
            for original in reservation.allocations:
                available = max(0, add_qty(original['qty'], -skip))
                skip = max(0, add_qty(skip, -original['qty']))
                take = min(remaining, available)
                if take > 0:
                    if original['source_id']:
                        allocations.append({'source_id': original['source_id'], 'qty': take, 'unit_cost': original['unit_cost']})
                    else:
                        allocations.extend(self._restore_shortage(reservation, take))
                    remaining = add_qty(remaining, -take)
                if remaining <= 0.000000001:
                    break
            if remaining > 0.000000001:
                raise ValidationError(_('The original stock allocation is incomplete.'))
            for index, allocation in enumerate(allocations):
                self._stock_change(store, reservation.product_id, self.env['ab_product_source'].browse(allocation['source_id']), allocation['qty'],
                    operation_key + ':return:' + str(index), 'native_return', document_model, document_id, unit_cost=allocation['unit_cost'], reconcile=bool(allocation['source_id']))
            reservation._write_state({'returned_qty': add_qty(reservation.returned_qty, qty)})
            result = model._create_state({'company_id': store.company_id.id, 'store_id': store.id, 'reservation_id': reservation.id,
                'operation_key': operation_key, 'qty': qty, 'allocations': allocations,
                'document_model': document_model, 'document_id': document_id})
            return result.with_env(self.env)

    def transfer_location(self, store_id, source_id, qty, from_location, to_location, operation_key, reason):
        qty = self._positive_quantity(qty)
        self._require_manager()
        store = self._check_store(store_id)
        operation_key = self._key(operation_key)
        valid = {key for key, label in LOCATIONS}
        if from_location not in valid or to_location not in valid or from_location == to_location or not str(reason or '').strip():
            raise ValidationError(_('Select different valid stock locations and provide a reason.'))
        source = self.env['ab_product_source'].browse(source_id).exists()
        source.check_access('read')
        if not source or source.store_id != store:
            raise ValidationError(_('The source does not belong to this store.'))
        qty = source.product_id._validate_stock_quantity(qty)
        with self.env.cr.savepoint():
            self._lock_store(store)
            outgoing = self._stock_change(store, source.product_id, source, -qty, operation_key + ':out', 'location', 'ab_product_source', source.id, from_location)
            incoming = self._stock_change(store, source.product_id, source, qty, operation_key + ':in', 'location', 'ab_product_source', source.id, to_location, reconcile=to_location == 'saleable')
            if not self.env['ab_inventory_projection_repair'].sudo().search_count([('store_id', '=', store.id), ('reason', '=', 'Location: ' + operation_key)]):
                self.env['ab_inventory_projection_repair']._create_state({'company_id': store.company_id.id, 'store_id': store.id, 'actor_id': self.env.uid,
                    'reason': 'Location: ' + operation_key, 'changes': {'reason': str(reason), 'outgoing': outgoing.id, 'incoming': incoming.id}})
        return {'outgoing_id': outgoing.id, 'incoming_id': incoming.id}

    def check_integrity(self, store_id):
        store = self._check_store(store_id)
        ledger = {}
        errors = []
        last = {}
        sequence = 0
        movements = self.env['ab_inventory'].search([('store_id', '=', store.id), ('status', '=', 'saved')], order='posting_sequence,id')
        for movement in movements:
            key = (movement.product_id.id, movement.source_id.id or False, movement.location)
            ledger[key] = add_qty(ledger.get(key, 0), movement.qty)
            if abs(ledger[key] - movement.ending_balance) > 0.000000001 or movement.posting_sequence <= sequence:
                errors.append({'type': 'ledger', 'movement_id': movement.id, 'expected': ledger[key], 'actual': movement.ending_balance})
            sequence = movement.posting_sequence
            last[key] = movement
        reservations = {}
        for reservation in self.env['ab_inventory_reservation'].search([('store_id', '=', store.id), ('state', '=', 'held')]):
            for allocation in reservation.allocations:
                key = (reservation.product_id.id, allocation['source_id'] or False, 'saleable')
                reservations[key] = add_qty(reservations.get(key, 0), allocation['qty'])
        rows = self._balances(store)
        present = set()
        for row in rows:
            key = (row.product_id.id, row.source_id.id or False, row.location)
            present.add(key)
            qty, reserved = ledger.get(key, 0), reservations.get(key, 0)
            latest = last.get(key)
            if row.revision != (latest.posting_sequence if latest else 0) or row.last_movement_id.id != (latest.id if latest else False):
                errors.append({'type': 'projection_revision', 'balance_id': row.id})
            if abs(qty - row.on_hand) > 0.000000001 or abs(reserved - row.reserved) > 0.000000001:
                errors.append({'type': 'projection', 'balance_id': row.id, 'expected_on_hand': qty, 'actual_on_hand': row.on_hand, 'expected_reserved': reserved, 'actual_reserved': row.reserved})
        for key in (set(ledger) | set(reservations)) - present:
            errors.append({'type': 'missing_balance', 'product_id': key[0], 'source_id': key[1], 'location': key[2]})
        shortages = {product.id: quantity for product, quantity in self.env['ab_inventory_shortage']._read_group(
            [('store_id', '=', store.id)], ['product_id'], ['remaining_qty:sum'])}
        deficits = {}
        for (product_id, source_id, location), quantity in ledger.items():
            if not source_id:
                deficits[product_id] = add_qty(deficits.get(product_id, 0), quantity)
        for product_id in set(shortages) | set(deficits):
            if abs(deficits.get(product_id, 0) + shortages.get(product_id, 0)) > 0.000000001:
                errors.append({'type': 'shortage', 'product_id': product_id})
        counter = self.env['ab_inventory_posting_sequence'].search([('store_id', '=', store.id)], limit=1)
        if counter.revision != sequence:
            errors.append({'type': 'sequence', 'expected': sequence, 'actual': counter.revision})
        return {'store_id': store.id, 'consistent': not errors, 'movement_count': len(movements), 'balance_count': len(rows), 'errors': errors}

    def rebuild_projection(self, store_id, reason):
        self._require_manager()
        store = self._check_store(store_id)
        if not str(reason or '').strip():
            raise ValidationError(_('Provide a reason for rebuilding the inventory projection.'))
        with self.env.cr.savepoint():
            self._lock_store(store)
            report = self.check_integrity(store.id)
            if any(error['type'] in ('ledger', 'sequence', 'shortage') for error in report['errors']):
                raise ValidationError(_('Stored movement history is inconsistent; projection repair cannot rewrite it.'))
            balances = {}
            latest = {}
            for movement in self.env['ab_inventory'].search([('store_id', '=', store.id), ('status', '=', 'saved')], order='posting_sequence'):
                key = (movement.product_id.id, movement.source_id.id, movement.location)
                balances[key] = add_qty(balances.get(key, 0), movement.qty)
                latest[key] = movement
            reserved = {}
            for reservation in self.env['ab_inventory_reservation'].search([('store_id', '=', store.id), ('state', '=', 'held')]):
                for allocation in reservation.allocations:
                    key = (reservation.product_id.id, allocation['source_id'], 'saleable')
                    reserved[key] = add_qty(reserved.get(key, 0), allocation['qty'])
            changes = []
            keys = set(balances) | set(reserved) | {(row.product_id.id, row.source_id.id, row.location) for row in self._balances(store)}
            for key in sorted(keys, key=str):
                row = self._balance_for(store, self.env['ab_product'].browse(key[0]), self.env['ab_product_source'].browse(key[1]), key[2])
                values = {'on_hand': balances.get(key, 0), 'reserved': reserved.get(key, 0), 'revision': latest[key].posting_sequence if key in latest else 0, 'last_movement_id': latest[key].id if key in latest else False}
                if any((row[field].id if field == 'last_movement_id' else row[field]) != value for field, value in values.items()):
                    changes.append({'balance_id': row.id, 'before': {'on_hand': row.on_hand, 'reserved': row.reserved}, 'after': values})
                    row._write_state(values)
            if changes:
                self.env['ab_inventory_projection_repair']._create_state({'company_id': store.company_id.id, 'store_id': store.id, 'actor_id': self.env.uid, 'reason': str(reason), 'changes': changes})
            return self.check_integrity(store.id)
