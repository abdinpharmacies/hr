from odoo import api, fields, models


class MailMessage(models.Model):
    _inherit = "mail.message"

    ab_is_followup_message = fields.Boolean(copy=False, default=False, index=True)

    @api.model
    def _message_fetch(
        self,
        domain,
        *,
        thread=None,
        search_term=None,
        is_notification=None,
        before=None,
        after=None,
        around=None,
        limit=30,
    ):
        res = super()._message_fetch(
            domain,
            thread=thread,
            search_term=search_term,
            is_notification=is_notification,
            before=before,
            after=after,
            around=around,
            limit=limit,
        )
        if thread and thread._name == "ab_request" and self._ab_should_filter_request_chatter():
            res["messages"] = res["messages"].filtered(self._ab_is_request_user_visible_message)
            if "count" in res:
                res["count"] = len(res["messages"])
        return res

    def _ab_should_filter_request_chatter(self):
        user = self.env.user
        return (
            user.has_group("ab_request_management.group_ab_request_management_user")
            and not user.has_group("ab_request_management.group_ab_request_management_manager")
            and not user.has_group("ab_request_management.group_ab_request_management_admin")
        )

    def _ab_is_request_user_visible_message(self, message):
        note_subtype = self.env.ref("mail.mt_note", raise_if_not_found=False)
        if message.message_type in {"notification", "auto_comment"}:
            return False
        if note_subtype and message.subtype_id == note_subtype and not message.ab_is_followup_message:
            return False
        if message.sudo().tracking_value_ids:
            return False
        return True
