import json

from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.http import request


class AbSalesHrPosApi(models.TransientModel):
    _name = "ab_employee_access_sales_pos_api"
    _description = "Sales HR POS API"

    @api.model
    def _client_ip(self):
        if request and getattr(request, "httprequest", None):
            http_request = request.httprequest
            forwarded = http_request.headers.get("X-Forwarded-For")
            if forwarded:
                first_hop = forwarded.split(",")[0].strip()
                if first_hop:
                    return first_hop
            return getattr(http_request, "remote_addr", "") or ""
        return ""

    @api.model
    def _allowed_service_store_domain(self):
        domain = [("allow_sale", "=", True)]
        if self.env.user.has_group("base.group_system"):
            return domain
        domain.extend(["|", ("pos_service_user_id", "=", False), ("pos_service_user_id", "=", self.env.user.id)])
        return domain

    @api.model
    def _get_store(self, store_id, required=True):
        try:
            parsed_store_id = int(store_id or 0)
        except Exception:
            parsed_store_id = 0
        store = self.env["ab_store"].sudo().search(
            self._allowed_service_store_domain() + [("id", "=", parsed_store_id)],
            limit=1,
        )
        if required and not store:
            raise UserError(_("Selected store is not available for the current service user."))
        return store

    @api.model
    def _available_stores_for_profile(self, profile):
        profile = profile.sudo().exists()[:1]
        stores = self.env["ab_store"].sudo().search(self._allowed_service_store_domain(), order="name")
        if not profile:
            return stores
        if profile.pos_allowed_store_ids:
            stores = stores.filtered(lambda store: store.id in profile.pos_allowed_store_ids.ids)
        return stores

    @api.model
    def _check_service_user(self, store):
        store = store.exists()
        if not store:
            raise UserError(_("Store not found."))
        if self.env.user.has_group("base.group_system"):
            return True
        service_user = store.pos_service_user_id
        if service_user and service_user.id != self.env.user.id:
            raise UserError(_("Store %s is assigned to another service user.") % (store.display_name,))
        return True

    @api.model
    def _normalize_device_uid(self, device_uid):
        value = str(device_uid or "").strip()
        return value or f"browser_{self.env.user.id}"

    @api.model
    def _normalize_device_name(self, device_name, store=False):
        value = str(device_name or "").strip()
        if value:
            return value
        if store:
            return f"{store.code or 'POS'} Terminal"
        return f"POS Terminal {self.env.user.id}"

    @api.model
    def _session_domain(self, session_token, states=None):
        token = str(session_token or "").strip()
        domain = [("session_token", "=", token)]
        if states:
            domain.append(("state", "in", list(states)))
        return domain

    @api.model
    def _get_session(self, session_token, states=None, required=True):
        session = self.env["ab_employee_access_sales_pos_session"].sudo().search(
            self._session_domain(session_token, states=states),
            limit=1,
        )
        if required and not session:
            raise UserError(_("Employee POS session is missing or expired."))
        return session

    @api.model
    def _log_operation(
            self,
            operation_type,
            employee,
            profile=False,
            session=False,
            status="success",
            manager_employee=False,
            header=False,
            details=None,
    ):
        employee = employee.sudo().exists()[:1]
        if not employee:
            return False
        session = session.sudo().exists()[:1] if session else self.env["ab_employee_access_sales_pos_session"]
        if profile:
            profile = profile.sudo().exists()[:1]
        elif session:
            profile = session._get_pos_profile()
        else:
            profile = self.env["ab_employee_access"]
        values = {
            "employee_id": employee.id,
            "profile_id": profile.id if profile else False,
            "role_id": profile.pos_role_id.id if profile and profile.pos_role_id else False,
            "operation_type": operation_type,
            "operation_status": status,
            "details_json": json.dumps(details or {}, ensure_ascii=False) if details else False,
        }
        if session:
            values.update({
                "session_id": session.id,
                "shift_id": session.shift_id.id if session.shift_id else False,
                "store_id": session.store_id.id if session.store_id else False,
                "service_user_id": session.service_user_id.id if session.service_user_id else False,
                "device_uid": session.device_uid or False,
                "device_name": session.device_name or False,
                "device_ip": session.device_ip or False,
            })
        if manager_employee:
            values["manager_employee_id"] = manager_employee.id
        if header:
            values["header_id"] = header.id
        return self.env["ab_employee_access_sales_operation_log"].sudo().create(values)

    @api.model
    def _close_other_device_sessions(self, device_uid, service_user):
        sessions = self.env["ab_employee_access_sales_pos_session"].sudo().search([
            ("device_uid", "=", device_uid),
            ("service_user_id", "=", service_user.id),
            ("state", "in", ["active", "locked"]),
        ])
        for session in sessions:
            profile = session._get_pos_profile()
            self._log_operation(
                "logout",
                session.employee_id,
                profile=profile,
                session=session,
                status="success",
                details={"reason": "replaced_by_new_login"},
            )
        sessions.close_session()
        return True

    @api.model
    def pos_bootstrap(self, session_token=False, store_id=False, device_uid="", device_name=""):
        stores = self.env["ab_store"].sudo().search(self._allowed_service_store_domain(), order="name")
        session_payload = False
        if session_token:
            session = self._get_session(session_token, states=["active", "locked"], required=False)
            if session:
                session_payload = session.payload()
        current_store = self._get_store(store_id, required=False) if store_id else self.env["ab_store"]
        default_store = current_store[:1] or stores[:1]
        return {
            "allowed_store_ids": stores.ids,
            "default_store_id": default_store.id if default_store else False,
            "service_user_id": self.env.user.id,
            "service_user_name": self.env.user.display_name,
            "require_employee_login": True,
            "session": session_payload,
            "device_uid": self._normalize_device_uid(device_uid),
            "device_name": self._normalize_device_name(device_name, store=default_store),
            "device_ip": self._client_ip(),
        }

    @api.model
    def employee_login(
        self,
        employee_code="",
        pin="",
        store_id=False,
        device_uid="",
        device_name="",
        employee_id=False,
        employee_access_id=False,
    ):
        employee_code = str(employee_code or "").strip()
        pin = str(pin or "").strip()
        try:
            employee_id = int(employee_id or 0)
        except Exception:
            employee_id = 0
        try:
            employee_access_id = int(employee_access_id or 0)
        except Exception:
            employee_access_id = 0
        if (not employee_id and not employee_access_id and not employee_code) or not pin:
            raise UserError(_("Employee and PIN are required."))
        profile = self.env["ab_employee_access"]
        if employee_access_id:
            profile = self.env["ab_employee_access"].sudo().browse(employee_access_id).exists()[:1]
        elif employee_id:
            profile = self.env["ab_employee_access"].sudo().search([
                ("employee_id", "=", employee_id),
                ("pos_allow_login", "=", True),
            ], limit=1)
        elif employee_code:
            profile = self.env["ab_employee_access"].sudo()._find_by_employee_code(employee_code).exists()
        employee = profile.employee_id
        if not profile or not employee or not profile.pos_allow_login:
            raise UserError(_("Employee is invalid or POS login is disabled."))
        if not profile.check_pos_pin(pin):
            raise UserError(_("Employee PIN is invalid."))

        if store_id:
            store = self._get_store(store_id, required=True)
            self._check_service_user(store)
            if not profile._is_store_allowed_for_pos(store):
                raise UserError(_("Employee is not allowed to work in store %s.") % (store.display_name,))
        else:
            store = self._available_stores_for_profile(profile)[:1]
            if not store:
                raise UserError(_("No POS store is available for this employee."))

        permissions = profile._effective_pos_permissions()
        if not permissions.get("allow_pos_screen"):
            raise UserError(_("Employee role does not allow POS screen access."))

        normalized_device_uid = self._normalize_device_uid(device_uid)
        normalized_device_name = self._normalize_device_name(device_name, store=store)
        self._close_other_device_sessions(normalized_device_uid, self.env.user)

        session = self.env["ab_employee_access_sales_pos_session"].sudo().create({
            "employee_id": employee.id,
            "profile_id": profile.id,
            "role_id": profile.pos_role_id.id if profile.pos_role_id else False,
            "service_user_id": self.env.user.id,
            "store_id": store.id,
            "device_uid": normalized_device_uid,
            "device_name": normalized_device_name,
            "device_ip": self._client_ip(),
            "state": "active",
        })
        self._log_operation(
            "login",
            employee,
            profile=profile,
            session=session,
            status="success",
            details={"store_id": store.id},
        )
        return session.payload()

    @api.model
    def lock_session(self, session_token, reason="idle"):
        session = self._get_session(session_token, states=["active"])
        profile = session._get_pos_profile()
        session.lock_session()
        self._log_operation(
            "lock",
            session.employee_id,
            profile=profile,
            session=session,
            status="success",
            details={"reason": reason},
        )
        return session.payload()

    @api.model
    def unlock_session(self, session_token, pin):
        session = self._get_session(session_token, states=["locked"])
        profile = session._get_pos_profile()
        if not profile or not profile.check_pos_pin(pin):
            raise UserError(_("Employee PIN is invalid."))
        session.unlock_session()
        self._log_operation(
            "unlock",
            session.employee_id,
            profile=profile,
            session=session,
            status="success",
            details={"unlock_count": session.unlock_count},
        )
        return session.payload()

    @api.model
    def logout_session(self, session_token, close_shift=True):
        session = self._get_session(session_token, states=["active", "locked"])
        self._log_operation(
            "logout",
            session.employee_id,
            profile=session._get_pos_profile(),
            session=session,
            status="success",
        )
        session.close_session()
        return {"closed": True}

    @api.model
    def heartbeat(self, session_token):
        session = self._get_session(session_token, states=["active"])
        session.mark_activity()
        return session.payload()

    @api.model
    def log_operation(self, session_token, operation_type, status="success", details=None, header_id=False):
        session = self._get_session(session_token, states=["active", "locked"])
        header = self.env["ab_sales_header"].sudo().browse(int(header_id or 0)).exists() if header_id else False
        self._log_operation(
            operation_type,
            session.employee_id,
            profile=session._get_pos_profile(),
            session=session,
            status=status,
            header=header,
            details=details,
        )
        return {"ok": True}

    @api.model
    def change_store(self, session_token, store_id):
        session = self._get_session(session_token, states=["active", "locked"])
        store = self._get_store(store_id, required=True)
        self._check_service_user(store)
        profile = session._get_pos_profile()
        if not profile or not profile._is_store_allowed_for_pos(store):
            raise UserError(_("Employee is not allowed to work in store %s.") % (store.display_name,))
        if session.store_id != store:
            session.write({"store_id": store.id})
            self._log_operation(
                "change_store",
                session.employee_id,
                profile=profile,
                session=session,
                status="success",
                details={"action": "change_store", "store_id": store.id},
            )
        return session.payload()
