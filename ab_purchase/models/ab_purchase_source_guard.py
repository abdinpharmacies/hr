from odoo import models, _
from odoo.exceptions import AccessError, ValidationError


class PurchaseSourceGuard(models.Model):
    _inherit = 'ab_product_source'

    def write(self, vals):
        user = self.env.user
        if user.has_group('ab_purchase.group_ab_purchase_data_entry') and not (
                self.env.su or user.has_group('base.group_system')
                or user.has_group('ab_purchase.group_ab_purchase_manager')
                or user.has_group('ab_inventory.group_inventory_manager')):
            # Inspect all links to prevent hidden receipts from being changed through a shared source.
            lines = self.env['ab_purchase_line'].sudo().search([('source_id', 'in', self.ids)])
            permitted = lines.filtered(lambda line: line.header_id.status == 'prepending'
                                      and line.header_id.store_id in user.inventory_store_ids)
            if (set(permitted.mapped('source_id').ids) != set(self.ids)
                    or len(permitted) != len(lines)):
                raise AccessError(_('Only product sources belonging to your store purchase drafts can be edited.'))
        return super().write(vals)

    def _get_purchase_tax_values(self, qty=None, bonus=None):
        values = super()._get_purchase_tax_values(qty=qty, bonus=bonus)
        self.check_access('read')
        snapshot = self.sudo().posting_snapshot if 'posting_snapshot' in self._fields else False
        if qty is not None or bonus is not None or (snapshot and snapshot.get('tax_calculation')):
            return values
        self.ensure_one()
        if self.origin_model != 'ab_purchase_header' or not self.origin_res_id:
            return values
        invoice = self.env['ab_purchase_header'].browse(self.origin_res_id).exists()
        invoice.check_access('read')
        if not invoice or not invoice.total_extra_discount:
            return values
        gross = sum(super(PurchaseSourceGuard, source)._get_purchase_tax_values()['total'] for source in invoice.line_ids.source_id)
        if invoice.total_extra_discount > gross or gross <= 0:
            raise ValidationError(_('The invoice discount cannot exceed its line total.'))
        allocated_discount = invoice.total_extra_discount * values['total'] / gross
        quantity = self.qty + self.bonus
        inventory_value = values['untaxed'] + values['inventory_tax'] - allocated_discount
        if inventory_value < 0:
            raise ValidationError(_('Invoice discounts cannot make inventory value negative.'))
        values['invoice_discount'] = allocated_discount
        values['stock_unit_cost'] = inventory_value / quantity if quantity else 0
        return values
