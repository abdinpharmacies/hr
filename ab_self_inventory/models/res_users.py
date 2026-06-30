import re

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    ab_self_inventory_branch_ids = fields.Many2many(
        'ab_store',
        compute='_compute_ab_self_inventory_branch_ids',
        string='Self Inventory Branches',
    )

    @api.depends(
        'name',
        'ab_department_ids.name',
        'ab_department_ids.store_id',
        'ab_employee_ids.department_id.name',
        'ab_employee_ids.department_id.store_id',
    )
    def _compute_ab_self_inventory_branch_ids(self):
        Store = self.env['ab_store'].sudo().with_context(active_test=False)
        stores = Store.search([('store_type', '=', 'branch')])
        stores_by_name = {
            self._normalize_self_inventory_branch_token(store.name): store
            for store in stores
            if store.name
        }
        stores_by_code = {
            self._normalize_self_inventory_branch_token(store.code): store
            for store in stores
            if store.code
        }
        stores_by_serial = {
            self._normalize_self_inventory_branch_token(str(store.eplus_serial)): store
            for store in stores
            if store.eplus_serial
        }

        for user in self:
            departments = user.sudo().ab_department_ids | user.sudo().ab_employee_ids.mapped('department_id')
            branch_stores = departments.mapped('store_id')
            branch_stores |= self._match_self_inventory_branch_tokens(
                departments.mapped('name'),
                stores_by_name,
                stores_by_code,
                stores_by_serial,
            )
            branch_stores |= self._match_self_inventory_branch_tokens(
                [user.name],
                stores_by_name,
                stores_by_code,
                stores_by_serial,
            )
            user.ab_self_inventory_branch_ids = branch_stores

    @api.model
    def _match_self_inventory_branch_tokens(self, values, stores_by_name, stores_by_code, stores_by_serial):
        matches = self.env['ab_store']
        for value in values:
            normalized = self._normalize_self_inventory_branch_token(value)
            if not normalized:
                continue
            matches |= stores_by_name.get(normalized, self.env['ab_store'])
            code, name = self._split_self_inventory_branch_code_name(normalized)
            if code:
                matches |= stores_by_code.get(code, self.env['ab_store'])
                matches |= stores_by_serial.get(code, self.env['ab_store'])
            if name:
                matches |= stores_by_name.get(name, self.env['ab_store'])
        return matches

    @api.model
    def _normalize_self_inventory_branch_token(self, value):
        return re.sub(r'\s+', ' ', str(value or '').strip())

    @api.model
    def _split_self_inventory_branch_code_name(self, value):
        match = re.match(r'^(\d+)\s*[-_/\\]\s*(.+)$', value or '')
        if not match:
            return False, False
        return (
            self._normalize_self_inventory_branch_token(match.group(1)),
            self._normalize_self_inventory_branch_token(match.group(2)),
        )
