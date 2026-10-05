import os
import json
from pathlib import Path
import urllib.error
import urllib.request

from markupsafe import Markup, escape

from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import config


def deployment_secret(name):
    filename = os.environ.get(name + "_FILE") or config.get(name.lower() + "_file")
    if filename:
        try:
            path = Path(filename)
            if path.stat().st_mode & 0o077:
                return ""
            return path.read_text().strip()
        except OSError:
            return ""
    return os.environ.get(name, "").strip()


class AuthChannel(models.AbstractModel):
    _name = "ab_storefront_auth_channel"
    _description = "Storefront Verification Channel"

    def _deliver(self, payload):
        raise NotImplementedError

    def _identity_kind(self):
        raise NotImplementedError

    def _recovery_purpose(self):
        return "otp"

    def _available_for(self, user):
        raise NotImplementedError

    def _can_recover(self, user):
        return self._available_for(user)

    def _prepare_recovery(self, service, challenge, token):
        raise NotImplementedError


class EmailChannel(models.AbstractModel):
    _name = "ab_storefront_auth_email"
    _inherit = "ab_storefront_auth_channel"
    _description = "Storefront Email Verification Channel"

    def _identity_kind(self):
        return "email"

    def _recovery_purpose(self):
        return "email_reset"

    def _available_for(self, user):
        return bool(self.env["ab_storefront_auth_service"]._identities(user).filtered(lambda identity: identity.kind == "email"))

    def _can_recover(self, user):
        return bool(user)

    def _prepare_recovery(self, service, challenge, token):
        service._queue(challenge.channel, {"user_id": challenge.user_id.id, "destination": challenge.value, "purpose": "email_reset", "url": service._base_url() + "/ab_storefront/auth/recover#" + token}, challenge)

    def _deliver(self, payload):
        user = self.env["res.users"].sudo().browse(payload["user_id"]).exists()
        if not user or not user.active:
            return
        translated = self.with_context(lang=user.lang or "en_US").env
        subject = translated._("Verify email") if payload["purpose"] == "email_verify" else translated._("Password reset")
        body = Markup("<p>%s</p><p><a href=\"%s\">%s</a></p><p>%s</p>") % (
            escape(translated._("Follow this link to continue. It expires shortly and can only be used once.")),
            escape(payload["url"]), escape(subject),
            escape(translated._("If you did not request this, ignore this message.")),
        )
        self.env["mail.mail"].sudo().create({
            "subject": subject, "body_html": body, "email_to": payload["destination"],
            "email_from": user.company_id.email_formatted or False,
            "auto_delete": True,
        })


class TelegramChannel(models.AbstractModel):
    _name = "ab_storefront_auth_telegram"
    _inherit = "ab_storefront_auth_channel"
    _description = "Storefront Telegram Verification Channel"

    def _identity_kind(self):
        return "phone"

    def _available_for(self, user):
        kinds = self.env["ab_storefront_auth_service"]._identities(user).mapped("kind")
        return self._enabled() and {"phone", "telegram"}.issubset(set(kinds))

    def _prepare_recovery(self, service, challenge, token):
        code = service._generate_otp(challenge, token)
        user = challenge.user_id
        telegram = service._identities(user).filtered(lambda identity: identity.kind == "telegram")
        text = self.with_context(lang=user.lang or "ar_001").env._("Your Abdin Pharmacy security code is: %s. Do not share it. It expires shortly.", code)
        service._queue(challenge.channel, {"chat_id": telegram.chat_id, "text": text, "protect_content": True}, challenge)

    def _enabled(self):
        return self.env["ir.config_parameter"].sudo().get_param("ab_storefront_auth.telegram_enabled", "False") == "True" and bool(deployment_secret("AB_STOREFRONT_TELEGRAM_TOKEN"))

    def _api(self, method, payload):
        if method not in {"sendMessage", "setWebhook", "deleteWebhook", "getUpdates", "getMe", "getWebhookInfo", "setMyCommands"}:
            raise UserError(_("Unsupported Telegram operation."))
        token = deployment_secret("AB_STOREFRONT_TELEGRAM_TOKEN")
        if not token:
            raise UserError(_("Telegram delivery is unavailable."))
        try:
            api_request = urllib.request.Request("https://api.telegram.org/bot" + token + "/" + method, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(api_request, timeout=5) as response:
                result = json.loads(response.read(1048576))
            if not result.get("ok"):
                raise ValueError
            return result.get("result")
        except (urllib.error.URLError, ValueError, TimeoutError, OSError):
            raise UserError(_("Telegram delivery is unavailable.")) from None

    def _deliver(self, payload):
        if not self._enabled():
            raise UserError(_("Telegram delivery is unavailable."))
        self._api("sendMessage", payload)

    def _configure_webhook(self):
        params = self.env["ir.config_parameter"].sudo()
        url = params.get_param("ab_storefront_auth.telegram_webhook_url", "")
        secret = deployment_secret("AB_STOREFRONT_TELEGRAM_WEBHOOK_SECRET")
        if not url.startswith("https://") or not secret:
            raise UserError(_("Configure an HTTPS webhook and a webhook secret first."))
        username = params.get_param("ab_storefront_auth.telegram_bot_username", "Abdin_Pharmacy_Bot").lstrip("@")
        if self._api("getMe", {}).get("username", "").lower() != username.lower():
            raise UserError(_("The configured Telegram bot username does not match the token."))
        self._api("setWebhook", {"url": url, "secret_token": secret, "allowed_updates": ["message"], "max_connections": 10, "drop_pending_updates": False})
        for language_code, language in [("", "en_US"), ("ar", "ar_001")]:
            translated = self.with_context(lang=language).env
            commands = [{"command": "start", "description": translated._("Account verification")}, {"command": "help", "description": translated._("Help")}, {"command": "cancel", "description": translated._("Cancel verification")}]
            self._api("setMyCommands", {"commands": commands, "language_code": language_code})
        return True

    def _poll_once(self):
        params = self.env["ir.config_parameter"].sudo()
        if params.get_param("ab_storefront_auth.development", "False") != "True" or not self._enabled():
            raise UserError(_("Polling is available only in development mode."))
        self.env["ab_storefront_auth_service"].sudo()._lock("telegram-development-poll")
        if self._api("getWebhookInfo", {}).get("url"):
            raise UserError(_("Remove the webhook before using development polling."))
        offset = int(params.get_param("ab_storefront_auth.telegram_poll_offset", "0"))
        updates = self._api("getUpdates", {"offset": offset, "timeout": 0, "limit": 10, "allowed_updates": ["message"]})
        for update in updates:
            self.env["ab_storefront_auth_service"].sudo()._ingest_update(update)
            offset = max(offset, update["update_id"] + 1)
        params.set_param("ab_storefront_auth.telegram_poll_offset", offset)
        return len(updates)
