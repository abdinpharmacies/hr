from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class AbdinInventory(models.Model):
    _name = 'ab_inventory'
    _description = 'ab_inventory'
    _order = 'source_id,qty DESC'

    header_id = fields.Integer(index=True)
    store_id = fields.Many2one('ab_store', required=True, index=True, readonly=True)
    source_id = fields.Many2one('ab_product_source', index=True, readonly=True, auto_join=True)
    product_id = fields.Many2one(related='source_id.product_id')
    price = fields.Float(related='source_id.price')
    unit_cost = fields.Float(related='source_id.unit_cost')
    unit_taxes_value = fields.Float(related='source_id.unit_taxes_value')

    qty = fields.Integer(required=True, readonly=True)
    source_uom_id = fields.Many2one(related='source_id.uom_id', string='UOM')
    qty_in_source_unit = fields.Float(compute='_compute_qty_in_source_unit', string='Quantity')
    location = fields.Char()
    model_ref = fields.Selection(selection=[('ab_inventory', 'Inventory Line')],
                                 default="ab_inventory",
                                 required=True, index=True)

    res_id = fields.Integer(index=True, required=True, default=0, readonly=True)

    header_ref = fields.Char(index=True, required=True, readonly=True)

    serial = fields.Float(digits=(11, 0), readonly=True)

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

    # UNIQUE(model_ref,res_id,store_id,status)
    _sql_constraints = [
        ('ab_inventory_model_ref_store_id_unique', 'Check(1=1)',
         _('A record with this store and entry reference already exists.')),
    ]

    def _compute_qty_in_source_unit(self):
        for rec in self:
            rec.qty_in_source_unit = rec.product_id.qty_from_small(rec.qty, rec.source_uom_id.unit_size)

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

    def name_get(self):
        res = []
        for rec in self:
            source_id_balance_L = (
                    rec.source_id_balance / rec.product_id.unit_s_id.unit_no)
            price_large_unit = self._get_price_large_unit(rec)
            exp_date = "No Exp-Date" if rec.source_id.exp_date == False else rec.source_id.exp_date
            res.append(
                (rec.id,
                 f'{exp_date}_ {price_large_unit} EGP',
                 )
            )
        return res

    def _get_price_large_unit(self, rec):
        price_large_unit = 0.0
        if rec.source_id.uom_id.unit_size == 'large':
            price_large_unit = rec.source_id.price
        elif rec.source_id.uom_id.unit_size in ['medium', 'small']:
            price_large_unit = rec.source_id.price * rec.source_id.uom_id.unit_no
        return price_large_unit

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

    def btn_saved_store(self):
        try:
            self.ensure_one()
            if self.status == 'pending_main':
                raise ValidationError(_("You Can Not Save 'Rejected Line'"))
            if self.status != 'saved':
                self.status = 'saved'
        except Exception as ex:
            raise UserError(_("Action For One Record Only"))

    def btn_pending_main(self):
        try:
            self.ensure_one()
            if self.status == 'saved':
                raise ValidationError(_("You Can not Modify 'Saved Line'"))
            if self.status == 'pending_store':
                self.status = 'pending_main'
        except Exception as ex:
            raise UserError(_("Action For One Record Only"))

    def btn_pending_store(self):
        try:
            self.ensure_one()
            if self.status == 'saved':
                raise ValidationError(_("You Can not Modify 'Saved Line'"))
            if self.status == 'pending_main':
                self.status = 'pending_store'
        except Exception as ex:
            raise UserError(_("Action For One Record Only"))
