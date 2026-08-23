from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.addons.ab_odoo_connect import OdooConnectionSingleton


class AbSalesPosApi(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def _doctor_connection_unavailable_error(self):
        return UserError(_("No connection available."))

    @api.model
    def _prepare_main_doctor_values(self, values):
        name = (values or {}).get("name")
        vals = {
            "name": str(name or "").strip(),
            "code": str((values or {}).get("code") or "").strip(),
            "phone": str((values or {}).get("phone") or "").strip(),
            "specialty": str((values or {}).get("specialty") or "").strip(),
            "active": True,
        }
        if not vals["name"]:
            raise UserError(_("Doctor name is required."))
        self.env["ab_doctor"]._validate_doctor_code_format(vals["code"])
        self.env["ab_doctor"]._validate_doctor_specialty_value(vals["specialty"])
        return {key: value for key, value in vals.items() if value not in ("", None)}

    @api.model
    def _doctor_validation_error_substrings(self):
        return (
            "Doctor name is required",
            "Doctor code is required",
            "Doctor specialty is required",
            "Doctor code must contain only English letters and digits",
            "Doctor code already exists",
            "Doctor code must be unique",
        )

    @api.model
    def _main_doctor_code_lookup_domain(self, vals):
        return [("code", "=ilike", vals["code"])]

    @api.model
    def pos_create_main_doctor(self, values=None):
        vals = self._prepare_main_doctor_values(values or {})
        try:
            conn = OdooConnectionSingleton(self.env)
            remote_fields = conn.execute_kw(
                "ab_doctor",
                "fields_get",
                [],
                {"attributes": ["type"]},
            )
            remote_vals = {
                key: value for key, value in vals.items()
                if key in remote_fields
            }
            existing_ids = conn.execute_kw(
                "ab_doctor",
                "search",
                [self._main_doctor_code_lookup_domain(remote_vals)],
                {"limit": 1, "context": {"active_test": False}},
            )
            if existing_ids:
                raise UserError(_("Doctor code already exists."))

            doctor_id = int(conn.execute_kw("ab_doctor", "create", [remote_vals]))
            self.env["ab_odoo_replication"].sudo().replicate_model("ab_doctor")
        except UserError as error:
            message = str(error)
            if any(error_msg in message for error_msg in self._doctor_validation_error_substrings()):
                raise
            raise self._doctor_connection_unavailable_error()
        except Exception as error:
            message = str(error)
            if any(error_msg in message for error_msg in self._doctor_validation_error_substrings()):
                raise UserError(message)
            raise self._doctor_connection_unavailable_error()

        doctor = self.env["ab_doctor"].sudo().with_context(active_test=False).browse(doctor_id).exists()
        if not doctor:
            raise UserError(_("Doctor was created on main but was not replicated to this branch yet."))

        return {
            "id": doctor.id,
            "display_name": doctor.display_name,
        }

    @api.model
    def _default_doctor_prescription_line_flags(self, payload):
        header_vals = payload.get("header") or {}
        try:
            doctor_id = int(header_vals.get("doctor_id") or 0)
        except Exception:
            doctor_id = 0
        if not doctor_id:
            return

        lines = payload.get("lines") or []
        missing_flag_product_ids = []
        for line in lines:
            if not isinstance(line, dict) or "is_doctor_prescription_product" in line:
                continue
            try:
                product_id = int(line.get("product_id") or 0)
            except Exception:
                product_id = 0
            if product_id:
                missing_flag_product_ids.append(product_id)
        if not missing_flag_product_ids:
            return

        prescription_products = self.env["ab_product_doctor_prescription"].sudo().search([
            ("doctor_id", "=", doctor_id),
            ("product_id", "in", list(set(missing_flag_product_ids))),
            ("active", "=", True),
        ])
        prescription_product_ids = set(prescription_products.mapped("product_id").ids)
        for line in lines:
            if not isinstance(line, dict) or "is_doctor_prescription_product" in line:
                continue
            try:
                product_id = int(line.get("product_id") or 0)
            except Exception:
                product_id = 0
            line["is_doctor_prescription_product"] = product_id in prescription_product_ids

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        if payload is None and kwargs:
            payload = kwargs
        if isinstance(payload, dict):
            header_vals = payload.get("header") or {}
            if header_vals.get("is_doctor_prescription"):
                if not header_vals.get("doctor_id"):
                    raise UserError(_("Doctor is required for doctor prescription bills."))
                self._default_doctor_prescription_line_flags(payload)
                lines = payload.get("lines") or []
                if not any((line or {}).get("is_doctor_prescription_product") for line in lines):
                    raise UserError(_("At least one line must be marked as a prescription product."))
        return super().pos_submit(payload=payload)
