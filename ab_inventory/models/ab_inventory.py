from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbInventory(models.Model):
    _name = 'ab_inventory'
    _description = 'Inventory Movement'
    _rec_name = 'id'
    _order = 'saved_at desc, id desc'

    store_id = fields.Many2one('ab_store', string='Store', required=True, index=True, ondelete='restrict')
    source_id = fields.Many2one('ab_product_source', string='Batch / Source',
                                required=True, index=True, ondelete='restrict')
    product_id = fields.Many2one('ab_product', string='Item', related='source_id.product_id',
                                 store=True, index=True)
    qty = fields.Integer(string='Quantity Change', required=True)
    incoming_qty = fields.Integer(string='Incoming', compute='_compute_direction_quantities')
    outgoing_qty = fields.Integer(string='Outgoing', compute='_compute_direction_quantities')
    closing_balance = fields.Integer(
        string='Closing Balance', compute='_compute_closing_balance', store=False,
        copy=False,
    )
    status = fields.Selection([('pending', 'Pending'), ('saved', 'Saved')], string='Status',
                              default='pending', required=True, readonly=True, copy=False, index=True)
    saved_at = fields.Datetime(string='Saved At', readonly=True, copy=False, index=True)
    model_ref = fields.Selection([
        ('manual', 'Manual'),
        ('opening', 'Opening Balance'),
    ], default='manual', required=True, string='Source Type', index=True)
    res_id = fields.Integer(string='Source Record ID', readonly=True, copy=False, index=True)

    _saved_source_sum_idx = models.Index(
        "(store_id, source_id, saved_at, id) INCLUDE (qty) WHERE status = 'saved'"
    )
    _saved_product_sum_idx = models.Index(
        "(store_id, product_id, saved_at) INCLUDE (qty) WHERE status = 'saved'"
    )
    _saved_date_sum_idx = models.Index(
        "(store_id, saved_at) INCLUDE (source_id, product_id, qty) WHERE status = 'saved'"
    )
    _pending_out_source_sum_idx = models.Index(
        "(store_id, source_id) INCLUDE (qty) WHERE status = 'pending' AND qty < 0"
    )
    _pending_out_product_sum_idx = models.Index(
        "(store_id, product_id) INCLUDE (qty) WHERE status = 'pending' AND qty < 0"
    )
    _linked_source_unique_idx = models.UniqueIndex(
        '(store_id, model_ref, res_id) WHERE res_id > 0',
        'This source record already has an inventory movement.',
    )

    @api.depends('store_id', 'source_id', 'qty', 'status', 'saved_at')
    def _compute_closing_balance(self):
        """Cumulative saved quantity for this store/source through each movement."""
        saved_ids = [rec.id for rec in self
                     if isinstance(rec.id, int) and rec.status == 'saved' and rec.saved_at]
        balances = {}
        if saved_ids:
            self.flush_model(['store_id', 'source_id', 'qty', 'status', 'saved_at'])
            self.env.cr.execute("""
                SELECT current.id,
                       COALESCE((
                           SELECT SUM(previous.qty)
                             FROM ab_inventory AS previous
                            WHERE previous.store_id = current.store_id
                              AND previous.source_id = current.source_id
                              AND previous.status = 'saved'
                              AND (previous.saved_at, previous.id)
                                  <= (current.saved_at, current.id)
                       ), 0)
                  FROM ab_inventory AS current
                 WHERE current.id = ANY(%s)
            """, (saved_ids,))
            balances = dict(self.env.cr.fetchall())
        for rec in self:
            rec.closing_balance = balances.get(rec.id, 0)

    @api.depends('store_id', 'product_id')
    def _compute_display_name(self):
        for rec in self:
            label = (_("Movement #%s") % rec.id) if isinstance(rec.id, int) else _("Inventory Movement")
            parts = [label]
            if rec.product_id:
                parts.append(rec.product_id.display_name)
            if rec.store_id:
                parts.append(rec.store_id.display_name)
            rec.display_name = ' / '.join(parts)

    @api.depends('qty')
    def _compute_direction_quantities(self):
        for rec in self:
            rec.incoming_qty = max(rec.qty, 0)
            rec.outgoing_qty = max(-rec.qty, 0)

    @api.constrains('qty')
    def _check_quantity(self):
        for rec in self:
            if not rec.qty:
                raise ValidationError(_("Quantity change must be a non-zero integer in the smallest unit."))

    @api.model
    def _validate_quantity_value(self, value):
        if isinstance(value, bool) or not isinstance(value, int) or not value:
            raise ValidationError(_("Quantity change must be a non-zero integer in the smallest unit."))

    @api.model_create_multi
    def create(self, vals_list):
        identities = []
        store_ids = set()
        source_ids = set()
        for vals in vals_list:
            if 'incoming_qty' in vals or 'outgoing_qty' in vals:
                raise ValidationError(_("Use a signed quantity change instead of incoming or outgoing fields."))
            self._validate_quantity_value(vals.get('qty'))
            if (vals.get('status', 'pending') != 'pending'
                    or 'saved_at' in vals or 'closing_balance' in vals):
                raise ValidationError(_("Post movements through the Post action."))
            self.env['ab_inventory_process']._check_store(vals.get('store_id'))
            store_ids.add(vals['store_id'])
            if vals.get('source_id'):
                source_ids.add(vals['source_id'])
            res_id = vals.get('res_id')
            if res_id and (isinstance(res_id, bool) or not isinstance(res_id, int) or res_id < 1):
                raise ValidationError(_("Source Record ID must be a positive integer."))
            if res_id:
                identities.append((vals['store_id'], vals.get('model_ref', 'manual'), res_id))
        identity_set = set(identities)
        if len(identities) != len(identity_set):
            raise ValidationError(_("This source record already has an inventory movement."))
        if not identity_set:
            with self.env.cr.savepoint():
                self.env['ab_inventory_process']._lock_stores(store_ids)
                self.env['ab_inventory_process']._lock_unit_definitions(source_ids)
                records = super().create(vals_list)
                records._check_pending_availability()
                return records
        with self.env.cr.savepoint():
            self.env['ab_inventory_process']._lock_stores(store_ids)
            self.env['ab_inventory_process']._lock_unit_definitions(source_ids)
            for store_id, model_ref, res_id in sorted(identity_set):
                # Serialize retries for the same linked line within a store.
                self.env.cr.execute(
                    'SELECT pg_advisory_xact_lock(hashtext(%s), %s)',
                    (f'{store_id}:{model_ref}', res_id),
                )
            existing = self.sudo().search([
                ('store_id', 'in', list({key[0] for key in identity_set})),
                ('model_ref', 'in', list({key[1] for key in identity_set})),
                ('res_id', 'in', list({key[2] for key in identity_set})),
            ])
            if any((rec.store_id.id, rec.model_ref, rec.res_id) in identity_set
                   for rec in existing):
                raise ValidationError(_("This source record already has an inventory movement."))
            records = super().create(vals_list)
            records._check_pending_availability()
            return records

    def _check_pending_availability(self):
        process = self.env['ab_inventory_process'].sudo()
        by_store = {}
        for rec in self:
            if rec.qty < 0:
                by_store.setdefault(rec.store_id.id, set()).add(rec.source_id.id)
        for store_id, source_ids in sorted(by_store.items()):
            balances = process._source_balances(
                store_id, source_ids=sorted(source_ids), include_pending_outgoing=True,
            )
            if any(balances.get(source_id, 0) < 0 for source_id in source_ids):
                raise ValidationError(_("Pending outgoing stock exceeds available quantity in this store or batch."))

    def write(self, vals):
        if 'incoming_qty' in vals or 'outgoing_qty' in vals:
            raise ValidationError(_("Use a signed quantity change instead of incoming or outgoing fields."))
        if 'qty' in vals:
            self._validate_quantity_value(vals['qty'])
        if any(rec.status == 'saved' for rec in self):
            raise ValidationError(_("Saved movements cannot be edited."))
        process = self.env['ab_inventory_process']
        for store in self.mapped('store_id'):
            process._check_store(store.id)
        if 'store_id' in vals:
            process._check_store(vals['store_id'])
        if 'res_id' in vals or ('model_ref' in vals and any(self.mapped('res_id'))):
            raise ValidationError(_("A movement's source record cannot be changed."))
        if 'saved_at' in vals or 'closing_balance' in vals or ('status' in vals and vals['status'] != 'saved'):
            raise ValidationError(_("Post movements through the Post action."))
        if vals.get('status') == 'saved':
            if set(vals) != {'status'}:
                raise ValidationError(_("Post movements through the Post action."))
            if any(self.mapped('res_id')):
                raise ValidationError(_("Linked movements must be saved through their business document."))
            return process._post(self, require_manager=True)
        if not {'qty', 'store_id', 'source_id'} & set(vals):
            return super().write(vals)
        with self.env.cr.savepoint():
            new_qty = vals.get('qty')
            affected = self.filtered(lambda rec: rec.qty < 0 or
                                     (new_qty is not None and new_qty < 0))
            store_ids = set(self.mapped('store_id').ids)
            if 'store_id' in vals:
                store_ids.add(vals['store_id'])
            process._lock_stores(store_ids)
            if vals.get('source_id'):
                process._lock_unit_definitions([vals['source_id']])
            result = super().write(vals)
            affected._check_pending_availability()
            return result

    def unlink(self):
        if any(rec.status == 'saved' for rec in self):
            raise ValidationError(_("Saved movements cannot be deleted."))
        with self.env.cr.savepoint():
            outgoing_stores = self.filtered(lambda rec: rec.qty < 0).mapped('store_id').ids
            self.env['ab_inventory_process']._lock_stores(outgoing_stores)
            return super().unlink()

    def action_post(self):
        return self.write({'status': 'saved'})
