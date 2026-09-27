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
    closing_balance = fields.Integer(string='Closing Balance', readonly=True, copy=False)
    status = fields.Selection([('pending', 'Pending'), ('saved', 'Saved')], string='Status',
                              default='pending', required=True, readonly=True, copy=False, index=True)
    saved_at = fields.Datetime(string='Saved At', readonly=True, copy=False, index=True)
    model_ref = fields.Selection([
        ('manual', 'Manual'),
        ('opening', 'Opening Balance'),
    ], default='manual', required=True, string='Source Type', index=True)
    res_id = fields.Integer(string='Source Record ID', readonly=True, copy=False, index=True)

    _latest_saved_balance_idx = models.Index(
        "(store_id, source_id, saved_at DESC, id DESC) WHERE status = 'saved'"
    )

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
        for vals in vals_list:
            if 'incoming_qty' in vals or 'outgoing_qty' in vals:
                raise ValidationError(_("Use a signed quantity change instead of incoming or outgoing fields."))
            self._validate_quantity_value(vals.get('qty'))
            if (vals.get('status', 'pending') != 'pending'
                    or 'saved_at' in vals or 'closing_balance' in vals):
                raise ValidationError(_("Post movements through the Post action."))
            self.env['ab_inventory_process']._check_store(vals.get('store_id'))
            res_id = vals.get('res_id')
            if res_id and (isinstance(res_id, bool) or not isinstance(res_id, int) or res_id < 1):
                raise ValidationError(_("Source Record ID must be a positive integer."))
            if res_id:
                identities.append((vals.get('model_ref', 'manual'), res_id))
        identity_set = set(identities)
        if len(identities) != len(identity_set):
            raise ValidationError(_("This source record already has an inventory movement."))
        if not identity_set:
            return super().create(vals_list)
        with self.env.cr.savepoint():
            for model_ref, res_id in sorted(identity_set):
                # Serialize retries even when they target different stores.
                self.env.cr.execute(
                    'SELECT pg_advisory_xact_lock(hashtext(%s), %s)',
                    (model_ref, res_id),
                )
            existing = self.sudo().search([
                ('model_ref', 'in', list({key[0] for key in identity_set})),
                ('res_id', 'in', list({key[1] for key in identity_set})),
            ])
            if any((rec.model_ref, rec.res_id) in identity_set for rec in existing):
                raise ValidationError(_("This source record already has an inventory movement."))
            return super().create(vals_list)

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
        return super().write(vals)

    def unlink(self):
        if any(rec.status == 'saved' for rec in self):
            raise ValidationError(_("Saved movements cannot be deleted."))
        return super().unlink()

    def action_post(self):
        return self.write({'status': 'saved'})
