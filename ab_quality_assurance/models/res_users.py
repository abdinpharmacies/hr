from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _get_quality_assurance_area_department_ids(self):
        """Resolve direct branch departments; HR changes require a rule-cache refresh."""
        self.ensure_one()
        employees = self.sudo().ab_employee_ids.filtered('active')
        if not employees:
            return []
        Department = self.env['ab_hr_department'].sudo().with_context(active_test=True)
        managed = Department.search(fields.Domain('manager_id', 'in', employees.ids))
        if not managed:
            return []
        return Department.search(
            fields.Domain('parent_id', 'in', managed.ids)
            & fields.Domain('store_id.store_type', '=', 'branch')
            & fields.Domain('store_id.active', '=', True)
        ).ids
