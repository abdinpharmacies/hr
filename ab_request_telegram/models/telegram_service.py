import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from odoo import models

_logger = logging.getLogger(__name__)


class AbTelegramService(models.AbstractModel):
    _name = "ab.telegram.service"
    _description = "Telegram Service"

    def _get_bot_token(self):
        icp = self.env["ir.config_parameter"].sudo()
        return (
            (icp.get_param("telegram.bot.token") or "").strip()
            or (icp.get_param("telebot_api_key") or "").strip()
        )

    def _call_telegram_api(self, method, payload=None, query_params=None):
        token = self._get_bot_token()
        if not token:
            _logger.warning("ab_request_telegram: missing system parameter telegram.bot.token.")
            return False

        endpoint = f"https://api.telegram.org/bot{token}/{method}"
        if query_params:
            endpoint = f"{endpoint}?{urllib.parse.urlencode(query_params)}"
        request_obj = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Content-Type": "application/json"} if payload is not None else {},
            method="POST" if payload is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request_obj, timeout=10) as response:
                response_body = response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            _logger.error(
                "ab_request_telegram: Telegram API %s failed status=%s body=%s",
                method,
                exc.code,
                body,
            )
            return False
        except urllib.error.URLError as exc:
            _logger.error("ab_request_telegram: Telegram API %s connection failed: %s", method, exc)
            return False

        try:
            response_json = json.loads(response_body or "{}")
        except json.JSONDecodeError:
            _logger.error("ab_request_telegram: Telegram API %s returned invalid JSON: %s", method, response_body)
            return False

        if not response_json.get("ok"):
            _logger.error("ab_request_telegram: Telegram API %s rejected request payload=%s", method, response_json)
            return False
        return response_json

    def get_updates(self, offset=None, limit=100, timeout=0):
        query_params = {"limit": limit, "timeout": timeout}
        if offset is not None:
            query_params["offset"] = offset
        response_json = self._call_telegram_api("getUpdates", query_params=query_params)
        if not response_json:
            return []
        return response_json.get("result", [])

    def send_telegram_message(self, chat_id, message):
        if not chat_id or not message:
            return False

        response_json = self._call_telegram_api(
            "sendMessage",
            {
                "chat_id": str(chat_id).strip(),
                "text": message,
                "parse_mode": "HTML",
            }
        )
        return bool(response_json)
