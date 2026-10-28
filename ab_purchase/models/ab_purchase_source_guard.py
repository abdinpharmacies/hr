from odoo import models, _
from odoo.exceptions import AccessError, ValidationError


class PurchaseSourceGuard(models.Model):
    _inherit = 'ab_product_source'

    def write(self, vals):
        protected = {
            'product_id', 'uom_id', 'qty', 'bonus', 'price', 'purchase_price',
            'extra_discount_percentage', 'exp_date', 'no_expiry', 'taxes_ids', 'source_model',
        }
        if protected.intersection(vals):
            linked_lines = self.env['ab_purchase_line'].sudo().search([('source_id', 'in', self.ids)])
            if any(line.header_id.status != 'prepending' for line in linked_lines):
                raise ValidationError(_('Submitted purchase records cannot be changed.'))
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
