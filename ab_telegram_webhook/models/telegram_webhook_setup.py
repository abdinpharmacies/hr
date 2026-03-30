import logging
import time

import telebot

from odoo import api, models

_logger = logging.getLogger(__name__)


class AbTelegramWebhookSetup(models.AbstractModel):
    _name = "ab.telegram.webhook.setup"
    _description = "AB Telegram Webhook Setup"

    @api.model
    def apply(self):
        icp = self.env["ir.config_parameter"].sudo()
        token = (icp.get_param("telebot_api_key") or "").strip()
        if not token:
            _logger.warning("ab_telegram_webhook: telebot_api_key is missing, webhook was not set.")
            return False
        echo_start_ts = int(time.time())
        icp.set_param("ab_telegram_webhook.echo_start_ts", str(echo_start_ts))

        base_url = (icp.get_param("web.base.url") or "").strip().rstrip("/")
        if not base_url:
            base_url = "https://ctrl.abdinpharmacies.com"
        default_webhook_url = f"{base_url}/ab_telegram_webhook/webhook?db={self.env.cr.dbname}"
        webhook_url = (icp.get_param("telebot_webhook_url") or default_webhook_url).strip()

        try:
            bot = telebot.TeleBot(token)
            bot.remove_webhook()
            try:
                bot.set_webhook(url=webhook_url, drop_pending_updates=True)
            except TypeError:
                bot.set_webhook(url=webhook_url)
            _logger.info(
                "ab_telegram_webhook: webhook set to %s (echo_start_ts=%s)",
                webhook_url,
                echo_start_ts,
            )
        except Exception:
            _logger.exception("ab_telegram_webhook: failed to set telegram webhook.")
            return False

        return True
