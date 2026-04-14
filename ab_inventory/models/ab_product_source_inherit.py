from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError, UserError


class AbProductSource(models.Model):
    _name = 'ab_product_source'
    _inherit = 'ab_product_source'

    available_qty = fields.Float(compute='_compute_invoice_data')
    total_qty = fields.Float(compute='_compute_invoice_data')
    is_pending = fields.Boolean(compute='_compute_is_pending', search='_search_is_pending')

    def _compute_is_pending(self):
        for rec in self:
            rec.is_pending = bool(self.env['ab_product_source_pending'].browse(rec.id))

    def _search_is_pending(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        pending = self.env['ab_product_source_pending'].search([])

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', pending.ids)]

    @api.depends('product_id', 'uom_id')
    def _compute_invoice_data(self):
        for rec in self:
            inventory_pending = self.env['ab_inventory'].search(
                [('source_id', '=', rec.id), ('status', '=', 'pending_main')])

            inventory_all = self.env['ab_inventory'].search([('source_id', '=', rec.id), ])

            # get min(pending_qty , total_qty) qty
            available_qty_pending_s_unit = sum(inv.qty for inv in inventory_pending)
            available_qty_all_s_unit = sum(inv.qty for inv in inventory_all)
            available_qty_s_unit = min(available_qty_pending_s_unit, available_qty_all_s_unit)

            available_qty = rec.product_id.qty_from_small(available_qty_s_unit, rec.uom_id.unit_size)

            # check if this line was returned before (to define actual rest of bonus)
            rec.available_qty = available_qty
            rec.total_qty = rec.product_id.qty_from_small(available_qty_all_s_unit, rec.uom_id.unit_size)

    def write(self, vals):
        inventory_mo = self.env['ab_inventory'].sudo()
        for rec in self:
            inventory_line = inventory_mo.search([('source_id', '=', rec.id)])
            res = super().write(vals)
            # @todo: review this error later
            # if len(inventory_line) > 1:
            #     raise ValidationError(_("Can not Edit Source Line, as Inventory Lines more than one. "
            #                             " Please Use 'Debit' Or 'Credit' Notices Instead."))
            if len(inventory_line) == 1:
                if inventory_line.status != 'pending_main':
                    raise ValidationError(_("Can not Edit Source Line, as Inventory Lines Must be Pending Main."
                                            " Please Wait Store to Take Action."
                                            f"\nLine: {inventory_line.id}"))
                inventory_dict = {}
                if inventory_line.qty != rec.qty:
                    inventory_dict['qty'] = rec.qty
                if inventory_line.product_id.id != rec.product_id.id:
                    inventory_dict['product_id'] = rec.product_id.id
                if inventory_dict:
                    inventory_line.write(inventory_dict)
            return res
