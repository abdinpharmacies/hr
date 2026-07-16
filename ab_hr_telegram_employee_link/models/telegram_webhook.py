# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AbTelegramService(models.AbstractModel):
    _inherit = "ab_telegram_service"

    def _log_employee_code_telegram_chat_message(
        self,
        telegram_user_id,
        telegram_chat_id,
        text,
        username=False,
        first_name=False,
        last_name=False,
        phone=False,
        language_code=False,
    ):
        if "ab_telegram_chat_message" not in self.env:
            return
        code = self.env["ab_hr_employee"].sudo()._extract_telegram_employee_code(text)
        if not code:
            return
        self.env["ab_telegram_chat_message"].sudo().create(
            {
                "telegram_chat_id": str(telegram_chat_id or "").strip() or "-",
                "telegram_user_id": str(telegram_user_id or "").strip() or str(telegram_chat_id or "").strip() or "-",
                "username": (username or "").strip() or False,
                "first_name": (first_name or "").strip() or False,
                "last_name": (last_name or "").strip() or False,
                "phone": (phone or "").strip() or False,
                "language_code": (language_code or "").strip() or False,
                "chat_type": "private",
                "content_type": "text",
                "content_text": (text or "").strip(),
                "message_datetime": fields.Datetime.now(),
                "processing_note": "employee_code_link",
            }
        )

    @api.model
    def _dispatch_telegram_message(self, message_data):
        if message_data.get("chat_type") != "private":
            return super()._dispatch_telegram_message(message_data)

        self._log_employee_code_telegram_chat_message(
            telegram_user_id=message_data.get("telegram_user_id"),
            telegram_chat_id=message_data.get("telegram_chat_id"),
            text=message_data.get("text"),
            username=message_data.get("username"),
            first_name=message_data.get("first_name"),
            last_name=message_data.get("last_name"),
            phone=message_data.get("phone"),
            language_code=message_data.get("language_code"),
        )
        employee_payload = self.env["ab_hr_employee"].sudo().bot_process_employee_telegram_link(
            telegram_user_id=message_data.get("telegram_user_id"),
            telegram_chat_id=message_data.get("telegram_chat_id"),
            text=message_data.get("text"),
            username=message_data.get("username"),
        )
        if employee_payload.get("handled"):
            return employee_payload
        return super()._dispatch_telegram_message(message_data)
