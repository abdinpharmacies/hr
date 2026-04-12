from odoo import api, fields, models


class AbRequestFollowupWizard(models.TransientModel):
    _name = "ab.request.followup.wizard"
    _description = "Request Follow-up Wizard"

    request_id = fields.Many2one(
        "ab.request",
        string="Request",
        required=True,
        default=lambda self: self._default_request_id(),
    )
    description = fields.Text(
        string="Follow-up Note",
        required=True,
        placeholder="Describe the requested changes or feedback...",
    )

    def _default_request_id(self):
        return self.env["ab.request"].browse(self._context.get("active_id"))

    def action_add_followup(self):
        self.ensure_one()
        request = self.request_id
        message = request.message_post(
            body=self.description,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        message.ab_is_followup_message = True
        request.with_context(allow_state_write=True).write({"state": "in_progress"})
        request._notify_requester_confirmation()
        return True
