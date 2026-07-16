from odoo import api, models


class AbTelegramService(models.AbstractModel):
    _inherit = "ab_telegram_service"

    @api.model
    def _dispatch_telegram_message(self, message_data):
        result = super()._dispatch_telegram_message(message_data)
        if result.get("handled") or message_data.get("chat_type") != "private":
            return result

        return self.env["ab_hr_bot"].sudo().bot_process_message(
            telegram_user_id=message_data.get("telegram_user_id"),
            telegram_chat_id=message_data.get("telegram_chat_id"),
            text=message_data.get("text"),
            username=message_data.get("username"),
            first_name=message_data.get("first_name"),
            last_name=message_data.get("last_name"),
            phone=message_data.get("phone"),
            language_code=message_data.get("language_code"),
            chat_type=message_data.get("chat_type"),
        ) or result
