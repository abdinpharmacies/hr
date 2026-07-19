from odoo import _, api, models


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.model
    def _dept_param(self, dept_code):
        return 'ab_supplier_claim_cycle.dept_manager_%s' % dept_code

    @api.model
    def _get_stored_manager(self, dept_code):
        icp = self.env['ir.config_parameter'].sudo()
        val = icp.get_param(self._dept_param(dept_code))
        if val and val.isdigit():
            try:
                Employee = self.env['ab_hr_employee'].sudo()
                return Employee.browse(int(val)).exists()
            except KeyError:
                pass
        return self.env['ab_hr_employee'].sudo().browse()

    @api.model
    def _store_manager(self, dept_code, employee):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(self._dept_param(dept_code), str(employee.id) if employee else '')

    @api.model
    def get_supplier_claim_dept_managers(self):
        CLAIM_GROUPS = [
            ('supplier_claim_group_inventory', 28, 'Supplier Claim Inventory', 'inventory'),
            ('supplier_claim_group_purchase', 29, 'Supplier Claim Purchase', 'purchase'),
            ('supplier_claim_group_suppliers', 527, 'Supplier Claim Suppliers', 'suppliers'),
            ('supplier_claim_group_bank_acc', 528, 'Supplier Claim Bank Acc', 'bank_accounts'),
            ('supplier_claim_group_tax_accounts', 530, 'Supplier Claim Tax Accounts', 'tax_accounts'),
        ]
        try:
            Department = self.env['ab_hr_department'].sudo()
        except KeyError:
            Department = None
        try:
            Employee = self.env['ab_hr_employee'].sudo()
        except KeyError:
            Employee = None
        results = []
        for xml_id, hr_dept_id, display_name, dept_code in CLAIM_GROUPS:
            group = self.env.ref(
                'ab_supplier_claim_workflow.%s' % xml_id, raise_if_not_found=False)
            manager = self._get_stored_manager(dept_code)
            if not manager and Department is not None:
                dept = Department.browse(hr_dept_id).exists()
                if dept and dept.manager_id:
                    manager = dept.manager_id
                    self._store_manager(dept_code, manager)
            if not manager:
                manager = Employee.browse() if Employee is not None else self.env['res.users'].browse()
            results.append({
                'dept_code': dept_code,
                'display_name': display_name,
                'group_id': group.id if group else False,
                'manager_id': manager.id if manager else False,
                'manager_name': manager.name if manager else False,
                'telegram_username': manager.telegram_username if manager else '',
                'has_telegram': bool(manager and manager.telegram_chat_id),
                'user_id': manager.user_id.id if manager and manager.user_id else False,
            })
        return results

    @api.model
    def assign_supplier_claim_manager(self, dept_code, employee_id):
        CLAIM_GROUP_MAP = {
            'inventory': 'supplier_claim_group_inventory',
            'purchase': 'supplier_claim_group_purchase',
            'suppliers': 'supplier_claim_group_suppliers',
            'bank_accounts': 'supplier_claim_group_bank_acc',
            'tax_accounts': 'supplier_claim_group_tax_accounts',
        }
        xml_id = CLAIM_GROUP_MAP.get(dept_code)
        if not xml_id:
            return {'error': _('Unknown department code: %s') % dept_code}
        group = self.env.ref(
            'ab_supplier_claim_workflow.%s' % xml_id, raise_if_not_found=False)
        if not group:
            return {'error': _('Security group not found: %s') % xml_id}
        try:
            Employee = self.env['ab_hr_employee'].sudo()
        except KeyError:
            return {'error': _('HR module not available')}
        employee = Employee.browse(employee_id).exists()
        if not employee:
            return {'error': _('Employee not found')}
        if not employee.telegram_chat_id:
            return {'error': _('Employee has no Telegram connection')}
        self._store_manager(dept_code, employee)
        if employee.user_id:
            group.sudo().write({'users': [(4, employee.user_id.id)]})
        return {
            'success': True,
            'manager_name': employee.name,
            'telegram_username': employee.telegram_username or '',
            'has_telegram': bool(employee.telegram_chat_id),
            'user_id': employee.user_id.id if employee.user_id else False,
        }

    @api.model
    def get_eligible_manager_candidates(self, exclude_dept_code=None):
        CLAIM_GROUP_MAP = {
            'inventory': 'supplier_claim_group_inventory',
            'purchase': 'supplier_claim_group_purchase',
            'suppliers': 'supplier_claim_group_suppliers',
            'bank_accounts': 'supplier_claim_group_bank_acc',
            'tax_accounts': 'supplier_claim_group_tax_accounts',
        }
        try:
            Employee = self.env['ab_hr_employee'].sudo()
        except KeyError:
            return []
        already_assigned_ids = set()
        for dept_code, xml_id in CLAIM_GROUP_MAP.items():
            if dept_code == exclude_dept_code:
                continue
            mgr = self._get_stored_manager(dept_code)
            if mgr:
                already_assigned_ids.add(mgr.id)
        candidates = Employee.search([
            ('telegram_chat_id', '!=', False),
            ('telegram_chat_id', '!=', ''),
            ('id', 'not in', list(already_assigned_ids)),
        ])
        return [{
            'id': e.id,
            'name': e.name,
            'telegram_username': e.telegram_username or '',
        } for e in candidates]

    @api.model
    def get_telegram_connected_employees(self):
        try:
            Employee = self.env['ab_hr_employee'].sudo()
        except KeyError:
            return []
        employees = Employee.search([
            ('telegram_chat_id', '!=', False),
            ('telegram_chat_id', '!=', ''),
        ], order='name')
        results = []
        for e in employees:
            linked_at = e.telegram_linked_at
            results.append({
                'id': e.id,
                'name': e.name,
                'department_name': e.department_id.name if e.department_id else '',
                'department_id': e.department_id.id if e.department_id else False,
                'telegram_username': e.telegram_username or '',
                'telegram_chat_id': e.telegram_chat_id or '',
                'telegram_user_id': e.telegram_user_id or '',
                'linked_at': linked_at.isoformat() if linked_at else False,
                'user_id': e.user_id.id if e.user_id else False,
                'user_name': e.user_id.name if e.user_id else '',
            })
        return results
