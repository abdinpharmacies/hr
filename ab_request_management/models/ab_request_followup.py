from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AbRequestFollowup(models.Model):
    _name = "ab.request.followup"
    _description = "Request Follow-up"
    _order = "date desc, id desc"

    request_id = fields.Many2one(
        "ab.request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        ondelete="restrict",
    )
    description = fields.Text(required=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Create follow-ups with request-level permission checks."""
        requests = self.env["ab.request"].browse([vals["request_id"] for vals in vals_list if vals.get("request_id")])
        requests._check_followup_creation_rights()
        prepared_vals_list = [self._prepare_vals(vals) for vals in vals_list]
        records = super().create(prepared_vals_list)
        for record in records:
            record.request_id.message_post(
                body=record.description,
                subtype_xmlid="mail.mt_note",
            )
        return records

    def write(self, vals):
        """Prevent edits to follow-ups after creation."""
        raise ValidationError(_("Follow-ups cannot be edited once created."))

    def unlink(self):
        """Prevent follow-up deletion to keep the timeline auditable."""
        raise ValidationError(_("Follow-ups cannot be deleted."))

    @api.model
    def _prepare_vals(self, vals):
        """Normalize follow-up values."""
        prepared_vals = dict(vals or {})
        prepared_vals["description"] = (prepared_vals.get("description") or "").strip()
        if not prepared_vals["description"]:
            raise ValidationError(_("Follow-up description is required."))
        prepared_vals.setdefault("user_id", self.env.user.id)
        prepared_vals.setdefault("date", fields.Datetime.now())
        return prepared_vals
