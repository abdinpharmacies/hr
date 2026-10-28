from odoo import api, fields, models


class AbSalesHeader(models.Model):
    _inherit = "ab_sales_header"

    pos_hr_employee_id = fields.Many2one("ab_hr_employee", copy=False, index=True, readonly=True)
    pos_hr_profile_id = fields.Many2one("ab_employee_access", copy=False, index=True, readonly=True)
    pos_hr_role_id = fields.Many2one("ab_employee_access_sales_role", copy=False, index=True, readonly=True)
    pos_hr_shift_id = fields.Many2one("ab_employee_access_sales_shift", copy=False, index=True, readonly=True)
    pos_hr_session_id = fields.Many2one("ab_employee_access_sales_pos_session", copy=False, index=True, readonly=True)
    pos_hr_service_user_id = fields.Many2one("res.users", copy=False, index=True, readonly=True)
    pos_hr_device_uid = fields.Char(copy=False, index=True, readonly=True)
    pos_hr_device_name = fields.Char(copy=False, readonly=True)
    pos_hr_device_ip = fields.Char(copy=False, index=True, readonly=True)

    @api.model
    def _pos_context_store_scope(self):
        token = str(self.env.context.get("ab_pos_session_token") or "").strip()
        if not token:
            return False
        session_api = self.env["ab_employee_access_sales_pos_api"]
        session = session_api._get_session(token, states=["active"])
        return session_api._resolve_pos_store_scope(profile=session._get_pos_profile())

    @api.model
    def _get_allowed_store_ids(self):
        scope = self._pos_context_store_scope()
        if scope:
            return scope["available_store_ids"]
        return super()._get_allowed_store_ids()

    @api.model
    def _get_allowed_store_domain(self):
        scope = self._pos_context_store_scope()
        if scope:
            return (
                fields.Domain("active", "=", True)
                & fields.Domain("allow_sale", "=", True)
                & fields.Domain("id", "in", scope["available_store_ids"])
            )
        return super()._get_allowed_store_domain()

    @api.model
    def _get_eplus_emp_id(self, employee=False):
        token = str(self.env.context.get("ab_return_session_token") or "").strip()
        if token and not employee:
            session = self.env["ab_employee_access_sales_pos_api"]._get_session(token, states=["active", "locked"], required=False)
            if session and session.employee_id:
                employee = session.employee_id
        parent = getattr(super(), "_get_eplus_emp_id", None)
        if parent:
            return parent(employee=employee)
        employee = employee or self.employee_id
        return employee.costcenter_id.eplus_serial if employee and employee.costcenter_id else False
