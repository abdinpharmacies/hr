from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Store(models.Model):
    _inherit = 'ab_store'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)

    def _check_integration_scope(self):
        self.check_access('read')
        for store in self:
            if (not self.env.context.get('ab_sales_branch_scope')
                    and store.company_id not in self.env.companies):
                raise AccessError(_('The store must belong to an allowed company.'))
            self.env['ab_inventory_process']._check_store(store.id)
        return self

    def _lock_stock_scope(self):
        self.env['ab_inventory_process']._lock_stores(self.ids)

    @api.model_create_multi
    def create(self, vals_list):
        if any('company_id' in vals for vals in vals_list) and not self.env.is_system():
            raise AccessError(_('Only administrators can assign a store company.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'company_id' in vals:
            if not self.env.is_system():
                raise AccessError(_('Only administrators can assign a store company.'))
            self.check_access('write')
            self.lock_for_update(allow_referencing=True)
            changed = self.filtered(lambda store: store.company_id.id != vals['company_id'])
            if changed and self.env['ab_inventory'].sudo().search_count(fields.Domain('store_id', 'in', changed.ids), limit=1):
                raise ValidationError(_('A store with inventory history cannot change its company.'))
        return super().write(vals)
