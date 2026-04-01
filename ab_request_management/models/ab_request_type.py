from odoo import api, fields, models


class AbRequestType(models.Model):
    _name = "ab_request_type"
    _description = "Request Type"
    _order = "name"

    _uniq_code = models.Constraint(
        "UNIQUE(code)",
        "Request type code must be unique.",
    )

    name = fields.Char(required=True)
    code = fields.Char(required=True, copy=False, index=True)
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            if rec.code:
                rec.display_name = f"[{rec.code}] {rec.name}"
            else:
                rec.display_name = rec.name or "-"

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = [self._prepare_vals(vals) for vals in vals_list]
        return super().create(prepared_vals_list)

    def write(self, vals):
        return super().write(self._prepare_vals(vals))

    @api.model
    def _prepare_vals(self, vals):
        prepared_vals = dict(vals or {})
        if prepared_vals.get("code"):
            prepared_vals["code"] = prepared_vals["code"].strip().upper()
        if prepared_vals.get("name"):
            prepared_vals["name"] = prepared_vals["name"].strip()
        return prepared_vals
