from odoo import _, api, models


class SupplierClaimManagerService(models.AbstractModel):
    _inherit = 'ab_supplier_claim_manager_service'

    @api.model
    def _employee_has_real_telegram_identity(self, employee):
        return self.env['ab_supplier_claim_telegram_registration'].sudo()._employee_has_real_telegram_identity(employee)

    @api.model
    def _get_employee_telegram_chat_id(self, employee):
        return self.env['ab_supplier_claim_telegram_registration'].sudo()._get_employee_telegram_chat_id(employee)

    @api.model
    def _get_employee_telegram_username(self, employee):
        return self.env['ab_supplier_claim_telegram_registration'].sudo()._get_employee_telegram_username(employee)

    @api.model
    def get_supplier_claim_dept_managers(self):
        results = super().get_supplier_claim_dept_managers()
        manager_ids = [row['manager_id'] for row in results if row.get('manager_id')]
        employees = self.env['ab_hr_employee'].sudo().browse(manager_ids)
        employee_by_id = {employee.id: employee for employee in employees}
        for row in results:
            manager = employee_by_id.get(row.get('manager_id'))
            row.update({
                'telegram_username': self._get_employee_telegram_username(manager) if manager else '',
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
                'telegram_username': self._get_employee_telegram_username(employee) or '',
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
        links = self.env['ab_hr_bot'].sudo().search([])
        linked_employee_ids = [link.employee_id for link in links if link.employee_id and link.chat_id]
        employees = self.env['ab_hr_employee'].sudo().search([
            ('id', 'in', linked_employee_ids or [0]),
            ('id', 'not in', list(already_assigned_ids)),
        ])
        return [{
            'id': employee.id,
            'name': employee.name,
            'telegram_username': self._get_employee_telegram_username(employee) or '',
        } for employee in employees]

    @api.model
    def get_telegram_connected_employees(self):
        links = self.env['ab_hr_bot'].sudo().search([])
        link_by_employee_id = {
            link.employee_id: link
            for link in links
            if link.employee_id and link.chat_id
        }
        linked_employee_ids = list(link_by_employee_id)
        employees = self.env['ab_hr_employee'].sudo().search([
            ('id', 'in', linked_employee_ids or [0]),
        ], order='name')
        results = []
        for employee in employees:
            link = link_by_employee_id.get(employee.id)
            linked_at = link.create_date if link else False
            results.append({
                'id': employee.id,
                'name': employee.name,
                'department_name': employee.department_id.name if employee.department_id else '',
                'department_id': employee.department_id.id if employee.department_id else False,
                'telegram_username': self._get_employee_telegram_username(employee) or '',
                'telegram_chat_id': self._get_employee_telegram_chat_id(employee) or '',
                'telegram_user_id': '',
                'linked_at': linked_at.isoformat() if linked_at else False,
                'user_id': employee.user_id.id if employee.user_id else False,
                'user_name': employee.user_id.name if employee.user_id else '',
            })
        return results
