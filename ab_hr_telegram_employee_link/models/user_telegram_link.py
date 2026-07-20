# -*- coding: utf-8 -*-
from odoo import fields, models


class AbUserTelegramLink(models.Model):
    _inherit = "ab_user_telegram_link"

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

    def bot_process_message(
        self,
        telegram_user_id,
        telegram_chat_id,
        text,
        username="",
        first_name="",
        last_name="",
        phone="",
        language_code="",
    ):
        self._log_employee_code_telegram_chat_message(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            text=text,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            language_code=language_code,
        )
        employee_payload = self.env["ab_hr_employee"].sudo().bot_process_employee_telegram_link(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            text=text,
            username=username,
        )
        if employee_payload.get("handled"):
            return employee_payload
        return super().bot_process_message(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            text=text,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            language_code=language_code,
        )


class AbHrBot(models.Model):
    _inherit = "ab_hr_bot"

    def bot_process_message(
        self,
        telegram_chat_id,
        text,
        username=False,
        chat_type="private",
        telegram_user_id=False,
        first_name=False,
        last_name=False,
        phone=False,
        language_code=False,
    ):
        self.env["ab_user_telegram_link"].sudo()._log_employee_code_telegram_chat_message(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            text=text,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            language_code=language_code,
        )
        employee_payload = self.env["ab_hr_employee"].sudo().bot_process_employee_telegram_link(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            text=text,
            username=username,
        )
        if employee_payload.get("handled"):
            return employee_payload
        return super().bot_process_message(
            telegram_chat_id=telegram_chat_id,
            text=text,
            username=username,
            chat_type=chat_type,
            telegram_user_id=telegram_user_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            language_code=language_code,
        )
