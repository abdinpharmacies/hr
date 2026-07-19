from odoo import api, models


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.depends('privilege_id.name', 'name')
    @api.depends_context('short_display_name')
    def _compute_full_name(self):
        cat = self.env.ref('ab_supplier_claim_cycle.ab_supplier_claim_cycle_category', raise_if_not_found=False)
        for group in self:
            if cat and group.privilege_id and group.privilege_id.category_id and group.privilege_id.category_id.id == cat.id:
                group.full_name = group.name
            else:
                group.full_name = group.privilege_id.name + ' / ' + group.name if group.privilege_id and not self.env.context.get('short_display_name') else group.name
