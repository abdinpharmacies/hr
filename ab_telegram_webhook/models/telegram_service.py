import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from odoo import api, models

_logger = logging.getLogger(__name__)


class AbTelegramService(models.AbstractModel):
    _name = "ab_telegram_service"
    _description = "Telegram Service"

    @api.model
    def _get_bot_token(self):
        icp = self.env["ir.config_parameter"].sudo()
        return (
            (icp.get_param("telegram.bot.token") or "").strip()
            or (icp.get_param("telebot_api_key") or "").strip()
        )

    @api.model
    def _call_telegram_api(self, method, payload=None, query_params=None):
        token = self._get_bot_token()
        if not token:
            _logger.warning("ab_telegram_webhook: missing system parameter telegram.bot.token.")
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
                "ab_telegram_webhook: Telegram API %s failed status=%s body=%s",
                method,
                exc.code,
                body,
            )
            return False
        except urllib.error.URLError as exc:
            _logger.error("ab_telegram_webhook: Telegram API %s connection failed: %s", method, exc)
            return False

        try:
            response_json = json.loads(response_body or "{}")
        except json.JSONDecodeError:
            _logger.error("ab_telegram_webhook: Telegram API %s returned invalid JSON: %s", method, response_body)
            return False

        if not response_json.get("ok"):
            _logger.error("ab_telegram_webhook: Telegram API %s rejected request payload=%s", method, response_json)
            return False
        return response_json

    @api.model
    def get_updates(self, offset=None, limit=100, timeout=0):
        query_params = {"limit": limit, "timeout": timeout}
        if offset is not None:
            query_params["offset"] = offset
        response_json = self._call_telegram_api("getUpdates", query_params=query_params)
        if not response_json:
            return []
        return response_json.get("result", [])

    @api.model
    def build_reply_keyboard(self, keyboard_rows, resize_keyboard=True, one_time_keyboard=False):
        rows = []
        for row in keyboard_rows or []:
            buttons = [{"text": str(label)} for label in (row or []) if label]
            if buttons:
                rows.append(buttons)
        if not rows:
            return False
        return {
            "keyboard": rows,
            "resize_keyboard": bool(resize_keyboard),
            "one_time_keyboard": bool(one_time_keyboard),
        }

    @api.model
    def send_message(
        self,
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=None,
        keyboard_rows=None,
        disable_web_page_preview=None,
    ):
        if not chat_id or not text:
            return False

        payload = {
            "chat_id": str(chat_id).strip(),
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if disable_web_page_preview is not None:
            payload["disable_web_page_preview"] = bool(disable_web_page_preview)
        if reply_markup:
            payload["reply_markup"] = reply_markup
        elif keyboard_rows:
            payload["reply_markup"] = self.build_reply_keyboard(keyboard_rows)

        return bool(self._call_telegram_api("sendMessage", payload=payload))

    @api.model
    def send_telegram_message(self, chat_id, message):
        return self.send_message(chat_id, message)

    @api.model
    def send_chat_action(self, chat_id, action="typing"):
        if not chat_id or not action:
            return False
        return bool(
            self._call_telegram_api(
                "sendChatAction",
                payload={
                    "chat_id": str(chat_id).strip(),
                    "action": action,
                },
            )
        )

    @api.model
    def remove_webhook(self, drop_pending_updates=True):
        return bool(
            self._call_telegram_api(
                "deleteWebhook",
                payload={"drop_pending_updates": bool(drop_pending_updates)},
            )
        )

    @api.model
    def get_default_webhook_url(self):
        icp = self.env["ir.config_parameter"].sudo()
        base_url = (icp.get_param("web.base.url") or "").strip().rstrip("/")
        if not base_url:
            base_url = "https://ctrl.abdinpharmacies.com"
        return f"{base_url}/ab_telegram_webhook/webhook?db={self.env.cr.dbname}"

    @api.model
    def set_webhook(self, webhook_url=False, drop_pending_updates=True):
        webhook_url = (webhook_url or self.get_default_webhook_url() or "").strip()
        if not webhook_url:
            _logger.warning("ab_telegram_webhook: cannot set webhook without a URL.")
            return False

        self.env["ir.config_parameter"].sudo().set_param(
            "ab_telegram_webhook.echo_start_ts",
            str(int(time.time())),
        )
        return bool(
            self._call_telegram_api(
                "setWebhook",
                payload={
                    "url": webhook_url,
                    "drop_pending_updates": bool(drop_pending_updates),
                },
            )
        )

    @api.model
    def dispatch_webhook_payload(self, payload):
        message = (payload or {}).get("message") or {}
        if not message:
            return {"ok": True, "echoed": False, "reason": "not_new_message"}

        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if sender.get("is_bot"):
            return {"ok": True, "echoed": False, "reason": "bot_sender"}
        if not self._get_bot_token():
            return {"ok": False, "echoed": False, "reason": "missing_token"}

        chat_id = chat.get("id")
        chat_type = chat.get("type") or "unknown"
        if not chat_id:
            return {"ok": True, "echoed": False, "reason": "invalid_chat"}

        if self._is_old_message(message):
            return {"ok": True, "echoed": False, "reason": "old_message"}

        text = ((message.get("text") or message.get("caption")) or "").strip()
        if not text:
            return {"ok": True, "echoed": False, "reason": "empty_text"}

        if chat_type in {"group", "supergroup"}:
            if not self._is_chat_id_request(text):
                return {"ok": True, "echoed": False, "reason": "not_group_id_request"}
            self.send_message(chat_id, f"Group ID: {chat_id}", parse_mode=False)
            return {"ok": True, "echoed": True, "reason": "chat_id_request"}

        if chat_type != "private":
            return {"ok": True, "echoed": False, "reason": "chat_not_supported"}

        self.send_chat_action(chat_id, "typing")
        message_data = self._prepare_message_data(message, chat_id, chat_type, text, sender)
        handler_payload = self._dispatch_telegram_message(message_data) or {}
        if handler_payload.get("handled"):
            self.send_message(
                chat_id,
                (handler_payload.get("text") or "").strip() or "Done.",
                keyboard_rows=handler_payload.get("keyboard_rows"),
            )
            return {"ok": True, "echoed": True, "reason": handler_payload.get("note") or "handler"}

        fallback = self._build_private_fallback(chat_id, text, sender)
        self.send_message(
            chat_id,
            fallback["text"],
            keyboard_rows=fallback.get("keyboard_rows"),
        )
        return {"ok": True, "echoed": True, "reason": fallback["reason"]}

    @api.model
    def _prepare_message_data(self, message, chat_id, chat_type, text, sender):
        return {
            "telegram_chat_id": str(chat_id),
            "chat_id": str(chat_id),
            "chat_type": chat_type,
            "text": text,
            "telegram_user_id": str(sender.get("id") or "").strip(),
            "username": (sender.get("username") or "").strip(),
            "first_name": (sender.get("first_name") or "").strip(),
            "last_name": (sender.get("last_name") or "").strip(),
            "phone": ((message.get("contact") or {}).get("phone_number") or "").strip(),
            "language_code": (sender.get("language_code") or "").strip(),
            "raw_message": message,
        }

    @api.model
    def _dispatch_telegram_message(self, message_data):
        if "ab_user_telegram_link" not in self.env:
            return {"handled": False}
        return self.env["ab_user_telegram_link"].sudo().bot_process_message(
            telegram_user_id=message_data.get("telegram_user_id"),
            telegram_chat_id=message_data.get("telegram_chat_id"),
            text=message_data.get("text"),
            username=message_data.get("username"),
            first_name=message_data.get("first_name"),
            last_name=message_data.get("last_name"),
            phone=message_data.get("phone"),
            language_code=message_data.get("language_code"),
        ) or {"handled": False}

    @api.model
    def _is_old_message(self, message):
        icp = self.env["ir.config_parameter"].sudo()
        try:
            echo_start_ts = int((icp.get_param("ab_telegram_webhook.echo_start_ts") or "0").strip())
        except Exception:
            echo_start_ts = 0
        try:
            message_ts = int(message.get("date") or 0)
        except Exception:
            message_ts = 0
        return bool(message_ts and message_ts < echo_start_ts)

    @api.model
    def _is_chat_id_request(self, text):
        cleaned = (text or "").strip().lower()
        normalized = " ".join(cleaned.replace("_", " ").replace("-", " ").split())
        return normalized in {
            "id",
            "/id",
            "user id",
            "userid",
            "my id",
            "get my id",
            "group id",
            "/group id",
            "groupid",
            "/groupid",
            "chat id",
            "/chat id",
            "chatid",
            "/chatid",
            "message id",
            "msg id",
        } or cleaned.startswith(("/id@", "/groupid@", "/chatid@"))

    @api.model
    def _is_private_menu_request(self, text):
        cleaned = (text or "").strip().lower()
        return cleaned in {"/start", "start", "/menu", "menu", "/help", "help"} or cleaned.startswith("/start@")

    @api.model
    def _build_private_fallback(self, chat_id, text, sender):
        keyboard_rows = [["Get My ID", "Help"]]
        if self._is_chat_id_request(text):
            return {
                "reason": "user_id_request",
                "text": f"Your Telegram user ID is: {sender.get('id') or chat_id}",
                "keyboard_rows": keyboard_rows,
            }
        if self._is_private_menu_request(text):
            return {
                "reason": "menu_request",
                "text": (
                    "Telegram ID Menu\n"
                    "- Tap \"Get My ID\" to receive your user ID.\n"
                    "- You can also send: id"
                ),
                "keyboard_rows": keyboard_rows,
            }
        return {
            "reason": "default_private_help",
            "text": (
                "I can help you get your Telegram user ID.\n"
                "Tap \"Get My ID\" or send: id"
            ),
            "keyboard_rows": keyboard_rows,
        }
