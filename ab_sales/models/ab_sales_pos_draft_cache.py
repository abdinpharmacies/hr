# -*- coding: utf-8 -*-

from odoo import api, fields, models



class AbSalesPosDraftCache(models.Model):
    _name = "ab_sales_pos_draft_cache"
    _description = "Sales POS Draft Cache"
    _rec_name = "pos_client_token"
    _order = "write_date desc, id desc"

    pos_client_token = fields.Char(required=True, index=True, copy=False)
    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="restrict")
    employee_id = fields.Many2one("ab_hr_employee", index=True, ondelete="restrict")
    store_id = fields.Many2one("ab_store", required=True, index=True, ondelete="restrict")
    bill_json = fields.Json(default=dict)
    revision = fields.Integer(default=1, required=True)
    state = fields.Selection([("active", "Active"), ("retired", "Retired"),
                              ("completed", "Completed")], default="active", required=True, index=True)
    last_synced_at = fields.Datetime()

    _uniq_pos_client_token = models.Constraint(
        "UNIQUE(pos_client_token)", "A saved draft already exists for this POS token.")

    @api.model
    def _payload_invalid_reason(self, payload, token=None, store_id=None):
        if not isinstance(payload, dict) or not payload:
            return "missing_bill_json"
        header = payload.get("header")
        if not isinstance(header, dict):
            return "invalid_header"
        payload_token = header.get("pos_client_token")
        if not isinstance(payload_token, str) or not payload_token.strip() or len(payload_token.strip()) > 128:
            return "missing_pos_client_token"
        payload_store = header.get("store_id")
        if type(payload_store) is not int or payload_store <= 0:
            return "missing_store_id"
        if token is not None and payload_token.strip() != token:
            return "token_mismatch"
        if store_id is not None and payload_store != store_id:
            return "store_mismatch"
        if (not isinstance(payload.get("lines", []), list)
                or any(not isinstance(line, dict) for line in payload.get("lines", []))
                or not isinstance(payload.get("promo", {}), dict)):
            return "invalid_payload_structure"
        return None



class AbSalesPosDraftScope(models.Model):
    _name = "ab_sales_pos_draft_scope"
    _description = "POS Draft Capacity Scope"

    user_id = fields.Many2one("res.users", required=True, ondelete="restrict", index=True)
    employee_key = fields.Integer(required=True, default=0)
    revision = fields.Integer(default=0)

    _uniq_owner = models.Constraint("UNIQUE(user_id, employee_key)", "Draft capacity scope already exists.")
