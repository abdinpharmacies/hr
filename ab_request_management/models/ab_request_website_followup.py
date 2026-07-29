from odoo import api, fields, models


class AbRequestWebsiteFollowup(models.Model):
    _name = "ab_request_website_followup"
    _description = "External Request Follow-up"
    _order = "create_date desc, id desc"

    request_id = fields.Many2one(
        "ab_request_website",
        string="External Request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    note = fields.Text(required=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "ab_request_website_followup_attachment_rel",
        "followup_id",
        "attachment_id",
        string="Attachments",
    )
    visible_to_user = fields.Boolean(string="Visible to User")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_attachments_to_followup()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "attachment_ids" in vals:
            self._sync_attachments_to_followup()
        return result

    def _sync_attachments_to_followup(self):
        for record in self:
            attachments = record.attachment_ids.sudo().filtered(
                lambda attachment: not attachment.res_model
                or (
                    attachment.res_model == record._name
                    and attachment.res_id in (False, 0, record.id)
                )
            )
            if attachments:
                attachments.write(
                    {
                        "res_model": record._name,
                        "res_id": record.id,
                    }
                )
