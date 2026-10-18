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
        """Return saved stock in the smallest unit; before is exclusive UTC.

        Read one saved closing balance per batch, never the full movement sum.
        This numeric API returns zero for a depleted or absent source.
        """
        store = self._check_store(store_id)
        movement_model = self.env['ab_inventory']
        if source_id:
            domain = [('store_id', '=', store.id), ('source_id', '=', source_id),
                      ('status', '=', 'saved')]
            if product_id:
                domain.append(('product_id', '=', product_id))
            if before:
                domain.append(('saved_at', '<', before))
            latest = movement_model.search(domain, order='saved_at desc, id desc', limit=1)
            return latest.closing_balance if latest else 0
        movements = self._latest_movements_by_source(store.id, product_id=product_id,
                                                     before=before)
        return sum(movements.mapped('closing_balance'))

    @api.model
    def get_source_balances(self, store_id, product_id=None, before=None,
                            include_zero=False):
        """Return {source_id: smallest-unit balance}; hide zero closes by default.

        include_zero also includes sources whose latest saved close is zero.
        Sources without any saved movement are never included.
        """
        movements = self._latest_movements_by_source(
            store_id, product_id=product_id, before=before,
        )
        return {movement.source_id.id: movement.closing_balance
                for movement in movements
                if include_zero or movement.closing_balance != 0}

    @api.model
    def _latest_movements_by_source(self, store_id, product_id=None, before=None,
                                    source_ids=None):
        """Fetch one indexed saved movement for each accessible source."""
        store = self._check_store(store_id)
        movement_model = self.env['ab_inventory']
        movement_model.check_access('read')
        if source_ids is None:
            source_domain = (fields.Domain('product_id', '=', product_id)
                             if product_id else fields.Domain.TRUE)
            source_ids = self.env['ab_product_source'].search(source_domain).ids
        if not source_ids:
            return movement_model.browse()
        # LATERAL + the partial index avoids reading every movement for a batch.
        movement_model.flush_model(['store_id', 'source_id', 'status', 'saved_at', 'closing_balance'])
        cutoff = 'AND movement.saved_at < %s' if before else ''
        query = f"""
            SELECT latest.id
              FROM unnest(%s::integer[]) AS source(source_id)
              CROSS JOIN LATERAL (
                    SELECT movement.id FROM ab_inventory AS movement
                     WHERE movement.store_id = %s
                       AND movement.source_id = source.source_id
                       AND movement.status = 'saved'
                       {cutoff}
                     ORDER BY movement.saved_at DESC, movement.id DESC
                     LIMIT 1
              ) AS latest
        """
        params = (source_ids, store.id, before) if before else (source_ids, store.id)
        self.env.cr.execute(query, params)
        movements = movement_model.browse([row[0] for row in self.env.cr.fetchall()])
        movements.check_access('read')
        return movements

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
        movement_qty = self._smallest_unit_qty(rec, qty, sign)
        key = (rec._name, rec.id)
        values = {
            'store_id': store.id,
            'source_id': rec.source_id.id,
            'qty': movement_qty,
            'model_ref': key[0],
            'res_id': key[1],
        }
        with self.env.cr.savepoint():
            self.env.cr.execute(
                'SELECT pg_advisory_xact_lock(hashtext(%s), %s)', key,
            )
            existing = movement_model.sudo().search([
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
                super(AbInventory, rec).write({
                    'status': 'saved', 'saved_at': saved_at, 'closing_balance': closing,
                })
                balances[key] = closing
        return True

    def _opening_balances(self, movements):
        stores = movements.mapped('store_id').sorted('id')
        for store in stores:
            # The store lock serializes concurrent postings, including first receipts.
            self.env.cr.execute('SELECT id FROM ab_store WHERE id = %s FOR UPDATE', (store.id,))
        balances = {}
        for store in stores:
            source_ids = movements.filtered(lambda rec: rec.store_id == store).mapped('source_id').ids
            latest = self.sudo()._latest_movements_by_source(
                store.id, source_ids=source_ids,
            )
            balances.update({(store.id, rec.source_id.id): rec.closing_balance
                             for rec in latest})
        return balances
