from odoo import api, models


class AbSupplierClaimHrTelegramBot(models.Model):
    _inherit = "ab_hr_bot"

    @api.model
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
        chat_type="private",
    ):
        return self.env["ab_supplier_claim_telegram_registration"].sudo()._link_employee_from_telegram_message({
            "telegram_user_id": telegram_user_id,
            "telegram_chat_id": telegram_chat_id,
            "text": text,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "language_code": language_code,
            "chat_type": chat_type,
        }) or {"handled": False}
