import json

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError
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
        return [("active", "=", True), ("allow_sale", "=", True)]

    @api.model
    def _require_internal_user(self):
        if not self.env.user.active or self.env.user.share:
            raise AccessError(_("An active internal Odoo user is required to use POS."))
        return True

    @api.model
    def _connection_message(self):
        return _("Branch connection is not configured. Contact support.")

    @api.model
    def _resolve_pos_store_scope(self, profile=False):
        self._require_internal_user()
        Store = self.env["ab_store"].sudo()
        base_stores = Store.search(self._allowed_service_store_domain(), order="name, id")
        stores = base_stores
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        replica_store_ids = set()
        if replica_db and replica_db.allowed_sales_store_ids:
            replica_store_ids = set(replica_db.allowed_sales_store_ids.ids)
            stores = stores.filtered(lambda store: store.id in replica_store_ids)
        profile = profile.sudo().exists()[:1] if profile else self.env["ab_employee_access"]
        profile_store_ids = set()
        if profile and profile.pos_allowed_store_ids:
            profile_store_ids = set(profile.pos_allowed_store_ids.ids)
            stores = stores.filtered(lambda store: store.id in profile_store_ids)

        configs = self.env["ab_sales_branch_rpc_config"].sudo().with_context(active_test=False).search([
            ("store_id", "in", stores.ids),
        ])
        configs_by_store = {}
        for config in configs.sorted(lambda item: (not item.active, item.id)):
            configs_by_store.setdefault(config.store_id.id, config)

        rows = []
        available_stores = Store
        unavailable_message = self._connection_message()
        for store in stores:
            config = configs_by_store.get(store.id)
            ready = bool(
                config
                and config.active
                and config.enrollment_state == "ready"
                and config.can_post
                and config.api_key
            )
            if not config:
                connection_state = "not_configured"
            elif not config.active:
                connection_state = "inactive"
            elif config.enrollment_state != "ready" or not config.api_key:
                connection_state = "verification_required"
            elif not config.can_post:
                connection_state = "posting_disabled"
            else:
                connection_state = "ready"
            if ready:
                available_stores |= store
            rows.append({
                "id": store.id,
                "name": store.display_name or store.name or "",
                "code": store.code or "",
                "ip1": store.ip1 or "",
                "connection_ready": ready,
                "connection_state": connection_state,
                "connection_message": "" if ready else unavailable_message,
            })

        default_store = Store
        if replica_db and replica_db.default_sales_store_id in available_stores:
            default_store = replica_db.default_sales_store_id
        elif available_stores:
            default_store = available_stores[:1]

        restricted_to_empty = bool(base_stores and not stores and (replica_store_ids or profile_store_ids))
        if restricted_to_empty:
            empty_reason = "permission"
            empty_message = _("No stores match the Replica DB and employee permissions.")
        elif stores and not available_stores:
            empty_reason = "connection"
            empty_message = unavailable_message
        elif not stores:
            empty_reason = "no_stores"
            empty_message = _("No stores available.")
        else:
            empty_reason = ""
            empty_message = ""
        return {
            "visible_stores": stores,
            "available_stores": available_stores,
            "default_store": default_store,
            "stores": rows,
            "visible_store_ids": stores.ids,
            "available_store_ids": available_stores.ids,
            "empty_reason": empty_reason,
            "empty_message": empty_message,
        }

    @api.model
    def _require_connectable_store(self, store_id, profile=False):
        try:
            parsed_store_id = int(store_id or 0)
        except Exception:
            parsed_store_id = 0
        scope = self._resolve_pos_store_scope(profile=profile)
        if parsed_store_id not in scope["visible_store_ids"]:
            raise AccessError(_("Selected store is outside the effective POS scope."))
        if parsed_store_id not in scope["available_store_ids"]:
            raise UserError(self._connection_message())
        return scope["available_stores"].filtered(lambda store: store.id == parsed_store_id)[:1]

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
            raise UserError(_("Selected store is not available for POS."))
        return store

    @api.model
    def _available_stores_for_profile(self, profile):
        return self._resolve_pos_store_scope(profile=profile)["available_stores"]

    @api.model
    def _check_service_user(self, store):
        store = store.exists()
        if not store:
            raise UserError(_("Store not found."))
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
        self._require_internal_user()
        session = self.env["ab_employee_access_sales_pos_session"].sudo().search(
            self._session_domain(session_token, states=states) + [("service_user_id", "=", self.env.uid)],
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
        session_payload = False
        session = self.env["ab_employee_access_sales_pos_session"]
        profile = self.env["ab_employee_access"]
        if session_token:
            session = self._get_session(session_token, states=["active", "locked"], required=False)
            if session:
                profile = session._get_pos_profile()
        scope = self._resolve_pos_store_scope(profile=profile)
        if session and session.store_id.id in scope["available_store_ids"]:
            session_payload = session.payload()
        default_store = scope["default_store"]
        return {
            "stores": scope["stores"],
            "visible_store_ids": scope["visible_store_ids"],
            "available_store_ids": scope["available_store_ids"],
            "allowed_store_ids": scope["available_store_ids"],
            "default_store_id": default_store.id if default_store else False,
            "empty_reason": scope["empty_reason"],
            "empty_message": scope["empty_message"],
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

        permissions = profile._effective_pos_permissions()
        if not permissions.get("allow_pos_screen"):
            raise UserError(_("Employee role does not allow POS screen access."))
        scope = self._resolve_pos_store_scope(profile=profile)
        if store_id:
            store = self._require_connectable_store(store_id, profile=profile)
        else:
            store = scope["default_store"]
            if not store:
                raise UserError(scope["empty_message"] or _("No POS store is available for this employee."))

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
        self._require_connectable_store(session.store_id.id, profile=profile)
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
        self._require_connectable_store(session.store_id.id, profile=session._get_pos_profile())
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
        profile = session._get_pos_profile()
        if not profile:
            raise UserError(_("Employee POS profile is missing."))
        store = self._require_connectable_store(store_id, profile=profile)
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
