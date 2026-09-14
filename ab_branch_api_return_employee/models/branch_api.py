from odoo import api, models, _
from odoo.exceptions import UserError


class BranchApiReturnEmployee(models.AbstractModel):
    _inherit = 'ab_branch_api'

    @api.model
    def submit_return(self, db_serial, invoice, token, lines, notes='', employee_ref=False):
        store = self._scope(db_serial)
        self._business_permissions('return', post=True)
        operation = self._operation(store, token, 'return')
        # Let the provider retain ownership, locking and replay/reconciliation rules.
        # Draft operation creation is transactional; no invoice is reserved here.
        if operation.state == 'draft':
            self._validate_return_employee(employee_ref)
        return super().submit_return(db_serial, invoice, token, lines, notes, employee_ref)

    @api.model
    def _validate_return_employee(self, employee_ref):
        if not employee_ref:
            raise UserError(_('A return employee is required. Log in to the callcenter POS or select a return employee in the Administrator return form.'))
        try:
            employee = self.with_context(active_test=False)._resolve('ab_hr_employee', employee_ref)
        except UserError as error:
            raise UserError(_('The return employee is missing or ambiguous on this branch. Check the employee cost center code.')) from error
        employee.check_access('read')
        costcenter = employee.costcenter_id
        costcenter.check_access('read')
        if not employee.active or not costcenter or not costcenter.active:
            raise UserError(_('The return employee and employee cost center must be active on this branch.'))
        if costcenter.eplus_serial <= 0:
            raise UserError(_('The return employee has no valid E-Plus mapping on this branch. Configure the employee cost center E-Plus serial before retrying.'))
        return employee
