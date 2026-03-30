from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class DistributionStoreLine(models.Model):
    _name = 'ab_distribution_store_line'
    _description = 'Distribution Store Line'
    _order = 'id'

    header_id = fields.Many2one('ab_distribution_store_header', required=True, ondelete='cascade')
    inventory_id = fields.Many2one(
        'ab_distribution_store_inventory',
        required=True,
        domain="[('balance', '>', 0)]",
    )
    product_id = fields.Many2one(related='inventory_id.product_id', store=True, readonly=True)
    pharma_price = fields.Float(related='inventory_id.pharma_price', store=True, readonly=True)
    customer_price = fields.Float(related='inventory_id.customer_price', store=True, readonly=True)
    batch_number = fields.Char(related='inventory_id.batch_number', store=True, readonly=True)
    expiry_date = fields.Date(related='inventory_id.expiry_date', store=True, readonly=True)
    balance = fields.Float(related='inventory_id.balance', readonly=True)

    qty = fields.Float(required=True, default=1.0)
    line_total = fields.Float(compute='_compute_line_total', store=True)

    @api.depends('qty', 'customer_price')
    def _compute_line_total(self):
        for rec in self:
            rec.line_total = rec.qty * rec.customer_price

    @staticmethod
    def _validate_qty_vals(vals_list, partial=False):
        for vals in vals_list:
            if 'qty' in vals:
                qty = vals.get('qty') or 0.0
                if qty <= 0:
                    raise ValidationError(_("Quantity must be greater than zero."))
            if not partial and not vals.get('inventory_id'):
                raise ValidationError(_("Inventory is required."))

    @staticmethod
    def _merge_delta(deltas, inv_id, delta):
        if not inv_id or not delta:
            return
        deltas[inv_id] = deltas.get(inv_id, 0.0) + delta

    def _prepare_create_deltas(self, vals_list):
        deltas = {}
        for vals in vals_list:
            inv_id = vals.get('inventory_id')
            qty = vals.get('qty') or 0.0
            self._merge_delta(deltas, inv_id, -qty)
        return deltas

    def _prepare_write_deltas(self, vals):
        deltas = {}
        new_inv_id = vals.get('inventory_id')
        new_qty = vals.get('qty')
        for line in self:
            old_inv_id = line.inventory_id.id
            old_qty = line.qty
            target_inv_id = new_inv_id if new_inv_id is not None else old_inv_id
            target_qty = new_qty if new_qty is not None else old_qty
            if old_inv_id == target_inv_id:
                self._merge_delta(deltas, old_inv_id, old_qty - target_qty)
            else:
                self._merge_delta(deltas, old_inv_id, old_qty)
                self._merge_delta(deltas, target_inv_id, -target_qty)
        return deltas

    def _prepare_unlink_deltas(self):
        deltas = {}
        for line in self:
            self._merge_delta(deltas, line.inventory_id.id, line.qty)
        return deltas

    def _check_inventory_balances(self, deltas):
        if not deltas:
            return
        inventories = self.env['ab_distribution_store_inventory'].browse(deltas.keys())
        for inventory in inventories:
            new_balance = inventory.balance + deltas.get(inventory.id, 0.0)
            if new_balance < 0:
                raise ValidationError(
                    _("Insufficient balance for %s.") % (inventory.display_name or inventory.id)
                )

    def _apply_inventory_deltas(self, deltas):
        if not deltas:
            return
        inventories = self.env['ab_distribution_store_inventory'].browse(deltas.keys())
        for inventory in inventories:
            delta = deltas.get(inventory.id, 0.0)
            if delta:
                inventory.write({'balance': inventory.balance + delta})

    @api.model_create_multi
    def create(self, vals_list):
        default_qty = self._fields['qty'].default(self)
        for vals in vals_list:
            if 'qty' not in vals:
                vals['qty'] = default_qty if default_qty is not None else 0.0
        self._validate_qty_vals(vals_list)
        deltas = self._prepare_create_deltas(vals_list)
        self._check_inventory_balances(deltas)
        lines = super().create(vals_list)
        lines._apply_inventory_deltas(deltas)
        return lines

    def write(self, vals):
        if 'qty' in vals or 'inventory_id' in vals:
            self._validate_qty_vals([vals], partial=True)
            deltas = self._prepare_write_deltas(vals)
            self._check_inventory_balances(deltas)
            res = super().write(vals)
            self._apply_inventory_deltas(deltas)
            return res
        return super().write(vals)

    def unlink(self):
        deltas = self._prepare_unlink_deltas()
        res = super().unlink()
        self._apply_inventory_deltas(deltas)
        return res
