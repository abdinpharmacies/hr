from odoo import api, models, _
from odoo.exceptions import UserError


class AbSalesPosApi(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def _require_pos_operation_session(self, pos_hr_session_token=None, store_id=False):
        token = str(pos_hr_session_token or self.env.context.get("ab_pos_session_token") or "").strip()
        session_api = self.env["ab_employee_access_sales_pos_api"]
        session = session_api._get_session(token, states=["active"])
        profile = session._get_pos_profile()
        if not profile:
            raise UserError(_("Employee POS profile is missing."))
        target_store_id = store_id or session.store_id.id
        store = session_api._require_connectable_store(target_store_id, profile=profile)
        if session.store_id != store:
            session.write({"store_id": store.id})
        session.mark_activity()
        return session

    @api.model
    def pos_promotions(self, store_id=None, lines=None, applied_program_id=None, manual_clear=False,
                       contract_id=None, total_invoice_discount=0.0, customer_id=None,
                       pos_hr_session_token=None):
        session = self._require_pos_operation_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesPosApi, self.with_context(ab_pos_session_token=session.session_token)).pos_promotions(
            store_id=store_id,
            lines=lines,
            applied_program_id=applied_program_id,
            manual_clear=manual_clear,
            contract_id=contract_id,
            total_invoice_discount=total_invoice_discount,
            customer_id=customer_id,
        )

    @api.model
    def pos_product_details(self, store_id, product_id, pos_hr_session_token=None):
        session = self._require_pos_operation_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesPosApi, self.with_context(ab_pos_session_token=session.session_token)).pos_product_details(
            store_id,
            product_id,
        )

    @api.model
    def pos_barcode_products(self, barcode=None, store_id=None, pos_hr_session_token=None):
        session = self._require_pos_operation_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesPosApi, self.with_context(ab_pos_session_token=session.session_token)).pos_barcode_products(
            barcode=barcode,
            store_id=store_id,
        )

    @api.model
    def pos_barcode_temp_products(self, barcode=None, pos_hr_session_token=None):
        session = self._require_pos_operation_session(pos_hr_session_token)
        return super(AbSalesPosApi, self.with_context(ab_pos_session_token=session.session_token)).pos_barcode_temp_products(
            barcode=barcode,
        )

    @api.model
    def pos_link_barcode_temp(self, barcode=None, product_ids=None, pos_hr_session_token=None):
        session = self._require_pos_operation_session(pos_hr_session_token)
        return super(AbSalesPosApi, self.with_context(ab_pos_session_token=session.session_token)).pos_link_barcode_temp(
            barcode=barcode,
            product_ids=product_ids,
        )

    @api.model
    def pos_cached_balance_totals(self, product_ids=None, store_id=None, include_sync_metadata=False,
                                  pos_hr_session_token=None):
        session = self._require_pos_operation_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesPosApi, self.with_context(ab_pos_session_token=session.session_token)).pos_cached_balance_totals(
            product_ids=product_ids,
            store_id=store_id,
            include_sync_metadata=include_sync_metadata,
        )

    @api.model
    def pos_refresh_search_balances(self, store_id=None, product_ids=None, pos_hr_session_token=None):
        session = self._require_pos_operation_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesPosApi, self.with_context(ab_pos_session_token=session.session_token)).pos_refresh_search_balances(
            store_id=store_id,
            product_ids=product_ids,
        )

    @api.model
    def pos_refresh_pos_balances(self, store_id=None, product_ids=None, include_sync_metadata=False,
                                 pos_hr_session_token=None):
        session = self._require_pos_operation_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesPosApi, self.with_context(ab_pos_session_token=session.session_token)).pos_refresh_pos_balances(
            store_id=store_id,
            product_ids=product_ids,
            include_sync_metadata=include_sync_metadata,
        )

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
        profile = session._get_pos_profile()
        if not profile:
            raise UserError(_("Employee POS profile is missing."))
        target_store = session_api._require_connectable_store(store_id, profile=profile)
        if session.store_id != target_store:
            session.write({"store_id": target_store.id})

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
