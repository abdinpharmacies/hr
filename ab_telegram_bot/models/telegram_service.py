import json
import logging
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request

from odoo import api, models

_logger = logging.getLogger(__name__)


class AbTelegramBot(models.AbstractModel):
    _name = "ab_telegram_bot"
    _description = "Generic Telegram Sending Service"

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
            _logger.warning("ab_telegram_bot: missing system parameter telegram.bot.token.")
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
            _logger.error("ab_telegram_bot: Telegram API %s failed status=%s body=%s", method, exc.code, body)
            return False
        except urllib.error.URLError as exc:
            _logger.error("ab_telegram_bot: Telegram API %s connection failed: %s", method, exc)
            return False

        try:
            response_json = json.loads(response_body or "{}")
        except json.JSONDecodeError:
            _logger.error("ab_telegram_bot: Telegram API %s returned invalid JSON: %s", method, response_body)
            return False

        if not response_json.get("ok"):
            _logger.error("ab_telegram_bot: Telegram API %s rejected request payload=%s", method, response_json)
            return False
        return response_json

    @api.model
    def _call_telegram_multipart(self, method, fields=None, files=None):
        token = self._get_bot_token()
        if not token:
            _logger.warning("ab_telegram_bot: missing system parameter telegram.bot.token.")
            return False

        boundary = "----OdooTelegramBoundary%s" % int(time.time() * 1000)
        body = []
        for name, value in (fields or {}).items():
            if value is None or value is False:
                continue
            body.extend(
                [
                    ("--%s" % boundary).encode("utf-8"),
                    ('Content-Disposition: form-data; name="%s"' % name).encode("utf-8"),
                    b"",
                    str(value).encode("utf-8"),
                ]
            )
        for name, filename, content, content_type in files or []:
            if not content:
                continue
            if isinstance(content, str):
                content = content.encode("utf-8")
            body.extend(
                [
                    ("--%s" % boundary).encode("utf-8"),
                    ('Content-Disposition: form-data; name="%s"; filename="%s"' % (name, filename)).encode("utf-8"),
                    ("Content-Type: %s" % (content_type or "application/octet-stream")).encode("utf-8"),
                    b"",
                    content,
                ]
            )
        body.append(("--%s--" % boundary).encode("utf-8"))
        body.append(b"")

        request_obj = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/{method}",
            data=b"\r\n".join(body),
            headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request_obj, timeout=30) as response:
                response_body = response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            _logger.error("ab_telegram_bot: Telegram API %s failed status=%s body=%s", method, exc.code, body)
            return False
        except urllib.error.URLError as exc:
            _logger.error("ab_telegram_bot: Telegram API %s connection failed: %s", method, exc)
            return False

        try:
            response_json = json.loads(response_body or "{}")
        except json.JSONDecodeError:
            _logger.error("ab_telegram_bot: Telegram API %s returned invalid JSON: %s", method, response_body)
            return False
        if not response_json.get("ok"):
            _logger.error("ab_telegram_bot: Telegram API %s rejected request payload=%s", method, response_json)
            return False
        return response_json

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
        chat_id = str(chat_id or "").strip()
        if not chat_id or not text:
            return {"sent": False, "reason": "missing_chat_or_text", "chat_id": chat_id}

        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if disable_web_page_preview is not None:
            payload["disable_web_page_preview"] = bool(disable_web_page_preview)
        if reply_markup:
            payload["reply_markup"] = reply_markup
        elif keyboard_rows:
            payload["reply_markup"] = self.build_reply_keyboard(keyboard_rows)

        response = self._call_telegram_api("sendMessage", payload=payload)
        return {
            "sent": bool(response),
            "reason": "sent" if response else "api_error",
            "chat_id": chat_id,
            "message_id": self._extract_telegram_message_id(response),
        }

    @api.model
    def send_document(self, chat_id, filename, content, caption=False, parse_mode="HTML"):
        chat_id = str(chat_id or "").strip()
        if not chat_id or not filename or not content:
            return {"sent": False, "reason": "missing_chat_or_document", "chat_id": chat_id}

        fields_payload = {"chat_id": chat_id}
        if caption:
            fields_payload["caption"] = caption
        if parse_mode:
            fields_payload["parse_mode"] = parse_mode

        response = self._call_telegram_multipart(
            "sendDocument",
            fields=fields_payload,
            files=[
                (
                    "document",
                    filename,
                    content,
                    mimetypes.guess_type(filename)[0] or "application/octet-stream",
                )
            ],
        )
        return {
            "sent": bool(response),
            "reason": "sent" if response else "api_error",
            "chat_id": chat_id,
            "message_id": self._extract_telegram_message_id(response),
        }

    @api.model
    def send_payroll_message(self, chat_id, message):
        return self._result_as_message(self.send_message(chat_id, message or ""))

    @api.model
    def send_payroll_document(self, chat_id, filename, content):
        return self._result_as_message(self.send_document(chat_id, filename, content))

    @api.model
    def send_to_record(self, recipient, text, **kwargs):
        chat_id = self._get_recipient_chat_id(recipient)
        if not chat_id:
            return self._missing_recipient_result(recipient)
        result = self.send_message(chat_id, text, **kwargs)
        result.update(self._recipient_metadata(recipient))
        return result

    @api.model
    def send_document_to_record(self, recipient, filename, content, caption=False, **kwargs):
        chat_id = self._get_recipient_chat_id(recipient)
        if not chat_id:
            return self._missing_recipient_result(recipient)
        result = self.send_document(chat_id, filename, content, caption=caption, **kwargs)
        result.update(self._recipient_metadata(recipient))
        return result

    @api.model
    def _get_recipient_chat_id(self, recipient):
        if not recipient:
            return False
        recipient = recipient.sudo().exists()
        if not recipient:
            return False
        if recipient._name == "ab_hr_bot":
            return str(recipient.chat_id or "").strip() or False
        link = self.env["ab_hr_bot"].sudo().get_chat_id_for_employee(recipient)
        if link:
            return link
        return False

    @api.model
    def _recipient_metadata(self, recipient):
        recipient = recipient.sudo().exists() if recipient else recipient
        if not recipient:
            return {"recipient_model": False, "recipient_id": False}
        return {"recipient_model": recipient._name, "recipient_id": recipient.id}

    @api.model
    def _missing_recipient_result(self, recipient):
        result = {"sent": False, "reason": "missing_chat_id", "chat_id": False}
        result.update(self._recipient_metadata(recipient))
        return result

    @api.model
    def _extract_telegram_message_id(self, response):
        if isinstance(response, dict):
            result = response.get("result") or {}
            message_id = result.get("message_id")
            return str(message_id) if message_id else False
        return False

    @api.model
    def _result_as_message(self, result):
        class TelegramMessageResult:
            def __init__(self, message_id):
                self.message_id = message_id

        if not result.get("sent"):
            return False
        return TelegramMessageResult(result.get("message_id") or "sent")
