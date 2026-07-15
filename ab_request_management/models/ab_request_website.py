from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

from .ab_request_ticket import REQUEST_SEQUENCE_CODE


class AbRequestWebsite(models.Model):
    _name = "ab_request_website"
    _description = "Website Request or Complaint"
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        default="New",
    )
    customer_name = fields.Char(required=True)
    customer_phone = fields.Char(required=True)
    customer_email = fields.Char()
    request_category_id = fields.Many2one("ab_request_category", string="Category", ondelete="set null")
    request_type_id = fields.Many2one("ab_request_type", string="Request/Complaint Type", required=True, ondelete="restrict")
    subject = fields.Char(required=True)
    description = fields.Text(required=True)
    source = fields.Selection(
        [
            ("website", "Website"),
            ("embed", "Embedded Website Form"),
        ],
        default="embed",
        required=True,
    )
    state = fields.Selection(
        [
            ("new", "New"),
            ("reviewed", "Reviewed"),
            ("converted", "Converted"),
            ("closed", "Closed"),
        ],
        default="new",
        required=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = [self._prepare_create_vals(vals) for vals in vals_list]
        return super().create(prepared_vals_list)

    @api.model
    def _prepare_create_vals(self, vals):
        prepared_vals = dict(vals or {})
        for field_name in ("customer_name", "customer_phone", "customer_email", "subject", "description"):
            if prepared_vals.get(field_name):
                prepared_vals[field_name] = prepared_vals[field_name].strip()
        if not prepared_vals.get("customer_name"):
            raise ValidationError(_("Customer name is required."))
        if not prepared_vals.get("customer_phone"):
            raise ValidationError(_("Customer phone is required."))
        if not prepared_vals.get("request_type_id"):
            raise ValidationError(_("Request/complaint type is required."))
        if not prepared_vals.get("subject"):
            raise ValidationError(_("Subject is required."))
        if not prepared_vals.get("description"):
            raise ValidationError(_("Details are required."))
        if not prepared_vals.get("name") or prepared_vals.get("name") == "New":
            prepared_vals["name"] = self.env["ir.sequence"].sudo().next_by_code(REQUEST_SEQUENCE_CODE) or "New"
        if not prepared_vals.get("request_category_id"):
            request_type = self.env["ab_request_type"].sudo().browse(prepared_vals["request_type_id"])
            prepared_vals["request_category_id"] = request_type.category_id.id or False
        return prepared_vals
