from odoo import _, api, models


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.model
    def _employee_has_real_telegram_identity(self, employee):
        return bool(
            employee
            and (employee.telegram_chat_id or '').strip()
            and (employee.telegram_user_id or '').strip()
        )

    @api.model
    def get_supplier_claim_dept_managers(self):
        results = super().get_supplier_claim_dept_managers()
        manager_ids = [row['manager_id'] for row in results if row.get('manager_id')]
        employees = self.env['ab_hr_employee'].sudo().browse(manager_ids)
        employee_by_id = {employee.id: employee for employee in employees}
        for row in results:
            manager = employee_by_id.get(row.get('manager_id'))
            row.update({
                'telegram_username': manager.telegram_username if manager else '',
                'has_telegram': self._employee_has_real_telegram_identity(manager),
            })
        return results

    @api.model
    def assign_supplier_claim_manager(self, dept_code, employee_id):
        employee = self.env['ab_hr_employee'].sudo().browse(employee_id).exists()
        if not employee:
            return {'error': _('Employee not found')}
        if not self._employee_has_real_telegram_identity(employee):
            return {'error': _('Employee has no Telegram connection')}
        result = super().assign_supplier_claim_manager(dept_code, employee_id)
        if result.get('success'):
            result.update({
                'telegram_username': employee.telegram_username or '',
                'has_telegram': self._employee_has_real_telegram_identity(employee),
            })
        return result

    @api.model
    def get_eligible_manager_candidates(self, exclude_dept_code=None):
        claim_group_map = {
            'inventory': 'supplier_claim_group_inventory',
            'purchase': 'supplier_claim_group_purchase',
            'suppliers': 'supplier_claim_group_suppliers',
            'bank_accounts': 'supplier_claim_group_bank_acc',
            'tax_accounts': 'supplier_claim_group_tax_accounts',
        }
        already_assigned_ids = set()
        for dept_code in claim_group_map:
            if dept_code == exclude_dept_code:
                continue
            manager = self._get_stored_manager(dept_code)
            if manager:
                already_assigned_ids.add(manager.id)
        employees = self.env['ab_hr_employee'].sudo().search([
            ('telegram_chat_id', '!=', False),
            ('telegram_chat_id', '!=', ''),
            ('telegram_user_id', '!=', False),
            ('telegram_user_id', '!=', ''),
            ('id', 'not in', list(already_assigned_ids)),
        ])
        return [{
            'id': employee.id,
            'name': employee.name,
            'telegram_username': employee.telegram_username or '',
        } for employee in employees]

    @api.model
    def get_telegram_connected_employees(self):
        employees = self.env['ab_hr_employee'].sudo().search([
            ('telegram_chat_id', '!=', False),
            ('telegram_chat_id', '!=', ''),
            ('telegram_user_id', '!=', False),
            ('telegram_user_id', '!=', ''),
        ], order='name')
        results = []
        for employee in employees:
            linked_at = employee.telegram_linked_at
            results.append({
                'id': employee.id,
                'name': employee.name,
                'department_name': employee.department_id.name if employee.department_id else '',
                'department_id': employee.department_id.id if employee.department_id else False,
                'telegram_username': employee.telegram_username or '',
                'telegram_chat_id': employee.telegram_chat_id or '',
                'telegram_user_id': employee.telegram_user_id or '',
                'linked_at': linked_at.isoformat() if linked_at else False,
                'user_id': employee.user_id.id if employee.user_id else False,
                'user_name': employee.user_id.name if employee.user_id else '',
            })
        return results
