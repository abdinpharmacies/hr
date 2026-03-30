import logging
import threading
from datetime import datetime, timezone

import telebot

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AbTelegramWebhookController(http.Controller):
    @staticmethod
    def _to_dt(ts_value):
        try:
            ts_int = int(ts_value)
        except Exception:
            return fields.Datetime.now()
        return datetime.fromtimestamp(ts_int, tz=timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _extract_content(message):
        media_keys = (
            "photo",
            "document",
            "video",
            "audio",
            "voice",
            "animation",
            "sticker",
            "contact",
            "location",
            "venue",
            "poll",
        )
        if message.get("text"):
            return "text", (message.get("text") or "").strip(), False, ""

        text = (message.get("caption") or "").strip()
        detected = [key for key in media_keys if key in message]
        has_media = bool(detected)
        content_type = detected[0] if detected else ("caption" if text else "unknown")
        return content_type, text, has_media, ",".join(detected)

    @staticmethod
    def _is_group_id_request(text):
        cleaned = (text or "").strip().lower()
        if not cleaned:
            return False

        normalized = cleaned.replace("_", " ").replace("-", " ")
        group_id_triggers = {
            "/id",
            "/groupid",
            "/group id",
            "/chatid",
            "/chat id",
            "id",
            "group id",
            "chat id",
            "message id",
            "msg id",
        }
        if normalized in group_id_triggers:
            return True

        if cleaned.startswith("/id@") or cleaned.startswith("/groupid@") or cleaned.startswith("/chatid@"):
            return True

        return cleaned.isdigit()

    @staticmethod
    def _is_user_id_request(text):
        cleaned = (text or "").strip().lower()
        normalized = " ".join(cleaned.replace("_", " ").replace("-", " ").split())
        if normalized in {"id", "/id", "user id", "userid", "my id", "get my id"}:
            return True
        return cleaned.startswith("/id@")

    @staticmethod
    def _is_private_menu_request(text):
        cleaned = (text or "").strip().lower()
        return cleaned in {"/start", "start", "/menu", "menu", "/help", "help"} or cleaned.startswith("/start@")

    @staticmethod
    def _private_menu_markup():
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        markup.row(
            telebot.types.KeyboardButton("Get My ID"),
            telebot.types.KeyboardButton("Help"),
        )
        return markup

    @staticmethod
    def _keyboard_markup_from_rows(keyboard_rows):
        if not keyboard_rows:
            return None
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        for row in keyboard_rows:
            buttons = [telebot.types.KeyboardButton(str(label)) for label in (row or []) if label]
            if buttons:
                markup.row(*buttons)
        return markup

    @http.route(
        "/ab_telegram_webhook/webhook",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def webhook_ping(self, **kwargs):
        return request.make_response(
            "ok",
            headers=[("Content-Type", "text/plain; charset=utf-8")],
        )

    @http.route(
        "/ab_telegram_webhook/webhook",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def webhook_receive(self, **kwargs):
        payload = request.httprequest.get_json(silent=True) or {}
        message = payload.get("message") or {}
        if not message:
            return request.make_json_response({"ok": True, "echoed": False, "reason": "not_new_message"})

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        chat_type = chat.get("type") or "unknown"

        sender = message.get("from") or {}
        if sender.get("is_bot"):
            return request.make_json_response({"ok": True, "echoed": False, "reason": "bot_sender"})

        icp = request.env["ir.config_parameter"].sudo()
        token = (icp.get_param("telebot_api_key") or "").strip()
        if not token:
            _logger.warning("ab_telegram_webhook: system parameter telebot_api_key is missing.")
            return request.make_json_response({"ok": False, "echoed": False, "reason": "missing_token"})

        try:
            echo_start_ts = int((icp.get_param("ab_telegram_webhook.echo_start_ts") or "0").strip())
        except Exception:
            echo_start_ts = 0

        message_ts = int(message.get("date") or 0)
        if message_ts and message_ts < echo_start_ts:
            return request.make_json_response({"ok": True, "echoed": False, "reason": "old_message"})

        text = ((message.get("text") or message.get("caption")) or "").strip()
        if not chat_id:
            return request.make_json_response({"ok": True, "echoed": False, "reason": "invalid_chat"})

        if not text:
            return request.make_json_response({"ok": True, "echoed": False, "reason": "empty_text"})

        sender_phone = ((message.get("contact") or {}).get("phone_number") or "").strip()

        try:
            bot = telebot.TeleBot(token)
            outbound_markup = None
            if chat_type in {"group", "supergroup"}:
                if not self._is_group_id_request(text):
                    return request.make_json_response({"ok": True, "echoed": False, "reason": "not_group_id_request"})
                outbound_text = f"Group ID: {chat_id}"
            elif chat_type == "private":
                typing_stop = threading.Event()

                def _typing_pulse():
                    while not typing_stop.is_set():
                        try:
                            bot.send_chat_action(chat_id, "typing")
                        except Exception:
                            _logger.debug("ab_telegram_webhook: failed to send chat action.", exc_info=True)
                        typing_stop.wait(4)

                typing_thread = threading.Thread(
                    target=_typing_pulse,
                    name=f"ab_tg_typing_{chat_id}",
                    daemon=True,
                )
                typing_thread.start()
                try:
                    extra_payload = {}
                    if "ab_user_telegram_link" in request.env:
                        extra_payload = request.env["ab_user_telegram_link"].sudo().bot_process_message(
                            telegram_user_id=str(sender.get("id") or ""),
                            telegram_chat_id=str(chat_id),
                            text=text,
                            username=(sender.get("username") or "").strip(),
                            first_name=(sender.get("first_name") or "").strip(),
                            last_name=(sender.get("last_name") or "").strip(),
                            phone=sender_phone,
                            language_code=(sender.get("language_code") or "").strip(),
                        )
                finally:
                    typing_stop.set()
                    if typing_thread.is_alive():
                        typing_thread.join(timeout=1)

                if extra_payload.get("handled"):
                    outbound_text = (extra_payload.get("text") or "").strip() or "Done."
                    outbound_markup = self._keyboard_markup_from_rows(extra_payload.get("keyboard_rows"))
                elif self._is_user_id_request(text):
                    outbound_text = f"Your Telegram user ID is: {sender.get('id') or chat_id}"
                    outbound_markup = self._private_menu_markup()
                elif self._is_private_menu_request(text):
                    outbound_text = (
                        "Telegram ID Menu\n"
                        "- Tap \"Get My ID\" to receive your user ID.\n"
                        "- You can also send: id"
                    )
                    outbound_markup = self._private_menu_markup()
                else:
                    outbound_text = (
                        "I can help you get your Telegram user ID.\n"
                        "Tap \"Get My ID\" or send: id"
                    )
                    outbound_markup = self._private_menu_markup()
            else:
                return request.make_json_response({"ok": True, "echoed": False, "reason": "chat_not_supported"})

            if outbound_markup:
                bot.send_message(chat_id, outbound_text, reply_markup=outbound_markup)
            else:
                bot.send_message(chat_id, outbound_text)
        except Exception:
            _logger.exception("ab_telegram_webhook: failed to send response message.")
            return request.make_json_response({"ok": False, "echoed": False, "reason": "send_failed"})

        return request.make_json_response({"ok": True, "echoed": True})
