from decimal import Decimal, InvalidOperation

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from .ab_inventory import AbInventory


class InventoryProcess(models.AbstractModel):
    _name = 'ab_inventory_process'
    _description = 'Inventory Integration Helper'

    @api.model
    def _check_store(self, store_id):
        store = self.env['ab_store'].browse(store_id).exists()
        if not store:
            raise ValidationError(_("Select a valid store."))
        user = self.env.user
        if not (user.has_group('base.group_system')
                or user.has_group('ab_inventory.group_inventory_manager')
                or store in user.inventory_store_ids):
            raise AccessError(_("You are not allowed to access this store's inventory."))
        return store

    @api.model
    def get_balance(self, store_id, product_id=None, source_id=None, before=None):
        """Return available stock now, or saved stock before an exclusive UTC cutoff."""
        store = self._check_store(store_id)
        self.env['ab_inventory'].check_access('read')
        movement_model = self.env['ab_inventory'].sudo()
        base = fields.Domain('store_id', '=', store.id)
        if source_id:
            base &= fields.Domain('source_id', '=', source_id)
        if product_id:
            base &= fields.Domain('product_id', '=', product_id)
        saved = base & fields.Domain('status', '=', 'saved')
        if before:
            saved &= fields.Domain('saved_at', '<', before)
        rows = movement_model._read_group(saved, [], ['qty:sum'])
        balance = (rows[0][0] or 0) if rows else 0
        if before is None:
            pending_out = (base & fields.Domain('status', '=', 'pending')
                           & fields.Domain('qty', '<', 0))
            rows = movement_model._read_group(pending_out, [], ['qty:sum'])
            balance += (rows[0][0] or 0) if rows else 0
        return balance

    @api.model
    def get_source_balances(self, store_id, product_id=None, before=None,
                            include_zero=False):
        """Return current available or historical saved quantity per source.

        Current availability includes pending outgoing, but not pending incoming.
        """
        return self._source_balances(
            store_id, product_id=product_id, before=before, include_zero=include_zero,
            include_pending_outgoing=before is None,
        )

    @api.model
    def _source_balances(self, store_id, product_id=None, before=None,
                         source_ids=None, include_zero=True,
                         include_pending_outgoing=False):
        """Aggregate saved quantities and optionally pending outgoing holds."""
        store = self._check_store(store_id)
        self.env['ab_inventory'].check_access('read')
        movement_model = self.env['ab_inventory'].sudo()
        if source_ids is not None and not source_ids:
            return {}
        base = fields.Domain('store_id', '=', store.id)
        if product_id:
            base &= fields.Domain('product_id', '=', product_id)
        if source_ids is not None:
            base &= fields.Domain('source_id', 'in', source_ids)
        saved = base & fields.Domain('status', '=', 'saved')
        if before:
            saved &= fields.Domain('saved_at', '<', before)
        balances = {source.id: quantity or 0 for source, quantity in
                    movement_model._read_group(saved, ['source_id'], ['qty:sum']) if source}
        if include_pending_outgoing and before is None:
            pending_out = (base & fields.Domain('status', '=', 'pending')
                           & fields.Domain('qty', '<', 0))
            for source, quantity in movement_model._read_group(
                    pending_out, ['source_id'], ['qty:sum']):
                if source:
                    balances[source.id] = balances.get(source.id, 0) + (quantity or 0)
        return {source_id: quantity for source_id, quantity in balances.items()
                if include_zero or quantity}

    @api.model
    def _lock_stores(self, store_ids):
        for store_id in sorted(set(store_ids)):
            self.env.cr.execute('SELECT id FROM ab_store WHERE id = %s FOR UPDATE',
                                (store_id,))

    @api.model
    def _lock_unit_definitions(self, source_ids, product_ids=(), uom_ids=()):
        """Serialize source and unit edits with movement creation/conversion."""
        source_ids = sorted(set(source_ids))
        locked_products = set(product_ids)
        locked_uoms = set(uom_ids)
        for source_id in source_ids:
            self.env.cr.execute(
                'SELECT product_id, uom_id FROM ab_product_source WHERE id = %s FOR UPDATE',
                (source_id,),
            )
            row = self.env.cr.fetchone()
            if row:
                if row[0]:
                    locked_products.add(row[0])
                if row[1]:
                    locked_uoms.add(row[1])
        for product_id in sorted(locked_products):
            self.env.cr.execute(
                'SELECT unit_l_id, unit_m_id, unit_s_id FROM ab_product '
                'WHERE id = %s FOR UPDATE', (product_id,),
            )
            row = self.env.cr.fetchone()
            if row:
                locked_uoms.update(uom_id for uom_id in row if uom_id)
        for uom_id in sorted(locked_uoms):
            self.env.cr.execute('SELECT id FROM ab_uom WHERE id = %s FOR UPDATE',
                                (uom_id,))
        # A transaction that held either lock may have changed these values.
        self.env['ab_product_source'].browse(source_ids).invalidate_recordset(
            ['product_id', 'uom_id'],
        )
        self.env['ab_product'].browse(sorted(locked_products)).invalidate_recordset(
            ['unit_s_id', 'unit_m_id', 'unit_l_id'],
        )
        self.env['ab_uom'].browse(sorted(locked_uoms)).invalidate_recordset(
            ['unit_no', 'unit_size', 'type_id'],
        )

    @api.model
    def _smallest_unit_qty(self, rec, qty, sign):
        if isinstance(sign, bool) or sign not in (-1, 1):
            raise ValidationError(_("Inventory direction must be +1 or -1."))
        try:
            amount = Decimal(str(qty))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError(_("Inventory quantity must be positive.")) from None
        if not amount.is_finite() or amount <= 0:
            raise ValidationError(_("Inventory quantity must be positive."))
        product = rec.source_id.product_id
        unit_size = rec.uom_id.unit_size
        if not product or not unit_size:
            raise ValidationError(_("The source item and unit are required for inventory."))
        if unit_size == 'large':
            numerator = Decimal(str(product.unit_s_id.unit_no or 0))
            denominator = Decimal(1)
        elif unit_size == 'medium':
            numerator = Decimal(str(product.unit_s_id.unit_no or 0))
            denominator = Decimal(str(product.unit_m_id.unit_no or 0))
        elif unit_size == 'small':
            numerator = denominator = Decimal(1)
        else:
            numerator = denominator = Decimal(0)
        if not numerator or not denominator:
            raise ValidationError(_("The item unit conversion is not configured."))
        converted = (amount * numerator) / denominator
        if converted != converted.to_integral_value():
            raise ValidationError(_("Quantity cannot be represented exactly in the smallest unit."))
        return sign * int(converted)

    @api.model
    def check_operation(self, operation, *, old=None, new=None):
        """Check one proposed stock effect inside the caller's transaction.

        old/new are dictionaries with store_id, source_id, signed smallest-unit
        qty, and status. The ledger's create/post guards remain authoritative.
        """
        if operation not in ('create', 'write', 'unlink'):
            raise ValueError('Unsupported inventory operation')
        if old is not None and not isinstance(old, dict):
            raise TypeError('old must be a stock-effect dictionary')
        if new is not None and not isinstance(new, dict):
            raise TypeError('new must be a stock-effect dictionary')

        store_ids = set()
        if old:
            store_ids.add(self._check_store(old.get('store_id')).id)
        if new:
            store_ids.add(self._check_store(new.get('store_id')).id)
        self._lock_stores(store_ids)

        if operation == 'unlink':
            if old and old.get('status') == 'saved':
                raise ValidationError(_("Saved movements cannot be deleted."))
            if old:
                raise ValidationError(_(
                    "Cancel pending inventory through its business document instead of deleting it."
                ))
            return True
        if old and old.get('status') == 'saved':
            raise ValidationError(_("Saved movements cannot be edited."))
        if not new:
            return True
        if new.get('status') not in ('pending', 'saved'):
            raise ValidationError(_("Inventory status must be Pending or Saved."))
        self.env['ab_inventory']._validate_quantity_value(new.get('qty'))
        if not new.get('source_id'):
            raise ValidationError(_("The source item and unit are required for inventory."))
        if new['qty'] >= 0:
            return True

        available = self.sudo()._source_balances(
            new['store_id'], source_ids=[new['source_id']],
            include_pending_outgoing=True,
        ).get(new['source_id'], 0)
        if (old and old.get('status') == 'pending' and old.get('qty', 0) < 0
                and old.get('store_id') == new['store_id']
                and old.get('source_id') == new['source_id']):
            # Remove this line's existing hold before checking its replacement.
            available -= old['qty']
        if available + new['qty'] < 0:
            if new['status'] == 'saved':
                raise ValidationError(_("Posting would create negative stock in a store or batch."))
            raise ValidationError(_(
                "Pending outgoing stock exceeds available quantity in this store or batch."
            ))
        return True

    @api.model
    def inventory_write(self, rec, qty, store_id, inventory_line=None,
                        status='saved', sign=1):
        """Upsert a pending observation or save one immutable business-line effect."""
        if not isinstance(rec, models.BaseModel) or len(rec) != 1 or not isinstance(rec.id, int):
            raise ValidationError(_("Provide one saved business line for inventory."))
        if status not in ('pending', 'saved'):
            raise ValidationError(_("Inventory status must be Pending or Saved."))
        if not rec.source_id:
            raise ValidationError(_("The source item and unit are required for inventory."))
        store = self._check_store(store_id)
        movement_model = self.env['ab_inventory']
        key = (rec._name, rec.id)
        with self.env.cr.savepoint():
            self._lock_stores([store.id])
            self._lock_unit_definitions(
                [rec.source_id.id], uom_ids=[rec.uom_id.id] if rec.uom_id else [],
            )
            movement_qty = self._smallest_unit_qty(rec, qty, sign)
            values = {
                'store_id': store.id,
                'source_id': rec.source_id.id,
                'qty': movement_qty,
                'model_ref': key[0],
                'res_id': key[1],
            }
            self.env.cr.execute(
                'SELECT pg_advisory_xact_lock(hashtext(%s), %s)',
                (f'{store.id}:{key[0]}', key[1]),
            )
            existing = movement_model.sudo().search([
                ('store_id', '=', store.id),
                ('model_ref', '=', key[0]), ('res_id', '=', key[1]),
            ], limit=1)
            if inventory_line:
                if (len(inventory_line) != 1 or inventory_line._name != movement_model._name
                        or inventory_line.id != existing.id):
                    raise ValidationError(_("The inventory line does not match the business line."))
            if existing:
                self._check_store(existing.store_id.id)
            if existing and existing.status == 'saved':
                if (existing.store_id.id != store.id
                        or existing.source_id.id != rec.source_id.id
                        or existing.qty != movement_qty):
                    raise ValidationError(_("Saved movements cannot be edited."))
                if status != 'saved':
                    raise ValidationError(_("Saved movements cannot return to Pending."))
                return movement_model.browse(existing.id)
            old_effect = ({
                'store_id': existing.store_id.id,
                'source_id': existing.source_id.id,
                'qty': existing.qty,
                'status': existing.status,
            } if existing else None)
            self.check_operation(
                'write' if existing else 'create', old=old_effect,
                new={
                    'store_id': store.id,
                    'source_id': rec.source_id.id,
                    'qty': movement_qty,
                    'status': status,
                },
            )
            if existing:
                existing.write({field: value for field, value in values.items()
                                if field not in ('model_ref', 'res_id')})
                movement = existing
            else:
                movement = movement_model.sudo().create(values)
            if status == 'saved':
                self._post(movement, require_manager=False)
            return movement_model.browse(movement.id)

    def _post(self, movements, require_manager=True):
        if require_manager and not (self.env.user.has_group('base.group_system')
                                    or self.env.user.has_group('ab_inventory.group_inventory_manager')):
            raise AccessError(_("Only inventory managers can post movements."))
        if any(rec.status != 'pending' for rec in movements):
            raise ValidationError(_("Only pending movements can be saved."))
        with self.env.cr.savepoint():
            balances = self._opening_balances(movements)
            saved_at = fields.Datetime.now()
            for rec in movements.sorted('id'):
                key = (rec.store_id.id, rec.source_id.id)
                closing = balances.get(key, 0) + rec.qty
                if closing < 0:
                    raise ValidationError(_("Posting would create negative stock in a store or batch."))
                # Bypass the movement's guarded write override only here.
                super(AbInventory, rec).write({'status': 'saved', 'saved_at': saved_at})
                balances[key] = closing
            by_store = {}
            for store_id, source_id in balances:
                by_store.setdefault(store_id, set()).add(source_id)
            for store_id, source_ids in sorted(by_store.items()):
                available = self.sudo()._source_balances(
                    store_id, source_ids=sorted(source_ids),
                    include_pending_outgoing=True,
                )
                if any(available.get(source_id, 0) < 0 for source_id in source_ids):
                    raise ValidationError(_("Posting would create negative stock in a store or batch."))
        return True

    def _opening_balances(self, movements):
        stores = movements.mapped('store_id').sorted('id')
        # The store lock serializes postings and pending outgoing reservations.
        self._lock_stores(stores.ids)
        balances = {}
        for store in stores:
            source_ids = movements.filtered(lambda rec: rec.store_id == store).mapped('source_id').ids
            source_balances = self.sudo()._source_balances(
                store.id, source_ids=source_ids,
            )
            balances.update({(store.id, source_id): quantity
                             for source_id, quantity in source_balances.items()})
        return balances
