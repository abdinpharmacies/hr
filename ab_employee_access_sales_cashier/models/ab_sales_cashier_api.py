from odoo import api, models, _
from odoo.exceptions import AccessError, UserError


class SalesCashierApi(models.TransientModel):
    _inherit = "ab_sales_cashier_api"

    @api.model
    def _cashier_requires_pin_login(self):
        return True

    @api.model
    def _store_domain_for_cashier(self, profile=False):
        domain = super()._store_domain_for_cashier(profile=profile)
        profile = profile.sudo().exists()[:1] if profile else self.env["ab_employee_access"]
        if profile and profile.pos_allowed_store_ids:
            domain.append(("id", "in", profile.pos_allowed_store_ids.ids))
        return domain

    @api.model
    def _get_cashier_employee_eplus_id(self, session=False):
        session = session.sudo().exists()[:1] if session else self.env["ab_employee_access_sales_pos_session"]
        if session and session.employee_id:
            employee = session.employee_id.sudo()
            serial = self._safe_int(employee.costcenter_id.eplus_serial if employee.costcenter_id else 0, 0)
            if serial:
                return serial
        return super()._get_cashier_employee_eplus_id(session=session)

    @api.model
    def _get_pos_hr_api(self):
        if "ab_employee_access_sales_pos_api" not in self.env.registry:
            raise UserError(_("POS HR module is required for cashier PIN access."))
        return self.env["ab_employee_access_sales_pos_api"]

    @api.model
    def _coerce_cashier_session(self, session_token=False, states=None, required=True):
        token = str(session_token or "").strip()
        if not token:
            if required:
                raise UserError(_("Cashier PIN login is required."))
            return self.env["ab_employee_access_sales_pos_session"]
        allowed_states = list(states or ["active"])
        return self._get_pos_hr_api()._get_session(token, states=allowed_states, required=required)

    @api.model
    def _ensure_cashier_pin_access(self, session):
        session = session.sudo().exists()[:1]
        if not session:
            raise UserError(_("Cashier PIN login is required."))
        profile = session._get_pos_profile().sudo().exists()[:1]
        if not profile:
            raise UserError(_("Employee POS profile is missing."))
        permissions = profile._effective_pos_permissions()
        if not permissions.get("allow_cashier_screen"):
            raise AccessError(_("Employee role does not allow cashier screen access."))
        return profile

    @api.model
    def _resolve_cashier_context(self, session_token=False, store_id=None, require_connection=False):
        pos_api = self._get_pos_hr_api()
        session = self._coerce_cashier_session(session_token=session_token, states=["active"], required=True)
        profile = self._ensure_cashier_pin_access(session)
        requested_store_id = self._safe_int(store_id, 0)
        if requested_store_id and session.store_id.id != requested_store_id:
            pos_api.change_store(session_token=session.session_token, store_id=requested_store_id)
            session = self._coerce_cashier_session(
                session_token=session.session_token,
                states=["active"],
                required=True,
            )
            profile = self._ensure_cashier_pin_access(session)
        store = self._coerce_store(
            store_id=session.store_id.id,
            required=True,
            require_connection=require_connection,
            profile=profile,
        )
        if session.store_id.id != store.id:
            pos_api.change_store(session_token=session.session_token, store_id=store.id)
            session = self._coerce_cashier_session(
                session_token=session.session_token,
                states=["active"],
                required=True,
            )
            profile = self._ensure_cashier_pin_access(session)
            store = session.store_id
        return session, profile, store

    @api.model
    def _cashier_bootstrap_payload(self, session=False, profile=False):
        payload = super()._cashier_bootstrap_payload(session=session, profile=profile)
        session = session.sudo().exists()[:1] if session else self.env["ab_employee_access_sales_pos_session"]
        profile = profile.sudo().exists()[:1] if profile else self.env["ab_employee_access"]
        employee_name = ""
        employee_code = ""
        employee_id = False
        employee_access_id = False
        if session:
            employee_id = session.employee_id.id
            employee_name = session.employee_id.display_name or session.employee_id.name or ""
        if profile:
            employee_id = employee_id or profile.employee_id.id
            employee_access_id = profile.id
            employee_code = profile.employee_id.barcode or profile.employee_id.accid or ""
        payload.update({
            "require_pin_login": True,
            "session_token": session.session_token if session else False,
            "session_id": session.id if session else False,
            "employee_id": employee_id,
            "employee_access_id": employee_access_id,
            "employee_name": employee_name,
            "employee_code": employee_code,
        })
        return payload

    @api.model
    def get_cashier_bootstrap(self, session_token=False):
        self._require_cashier_access()
        session = self._coerce_cashier_session(
            session_token=session_token,
            states=["active"],
            required=False,
        ) if session_token else self.env["ab_employee_access_sales_pos_session"]
        profile = self.env["ab_employee_access"]
        if session:
            profile = self._ensure_cashier_pin_access(session)
        return self._cashier_bootstrap_payload(session=session, profile=profile)

    @api.model
    def cashier_pin_login(
        self,
        employee_code="",
        pin="",
        device_uid="",
        device_name="",
        employee_id=False,
        employee_access_id=False,
    ):
        self._require_cashier_access()
        employee_code = str(employee_code or "").strip()
        employee_id = self._safe_int(employee_id, 0)
        employee_access_id = self._safe_int(employee_access_id, 0)
        pin = str(pin or "").strip()
        if not pin:
            raise UserError(_("Employee and PIN are required."))
        pos_api = self._get_pos_hr_api()
        profile = self.env["ab_employee_access"]
        if employee_id:
            profile = self.env["ab_employee_access"].sudo().search([
                ("employee_id", "=", employee_id),
                ("pos_allow_login", "=", True),
            ], limit=1)
        elif employee_access_id:
            profile = self.env["ab_employee_access"].sudo().browse(employee_access_id).exists()[:1]
        elif employee_code:
            profile = self.env["ab_employee_access"].sudo()._find_by_employee_code(employee_code).exists()[:1]
        if not profile:
            raise UserError(_("Employee is invalid or POS login is disabled."))
        employee_id = self._safe_int(profile.employee_id.id if profile.employee_id else 0, 0)
        if not employee_id:
            raise UserError(_("Selected employee has no POS profile."))
        if not employee_code:
            employee_code = (
                profile.employee_id.barcode
                or profile.employee_id.accid
                or ""
            ).strip()
        store_settings = self._get_cashier_store_settings(profile=profile)
        default_store_id = self._safe_int(store_settings.get("default_store_id"), 0)
        login_payload = pos_api.employee_login(
            employee_id=employee_id,
            employee_code=employee_code,
            pin=pin,
            store_id=default_store_id or False,
            device_uid=device_uid,
            device_name=device_name,
        )
        session_token = str(login_payload.get("token") or "").strip()
        session = self._coerce_cashier_session(session_token=session_token, states=["active"], required=True)
        profile = self._ensure_cashier_pin_access(session)
        return self._cashier_bootstrap_payload(session=session, profile=profile)

    @api.model
    def cashier_change_store(self, session_token, store_id):
        self._require_cashier_access()
        session = self._coerce_cashier_session(session_token=session_token, states=["active"], required=True)
        self._ensure_cashier_pin_access(session)
        parsed_store_id = self._safe_int(store_id, 0)
        if not parsed_store_id:
            raise UserError(_("Store is required."))
        self._get_pos_hr_api().change_store(session_token=session.session_token, store_id=parsed_store_id)
        session = self._coerce_cashier_session(session_token=session.session_token, states=["active"], required=True)
        profile = self._ensure_cashier_pin_access(session)
        payload = self._cashier_bootstrap_payload(session=session, profile=profile)
        payload.update({
            "store_id": session.store_id.id if session.store_id else False,
            "store_name": session.store_id.display_name if session.store_id else "",
        })
        return payload

    @api.model
    def get_pending_invoices(self, limit=300, store_id=None, session_token=False):
        payload = super().get_pending_invoices(limit=limit, store_id=store_id, session_token=session_token)
        session = self._coerce_cashier_session(
            session_token=session_token,
            states=["active"],
            required=False,
        ) if session_token else self.env["ab_employee_access_sales_pos_session"]
        payload["session_token"] = session.session_token if session else False
        return payload

    @api.model
    def get_store_wallets(self, store_id=None, session_token=False):
        payload = super().get_store_wallets(store_id=store_id, session_token=session_token)
        session = self._coerce_cashier_session(
            session_token=session_token,
            states=["active"],
            required=False,
        ) if session_token else self.env["ab_employee_access_sales_pos_session"]
        payload["session_token"] = session.session_token if session else False
        return payload

    @api.model
    def cashier_logout(self, session_token=False):
        self._require_cashier_access()
        token = str(session_token or "").strip()
        if token:
            self._get_pos_hr_api().logout_session(session_token=token)
        return {"closed": True}
