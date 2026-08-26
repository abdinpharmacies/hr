from odoo import api, models, _
from odoo.exceptions import UserError


class AbSalesPosApi(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def _validate_pos_hr_payload(self, payload):
        session_token = str(payload.get("pos_hr_session_token") or "").strip()
        if not session_token:
            raise UserError(_("Employee POS session is required."))

        session_api = self.env["ab_employee_access_sales_pos_api"]
        session = session_api._get_session(session_token, states=["active"])

        header_payload = payload.get("header") or {}
        try:
            store_id = int(header_payload.get("store_id") or 0)
        except Exception:
            store_id = 0
        if not store_id:
            raise UserError(_("Store is required."))
        if session.store_id.id != store_id:
            target_store = session_api._get_store(store_id, required=True)
            session_api._check_service_user(target_store)
            profile = session._get_pos_profile()
            if not profile or not profile._is_store_allowed_for_pos(target_store):
                raise UserError(_("Employee session does not match the selected store."))
            session.write({"store_id": target_store.id})

        profile = session._get_pos_profile()
        if not profile:
            raise UserError(_("Employee POS profile is missing."))

        session.mark_activity()
        return session

    @api.model
    def _pos_hr_is_remote_branch_submit(self):
        return self.env.user.has_group("ab_sales.group_call_center")

    @api.model
    def _pos_hr_header_metadata(self, session, selected_employee, profile=False, include_local_relations=True):
        vals = {
            "employee_id": selected_employee.id,
            "pos_hr_employee_id": session.employee_id.id,
            "pos_hr_device_uid": session.device_uid or False,
            "pos_hr_device_name": session.device_name or False,
            "pos_hr_device_ip": session.device_ip or False,
        }
        if include_local_relations:
            vals.update({
                "pos_hr_profile_id": profile.id if profile else False,
                "pos_hr_role_id": session.role_id.id if session.role_id else False,
                "pos_hr_shift_id": session.shift_id.id if session.shift_id else False,
                "pos_hr_session_id": session.id,
                "pos_hr_service_user_id": session.service_user_id.id if session.service_user_id else False,
            })
        else:
            vals.update({
                "pos_hr_profile_id": False,
                "pos_hr_role_id": False,
                "pos_hr_shift_id": False,
                "pos_hr_session_id": False,
                "pos_hr_service_user_id": False,
            })
        return vals

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        if payload is None and kwargs:
            payload = kwargs
        payload = dict(payload or {})
        session = self._validate_pos_hr_payload(payload)
        profile = session._get_pos_profile()

        header_payload = dict(payload.get("header") or {})
        selected_employee = self.env["ab_hr_employee"]
        try:
            selected_employee_id = int(header_payload.get("employee_id") or 0)
        except Exception:
            selected_employee_id = 0
        if selected_employee_id:
            selected_employee = self.env["ab_hr_employee"].sudo().browse(selected_employee_id).exists()[:1]
        if not selected_employee:
            selected_employee = session.employee_id
        header_payload.update(self._pos_hr_header_metadata(
            session=session,
            selected_employee=selected_employee,
            profile=profile,
            include_local_relations=not self._pos_hr_is_remote_branch_submit(),
        ))
        payload["header"] = header_payload

        try:
            result = super().pos_submit(payload=payload)
        except Exception as exc:
            self.env["ab_employee_access_sales_pos_api"]._log_operation(
                "sale_submit",
                session.employee_id,
                profile=profile,
                session=session,
                status="error",
                details={"message": str(exc)},
            )
            raise

        if isinstance(result, dict) and result.get("remote_callcenter"):
            self.env["ab_employee_access_sales_pos_api"]._log_operation(
                "sale_submit",
                session.employee_id,
                profile=profile,
                session=session,
                status="success",
                details={
                    "result_type": "remote_callcenter",
                    "remote_header_id": result.get("branch_header_id") or result.get("remote_header_id"),
                    "eplus_serial": result.get("eplus_serial"),
                },
            )
            return result

        header_id = result.get("pos_header_id") or result.get("id") if isinstance(result, dict) else False
        header = self.env["ab_sales_header"].sudo().browse(int(header_id or 0)).exists() if header_id else False
        if header:
            header.write(self._pos_hr_header_metadata(
                session=session,
                selected_employee=selected_employee,
                profile=profile,
                include_local_relations=True,
            ))
            self.env["ab_employee_access_sales_pos_api"]._log_operation(
                "sale_submit",
                session.employee_id,
                profile=profile,
                session=session,
                status="success",
                header=header,
                details={"result_type": result.get("type") if isinstance(result, dict) else ""},
            )
        return result
