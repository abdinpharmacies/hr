import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AbTelegramWebhookSetup(models.AbstractModel):
    _name = "ab.telegram.webhook.setup"
    _description = "AB Telegram Webhook Setup"

    @api.model
    def apply(self):
        icp = self.env["ir.config_parameter"].sudo()
        token = (
            (icp.get_param("telegram.bot.token") or "").strip()
            or (icp.get_param("telebot_api_key") or "").strip()
        )
        if not token:
            _logger.warning("ab_telegram_webhook: telegram.bot.token is missing, webhook was not set.")
            return False

        default_webhook_url = self.env["ab_telegram_service"].sudo().get_default_webhook_url()
        webhook_url = (icp.get_param("telebot_webhook_url") or default_webhook_url).strip()
        if self.env["ab_telegram_service"].sudo().set_webhook(webhook_url, drop_pending_updates=True):
            _logger.info(
                "ab_telegram_webhook: webhook set to %s",
                webhook_url,
            )
            return True

        _logger.warning("ab_telegram_webhook: failed to set telegram webhook.")
        return False
