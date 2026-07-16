from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbPayrollTelegramService(models.AbstractModel):
    _inherit = "ab_telegram_service"

    @api.model
    def _payroll_bot_client(self):
        from telebot import TeleBot

        token = self._get_bot_token()
        if not token:
            raise UserError(
                _("Telegram bot token is missing. Configure system parameter telegram.bot.token.")
            )
        return TeleBot(token)

    @api.model
    def send_payroll_message(self, chat_id, message):
        return self._payroll_bot_client().send_message(chat_id, message or "")

    @api.model
    def send_payroll_document(self, chat_id, filename, content):
        return self._payroll_bot_client().send_document(chat_id, (filename, content))
