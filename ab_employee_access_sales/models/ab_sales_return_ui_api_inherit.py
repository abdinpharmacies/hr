from odoo import api, models, _
from odoo.exceptions import UserError


class AbSalesReturnUiApi(models.TransientModel):
    _inherit = "ab_sales_return_ui_api"

    @api.model
    def _validate_return_employee_session(self, return_header_id, session_token, states=None):
        token = str(session_token or self.env.context.get("ab_return_session_token") or "").strip()
        if not token:
            raise UserError(_("Employee login is required."))

        session_api = self.env["ab_employee_access_sales_pos_api"]
        session = session_api._get_session(token, states=states or ["active"])
        profile = session._get_pos_profile()
        if not profile:
            raise UserError(_("Employee POS profile is missing."))

        permissions = profile._effective_pos_permissions()
        if not permissions.get("allow_return_screen"):
            raise UserError(_("Employee role does not allow sales return screen access."))

        header = self._get_return_header(return_header_id)
        target_store = header.store_id
        if not target_store:
            raise UserError(_("Sales return store is missing."))

        session_api._check_service_user(target_store)
        if not profile._is_store_allowed_for_pos(target_store):
            raise UserError(_("Employee is not allowed to work in store %s.") % (target_store.display_name,))

        if session.store_id != target_store:
            session.write({"store_id": target_store.id})

        session.mark_activity()
        return session

    @api.model
    def get_state(self, return_header_id, session_token=False):
        self._validate_return_employee_session(return_header_id, session_token, states=["active"])
        return super().get_state(return_header_id)

    @api.model
    def save_notes(self, return_header_id, notes="", session_token=False):
        self._validate_return_employee_session(return_header_id, session_token, states=["active"])
        return super(AbSalesReturnUiApi, self.with_context(ab_return_session_token=str(session_token or "").strip())).save_notes(
            return_header_id,
            notes=notes,
        )

    @api.model
    def update_line(self, return_header_id, line_id, qty_str=None, uom_id=False, session_token=False):
        self._validate_return_employee_session(return_header_id, session_token, states=["active"])
        return super(AbSalesReturnUiApi, self.with_context(ab_return_session_token=str(session_token or "").strip())).update_line(
            return_header_id,
            line_id,
            qty_str=qty_str,
            uom_id=uom_id,
        )

    @api.model
    def reload_lines(self, return_header_id, session_token=False):
        self._validate_return_employee_session(return_header_id, session_token, states=["active"])
        return super(AbSalesReturnUiApi, self.with_context(ab_return_session_token=str(session_token or "").strip())).reload_lines(
            return_header_id
        )

    @api.model
    def clear_lines(self, return_header_id, session_token=False):
        self._validate_return_employee_session(return_header_id, session_token, states=["active"])
        return super(AbSalesReturnUiApi, self.with_context(ab_return_session_token=str(session_token or "").strip())).clear_lines(
            return_header_id
        )

    @api.model
    def total_return_invoice(self, return_header_id, session_token=False):
        self._validate_return_employee_session(return_header_id, session_token, states=["active"])
        return super(AbSalesReturnUiApi, self.with_context(ab_return_session_token=str(session_token or "").strip())).total_return_invoice(
            return_header_id
        )

    @api.model
    def set_pending(self, return_header_id, session_token=False):
        self._validate_return_employee_session(return_header_id, session_token, states=["active"])
        return super(AbSalesReturnUiApi, self.with_context(ab_return_session_token=str(session_token or "").strip())).set_pending(
            return_header_id
        )

    @api.model
    def push_to_eplus(self, return_header_id, session_token=False):
        self._validate_return_employee_session(return_header_id, session_token, states=["active"])
        return super(AbSalesReturnUiApi, self.with_context(ab_return_session_token=str(session_token or "").strip())).push_to_eplus(
            return_header_id
        )
