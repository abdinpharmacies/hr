from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError, UserError


class AbdinInventory(models.Model):
    _name = 'ab_inventory'
    _description = 'ab_inventory'
    _order = 'source_id,qty DESC'

    header_id = fields.Many2one('ab_inventory_header', index=True)

    store_id = fields.Many2one('ab_store', required=True, index=True, readonly=True)
    source_id = fields.Many2one('ab_product_source', index=True, readonly=True, auto_join=True)
    product_id = fields.Many2one(related='source_id.product_id')
    price = fields.Float(related='source_id.price')
    unit_cost = fields.Float(related='source_id.unit_cost')
    unit_taxes_value = fields.Float(related='source_id.unit_taxes_value')

    qty = fields.Integer(required=True, readonly=True)
    uom_id = fields.Many2one(related='source_id.uom_id', string='UOM')
    qty_in_source_unit = fields.Float(compute='_compute_qty_in_source_unit', string='Quantity')
    location = fields.Char()

    # convert model_ref from Selection to Char to FIX adding new line type each time.
    # must add ondelete attribute, as odoo refused to neglect it on first upgrade
    model_ref = fields.Char(default="ab_inventory", required=True, index=True, ondelete=None)

    res_id = fields.Integer(index=True, required=True, default=0, readonly=True)

    header_ref = fields.Char(index=True, required=True, readonly=True)

    serial = fields.Float(digits=(11, 0), readonly=True)

    is_curr_store = fields.Boolean(compute='_compute_is_curr_store', compute_sudo=True)

    status = fields.Selection(
        selection=[
            ('pending_main', 'Pending Main'),
            ('pending_store', 'Pending Store'),
            ('saved', 'Saved Store')],
        default='pending_main',
        required=True,
        index=True, readonly=True
    )
    source_id_balance = fields.Float(compute='_compute_source_id_balance')

    is_store__eq__to_store = fields.Boolean(compute='_compute_is_store__eq__to_store', compute_sudo=True)

    def _compute_is_store__eq__to_store(self):
        for rec in self:
            rec.is_store__eq__to_store = (
                    rec.header_id.store_id.id == rec.header_id.to_store_id.id
                    or not rec.header_id.to_store_id
            )

    @api.depends('store_id', 'header_id.store_id')
    def _compute_is_curr_store(self):
        for rec in self:
            rec.is_curr_store = rec.store_id.id == rec.header_id.store_id.id

    def _compute_qty_in_source_unit(self):
        for rec in self:
            rec.qty_in_source_unit = rec.product_id.qty_from_small(rec.qty, rec.uom_id.unit_size)

    @api.depends('source_id', 'product_id', 'store_id')
    def _compute_source_id_balance(self):
        for rec in self:
            if rec:
                inventory = self.search(
                    [('store_id', '=', rec.store_id.id), ('product_id', '=', rec.product_id.id),
                     ('source_id', '=', rec.source_id.id), ('status', '=', 'saved')])
                rec.source_id_balance = sum(inv.qty for inv in inventory)
            else:
                rec.source_id_balance = 0.0

    @api.depends('source_id.exp_date', 'source_id.price', 'source_id.uom_id.unit_size', 'source_id.uom_id.unit_no')
    def _compute_display_name(self):
        for rec in self:
            price_large_unit = rec._get_price_large_unit()
            exp_date = rec.source_id.exp_date or "No Exp-Date"
            rec.display_name = f'{exp_date}_ {price_large_unit} EGP'

    def _get_price_large_unit(self):
        self.ensure_one()
        if not self.source_id or not self.source_id.uom_id:
            return 0.0
        if self.source_id.uom_id.unit_size == 'large':
            return self.source_id.price
        if self.source_id.uom_id.unit_size in ['medium', 'small']:
            return self.source_id.price * self.source_id.uom_id.unit_no
        return 0.0

    @api.model
    def create(self, vals):
        qty = vals.get('qty')
        if not isinstance(qty, int):
            raise ValidationError(_("Invalid quantity Or Part of quantity."))

        return super(AbdinInventory, self).create(vals)

    # def write(self, vals):
    #     store_id = vals.get('store_id')
    #     model_ref = vals.get('model_ref')
    #     res_id = vals.get('res_id')
    #     saved_record = self.search(
    #         [('store_id', '=', store_id), ('model_ref', '=', model_ref), ('res_id', '=', res_id),
    #          ('status', '=', 'saved')])
    #     if saved_record:
    #         raise ValidationError(
    #             _("A record with this store and references has been saved. You cannot edit the saved inventory record."))
    #     return super().write(vals)

    # def unlink(self):
    #     store_id = vals.get('store_id')
    #     model_ref = vals.get('model_ref')
    #     saved_record = self.search(
    #         [('store_id', '=', store_id), ('model_ref', '=', model_ref), ('status', '=', 'saved')])
    #     if saved_record:
    #         raise ValidationError(
    #             _("A record with this store and entry reference has been saved. You cannot delete the saved inventory record."))
    #     return super(AbdinInventory, self).unlink()

    def btn_pending_main_or_pending_store(self):
        self.ensure_one()
        current_status = self.status

        # from data entry or to data entry
        if self.is_store__eq__to_store or current_status == 'pending_main':
            if current_status == 'pending_main':
                self.status = 'pending_store'
            if current_status == 'pending_store':
                self.status = 'pending_main'
        else:
            raise ValidationError("Only available while Header Store = Header To Store")

    def btn_send_or_reject(self):
        self.ensure_one()
        from_store_id = self.header_id.store_id.id
        to_store_id = self.header_id.to_store_id.id
        if self.is_store__eq__to_store:
            raise ValidationError(_("Supposed to be hidden"))
        if self.status == 'saved':
            raise ValidationError(_("You Can not Modify 'Saved Line'"))

        self = self.sudo()
        if self.store_id.id == from_store_id:
            self.store_id = to_store_id
        elif self.store_id.id == to_store_id:
            self.store_id = from_store_id

    def btn_save(self):
        self.ensure_one()
        if self.status == 'pending_store':
            self.status = 'saved'
        else:
            raise ValidationError("Can only save pending store status!")
