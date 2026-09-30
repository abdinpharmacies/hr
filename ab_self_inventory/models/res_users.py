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

    def _is_self_inventory_area_reader(self):
        self.ensure_one()
        area_group = self.env.ref(
            'ab_self_inventory.group_ab_self_inventory_area_manager_readonly',
            raise_if_not_found=False,
        )
        if not area_group or area_group not in self.all_group_ids:
            return False
        return (
            self.env.ref('base.group_system') not in self.all_group_ids
            and self.env.ref('ab_self_inventory.group_ab_self_inventory_manager') not in self.all_group_ids
        )

    def _get_self_inventory_area_branch_ids(self):
        """Resolve only explicit HR mappings; never guess from names or codes."""
        self.ensure_one()
        employees = self.sudo().ab_employee_ids.filtered('active')
        if not employees:
            return []
        Department = self.env['ab_hr_department'].sudo().with_context(active_test=True)
        areas = Department.search(
            fields.Domain('manager_id', 'in', employees.ids)
            & fields.Domain('workplace_region', '!=', False)
        ).mapped('workplace_region')
        if not areas:
            return []
        return Department.search(
            fields.Domain('workplace_region', 'in', areas.ids)
            & fields.Domain('store_id.store_type', '=', 'branch')
            & fields.Domain('store_id.active', '=', True)
        ).mapped('store_id').ids
