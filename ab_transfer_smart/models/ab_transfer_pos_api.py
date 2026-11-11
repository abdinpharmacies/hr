# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError

from .ab_transfer_header import SMART_GROUP_STORE_REVISION, SMART_STAGE_PRE_SUBMIT


class AbTransferPosApi(models.TransientModel):
    _inherit = "ab_transfer_pos_api"

    @api.model
    def _fast_transfer_pre_submit_enabled(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "ab_transfer_smart.fast_transfer_pre_submit_enabled"
        )
        if value in (None, False, ""):
            return True
        return str(value).strip().lower() not in ("0", "false", "no", "off")

    @api.model
    def _check_fast_transfer_pre_submit_access(self):
        if not self.env.user.has_group(SMART_GROUP_STORE_REVISION):
            raise AccessError(_("You are not allowed to perform this smart transfer action."))

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        if not self._fast_transfer_pre_submit_enabled():
            return super(
                AbTransferPosApi,
                self.with_context(fast_transfer_immediate_submit=True),
            ).pos_submit(payload=payload, **kwargs)

        self._check_fast_transfer_pre_submit_access()
        self._require_models("ab_transfer_header", "ab_transfer_line")
        if payload is None and kwargs:
            payload = kwargs
        if not payload or not isinstance(payload, dict):
            raise UserError(_("Invalid payload."))

        raw_header_vals = payload.get("header") or {}
        header_vals = self._filter_vals("ab_transfer_header", raw_header_vals)
        line_vals = payload.get("lines") or []
        header_vals["notes"] = self._format_transfer_notes(
            raw_header_vals.get("transfer_type") or raw_header_vals.get("notes_type"),
            raw_header_vals.get("notes"),
        )
        header_vals["smart_stage"] = SMART_STAGE_PRE_SUBMIT

        if not header_vals.get("from_store_id"):
            default_store = self._default_from_store()
            header_vals["from_store_id"] = default_store.id if default_store else False
        default_user = self._default_user()
        header_vals["user_id"] = default_user.id if default_user else False

        if not header_vals.get("from_store_id"):
            raise UserError(_("Source store is required."))
        if not header_vals.get("to_store_id"):
            raise UserError(_("Destination store is required."))
        if not header_vals.get("user_id"):
            raise UserError(_("User is required."))
        if not line_vals:
            raise UserError(_("At least one line is required."))

        transfer_request = self.env["ab_transfer_request"].browse()
        if header_vals.get("transfer_request_id"):
            self._require_models("ab_transfer_request")
            try:
                transfer_request_id = int(header_vals.get("transfer_request_id") or 0)
            except Exception:
                transfer_request_id = 0
            transfer_request = self._lock_transfer_request_for_submit(transfer_request_id)
            to_store = self.env["ab_store"].browse(int(header_vals.get("to_store_id") or 0)).exists()
            self._validate_pos_transfer_request(transfer_request, to_store)

        lines_to_create = []
        for line in line_vals:
            vals = self._filter_vals("ab_transfer_line", line or {})
            if vals.get("product_id"):
                lines_to_create.append(vals)

        if not lines_to_create:
            raise UserError(_("At least one valid line is required."))

        header = self.env["ab_transfer_header"].create(header_vals)
        for vals in lines_to_create:
            vals["header_id"] = header.id
        self.env["ab_transfer_line"].create(lines_to_create)

        return {
            "type": "ir.actions.act_window",
            "name": _("Transfer"),
            "res_model": "ab_transfer_header",
            "views": [(False, "form")],
            "view_mode": "form",
            "res_id": header.id,
            "target": "current",
        }
