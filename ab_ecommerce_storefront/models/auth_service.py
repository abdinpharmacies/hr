import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import math
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from .auth_identity import normalize_identity


_logger = logging.getLogger(__name__)


class AuthRateLimitError(UserError):
    """Rate-limit response carrying only the safe client retry delay."""

    def __init__(self, retry_after):
        self.retry_after = max(1, int(retry_after))
        super().__init__(_("Please wait before trying again."))


class AuthService(models.AbstractModel):
    _name = "ab_storefront_auth_service"
    _description = "Storefront Authentication Service"

    def _setting(self, name, default, minimum=1, maximum=86400):
        try:
            return max(minimum, min(maximum, int(self.env["ir.config_parameter"].sudo().get_param("ab_storefront_auth." + name, default))))
        except (ValueError, TypeError):
            return default

    def _digest(self, value):
        key = self.env["ir.config_parameter"].sudo().get_param("database.secret")
        if not key:
            raise UserError(_("Authentication is temporarily unavailable."))
        return hmac.new(key.encode(), ("storefront-auth:" + value).encode(), hashlib.sha256).hexdigest()

    def _cipher(self):
        return Fernet(base64.urlsafe_b64encode(bytes.fromhex(self._digest("delivery-encryption"))))

    def _lock(self, key):
        number = int(self._digest("lock:" + key)[:15], 16)
        self.env.cr.execute("SELECT pg_advisory_xact_lock(%s)", (number,))

    def _rate_allow_with_retry(self, action, subject, limit=None, window=3600):
        key = self._digest("rate:" + action + ":" + subject)
        self._lock(key)
        Rate = self.env["ab_storefront_auth_rate"].sudo()
        bucket = Rate.search([("key", "=", key)], limit=1)
        now = fields.Datetime.now()
        if not bucket:
            bucket = Rate.create({"key": key, "expires_at": now + timedelta(seconds=window)})
        elif bucket.expires_at <= now:
            bucket.write({"count": 0, "expires_at": now + timedelta(seconds=window)})
        bucket.write({"count": bucket.count + 1})
        allowed = bucket.count <= (limit or self._setting("rate_limit", 5, maximum=100))
        retry_after = max(0, math.ceil((bucket.expires_at - now).total_seconds())) if not allowed else 0
        return allowed, retry_after

    def _rate_allow(self, action, subject, limit=None, window=3600):
        return self._rate_allow_with_retry(action, subject, limit, window)[0]

    def _channel_registry(self):
        return {"email": "ab_storefront_auth_email", "telegram": "ab_storefront_auth_telegram"}

    def _channel(self, name):
        model = self._channel_registry().get(name)
        if not model:
            raise ValidationError(_("Invalid recovery channel."))
        return self.env[model].sudo()

    def _base_url(self):
        url = self.env["ir.config_parameter"].sudo().get_param("ab_storefront_auth.base_url", "")
        parsed = urlparse(url)
        if not parsed.hostname or any(char.isspace() for char in parsed.netloc) or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise UserError(_("Configure the public authentication URL first."))
        if parsed.scheme != "https" and not (parsed.scheme == "http" and self._development_http_allowed(parsed.hostname)):
            raise UserError(_("Configure the public authentication URL first."))
        return url.rstrip("/")

    def _development_http_allowed(self, hostname):
        if self.env["ir.config_parameter"].sudo().get_param("ab_storefront_auth.development", "False") != "True":
            return False
        if (hostname or "").lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            return False

    def _new_challenge(self, purpose, user=None, browser=None, value=None, channel=None, ttl=None):
        token = secrets.token_urlsafe(32)
        challenge = self.env["ab_storefront_auth_challenge"].sudo().create({
            "purpose": purpose, "user_id": user.id if user else False,
            "website_id": self._auth_website().id,
            "token_hash": self._digest("token:" + token),
            "browser_hash": self._digest("browser:" + browser) if browser else False,
            "credential_stamp": self._credential_stamp(user) if user else False,
            "value": value, "channel": channel,
            "expires_at": fields.Datetime.now() + timedelta(seconds=ttl or self._setting("token_expiration", 900, maximum=3600)),
        })
        return challenge, token

    def _credential_stamp(self, user):
        return user._session_token_hash_compute("ab-storefront-recovery", user._session_token_get_values())

    def _find(self, token, purposes, browser=None):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            return self.env["ab_storefront_auth_challenge"].sudo().browse()
        digest = self._digest("token:" + token)
        self._lock("challenge:" + digest)
        challenge = self.env["ab_storefront_auth_challenge"].sudo().search([("token_hash", "=", digest), ("purpose", "in", purposes)], limit=1)
        challenge.invalidate_recordset()
        if not challenge or challenge.used_at or challenge.expires_at <= fields.Datetime.now():
            return challenge.browse()
        website = self._auth_website()
        if challenge.website_id and challenge.website_id != website and (website or browser):
            return challenge.browse()
        if (request and request.session.uid and challenge.user_id
                and challenge.purpose in {"lookup", "otp", "email_reset", "grant"}
                and challenge.user_id.id != request.session.uid):
            return challenge.browse()
        scoped = self.with_context(website_id=challenge.website_id.id) if challenge.website_id and not website else self
        if challenge.user_id and not scoped._eligible_customer(challenge.user_id):
            return challenge.browse()
        if challenge.purpose in {"otp", "grant", "lookup"} and not browser:
            return challenge.browse()
        if challenge.channel == "telegram" and not self._channel("telegram")._enabled():
            return challenge.browse()
        if browser and not secrets.compare_digest(challenge.browser_hash or "", self._digest("browser:" + browser)):
            return challenge.browse()
        if challenge.user_id and (not challenge.user_id.active or not secrets.compare_digest(challenge.credential_stamp or "", self._credential_stamp(challenge.user_id))):
            return challenge.browse()
        return challenge

    def _queue(self, channel, payload, challenge=None, update_key=None):
        return self.env["ab_storefront_auth_event"].sudo().create({
            "channel": channel, "payload": self._cipher().encrypt(json.dumps(payload).encode()).decode(),
            "challenge_id": challenge.id if challenge else False, "update_key": update_key,
        })

    def _identities(self, user):
        return self.env["ab_storefront_auth_identity"].sudo().search([("user_id", "=", user.id)])

    def _auth_website(self):
        website_id = request.website.id if request and hasattr(request, "website") else self.env.context.get("website_id")
        return self.env["website"].sudo().browse(website_id).exists()

    def _eligible_customer(self, user):
        website = self._auth_website()
        return bool(user and user.active and user.share and (
            not website or (user.company_id == website.company_id and (not user.website_id or user.website_id == website))))

    def _available_channels(self, user):
        if not self._eligible_customer(user):
            return []
        return [name for name in self._channel_registry() if self._channel(name)._available_for(user)]

    def _recovery_destination(self, user, channel):
        identity = self._identities(user).filtered(lambda item: item.kind == self._channel(channel)._identity_kind())
        if identity:
            return identity.value
        return user.email if channel == "email" else False

    def _resolve_recovery_user(self, identifier):
        identifier = str(identifier or "").strip()[:254]
        users = self.env["res.users"].sudo().browse()
        if not identifier:
            return users
        candidates = self.env["res.users"].sudo().search([
            ("active", "=", True), ("share", "=", True),
            "|", ("login", "=ilike", identifier), ("email", "=ilike", identifier),
        ])
        Identity = self.env["ab_storefront_auth_identity"].sudo()
        for kind in ("email", "phone"):
            try:
                value = normalize_identity(kind, identifier)
            except ValidationError:
                continue
            kinds = ["email"] if kind == "email" else ["phone", "whatsapp"]
            candidates |= Identity.search(["|", "&", ("kind", "in", kinds), ("value", "=", value),
                                          "&", ("kind", "=", "telegram"), ("phone_value", "=", value)]).user_id
        candidates = candidates.filtered(self._eligible_customer)
        return candidates if len(candidates) == 1 else users

    def _lookup_recovery(self, identifier, browser, ip, user=None):
        if not browser or not self._rate_allow("lookup-ip", ip, 20) or not self._rate_allow("lookup-browser", browser, 10):
            return False
        target = user.sudo() if user else self._resolve_recovery_user(identifier)
        if not self._eligible_customer(target):
            return False
        challenge, token = self._new_challenge("lookup", target, browser, ttl=300)
        return token

    def _invalidate_recovery(self, browser):
        self._lock("recovery-browser:" + self._digest(browser))
        self.env["ab_storefront_auth_challenge"].sudo().search([
            ("browser_hash", "=", self._digest("browser:" + browser)),
            ("purpose", "in", ["otp", "email_reset", "grant"]), ("used_at", "=", False),
        ]).write({"used_at": fields.Datetime.now(), "code_hash": False})

    def _profile_contact_status(self, user):
        identities = self._identities(user)
        result = {}
        for kind, value in (("phone", user.phone), ("email", user.email)):
            verified = False
            try:
                normalized = normalize_identity(kind, value)
                verified = bool(identities.filtered(lambda item: item.kind == kind and item.value == normalized))
            except ValidationError:
                pass
            result[kind] = {"value": value, "verified": verified}
        return result

    def _social_contacts(self, user):
        if not self._eligible_customer(user):
            return []
        identities = self._identities(user)
        pending = self.env["ab_storefront_auth_challenge"].sudo().search([
            ("user_id", "=", user.id), ("purpose", "=", "link"), ("used_at", "=", False),
            ("website_id", "in", [False, self._auth_website().id]),
            ("expires_at", ">", fields.Datetime.now()),
        ], order="id desc")
        contacts = []
        for channel in ("whatsapp", "telegram"):
            identity = identities.filtered(lambda item: item.kind == channel)
            attempt = pending.filtered(lambda item: item.channel == channel)[:1]
            contacts.append({"channel": channel, "value": (identity.phone_value or identity.value) if identity else attempt.value,
                             "verified": bool(identity), "pending": bool(attempt),
                             "enabled": channel in self._channel_registry() and self._channel(channel)._enabled(),
                             "url": "/ab_storefront/auth/whatsapp/link" if channel == "whatsapp" else "/ab_storefront/auth/phone"})
        return contacts

    def _assert_available_identity(self, user, kind, value):
        Identity = self.env["ab_storefront_auth_identity"].sudo()
        other = Identity.search([("kind", "=", kind), ("value", "=", value)], limit=1)
        if other and (not user or other.user_id != user):
            raise ValidationError(_("This identity is already linked to an account."))
        aliases = [value]
        if kind == "phone" and value.startswith("+20"):
            aliases.append("0" + value[3:])
        existing = self.env["res.users"].sudo().with_context(active_test=False).search([("login", "in", aliases)])
        if existing and (not user or existing != user):
            raise ValidationError(_("This identity is already linked to an account."))
        if kind == "email":
            existing = self.env["res.users"].sudo().with_context(active_test=False).search([("email", "=ilike", value)])
            if existing and (not user or existing != user):
                raise ValidationError(_("This identity is already linked to an account."))

    def _set_identity(self, user, kind, value, chat_id=None, phone_value=None):
        value = normalize_identity(kind, value)
        self._lock("identity:" + kind + ":" + value)
        self._lock("identities-user:" + str(user.id))
        self._assert_available_identity(user, kind, value)
        identity = self._identities(user).filtered(lambda item: item.kind == kind)
        values = {"user_id": user.id, "kind": kind, "value": value, "chat_id": chat_id, "phone_value": phone_value, "verified_at": fields.Datetime.now()}
        if identity:
            identity.write(values)
        else:
            self.env["ab_storefront_auth_identity"].sudo().create(values)
        self.env["ab_storefront_auth_challenge"].sudo().search([("user_id", "=", user.id), ("purpose", "in", ["otp", "email_reset", "grant"]), ("used_at", "=", False)]).write({"used_at": fields.Datetime.now(), "code_hash": False})

    def _request_email_verification(self, user, email, browser, ip):
        email = normalize_identity("email", email)
        if not self._rate_allow("email-verify-ip", ip, 20) or not self._rate_allow("email-verify", str(user.id)):
            return False
        self._assert_available_identity(user, "email", email)
        challenge, token = self._new_challenge("email_verify", user, value=email, channel="email")
        self._queue("email", {"user_id": user.id, "destination": email, "purpose": "email_verify", "url": self._base_url() + "/ab_storefront/auth/confirm#" + token}, challenge)
        return True

    def _request_link(self, user, phone, browser, ip):
        if not self._channel("telegram")._enabled():
            raise UserError(_("Telegram verification is currently unavailable on this website. Choose another method or contact support."))
        phone = normalize_identity("phone", phone)
        allowed_ip, retry_after = self._rate_allow_with_retry("link-ip", ip, 20)
        if not allowed_ip:
            raise AuthRateLimitError(retry_after)
        allowed_phone, retry_after = self._rate_allow_with_retry("link-phone", phone)
        if not allowed_phone:
            raise AuthRateLimitError(retry_after)
        if user and not self._eligible_customer(user):
            raise ValidationError(_("The code or link is invalid or expired."))
        if not user:
            self._assert_available_identity(user, "phone", phone)
        if not user and self.env["res.users"]._get_signup_invitation_scope() != "b2c":
            raise UserError(_("Signup is not allowed for uninvited users."))
        old = self.env["ab_storefront_auth_challenge"].sudo().search([("browser_hash", "=", self._digest("browser:" + browser)), ("purpose", "in", ["link", "phone_signup"]), ("used_at", "=", False)])
        old.write({"used_at": fields.Datetime.now()})
        challenge, token = self._new_challenge("link" if user else "phone_signup", user, browser, phone, "telegram")
        username = self.env["ir.config_parameter"].sudo().get_param("ab_storefront_auth.telegram_bot_username", "Abdin_Pharmacy_Bot").lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            raise UserError(_("Telegram delivery is unavailable."))
        return token, "https://t.me/" + username + "?start=" + token

    def _finish_link(self, token, browser, user):
        challenge = self._find(token, ["link"], browser)
        if not browser or not challenge or challenge.channel != "telegram" or challenge.user_id != user or not challenge.phone_verified:
            return False
        if not self._identities(user).filtered(lambda item: item.kind == "phone") and not user.partner_id.phone:
            self._set_identity(user, "phone", challenge.value)
        self._set_identity(user, "telegram", challenge.telegram_user_id, challenge.telegram_chat_id, challenge.value)
        if not user.partner_id.phone:
            user.partner_id.phone = challenge.value
        challenge.write({"used_at": fields.Datetime.now()})
        return True

    def _finish_phone_signup(self, token, browser, values):
        challenge = self._find(token, ["phone_signup"], browser)
        if not browser or not challenge or challenge.channel != "telegram" or not challenge.phone_verified:
            raise ValidationError(_("Complete Telegram phone verification first."))
        self._lock("identity:phone:" + challenge.value)
        self._assert_available_identity(None, "phone", challenge.value)
        values = dict(values, login=challenge.value, phone=challenge.value, email=False, ab_signup_otp_pending=True)
        user = self.env["res.users"].sudo().with_context(no_reset_password=True)._signup_create_user(values)
        user.write({"email": False})
        self._set_identity(user, "phone", challenge.value)
        self._set_identity(user, "telegram", challenge.telegram_user_id, challenge.telegram_chat_id, challenge.value)
        if not user.partner_id.phone:
            user.partner_id.phone = challenge.value
        challenge.write({"used_at": fields.Datetime.now()})
        return user

    def _recovery_user(self, kind, value):
        identity = self.env["ab_storefront_auth_identity"].sudo().search([("kind", "=", kind), ("value", "=", value)], limit=1)
        if identity:
            user = identity.user_id
        elif kind == "email":
            users = self.env["res.users"].sudo().search([("email", "=ilike", value), ("share", "=", True)], limit=2)
            user = users if len(users) == 1 else users.browse()
            if user and self._identities(user).filtered(lambda item: item.kind == "email"):
                user = user.browse()
        else:
            user = self.env["res.users"].sudo().browse()
        return user if user and user.active and user.share else user.browse()

    def _request_recovery(self, channel, identifier, browser, ip):
        adapter = self._channel(channel)
        if not browser:
            return False
        user = self._resolve_recovery_user(identifier)
        if request and request.session.uid:
            user = request.env.user.sudo()
        value = self._recovery_destination(user, channel) if user else "invalid"
        allowed_ip = self._rate_allow("recovery-ip", ip, self._setting("ip_rate_limit", 20, maximum=200))
        if not allowed_ip:
            return False
        subject = value if channel == "whatsapp" and value and user else str(user.id) if user else "invalid"
        if not self._rate_allow("recovery", subject) or not self._rate_allow("recovery-cooldown", subject, 1, self._setting("resend_cooldown", 60, maximum=3600)):
            return False
        if user and (not self._eligible_customer(user) or not adapter._can_recover(user)):
            return False
        self._invalidate_recovery(browser)
        purpose = adapter._recovery_purpose()
        challenge, token = self._new_challenge(purpose, user, browser, value=value or "invalid", channel=channel,
                                              ttl=self._setting("otp_expiration", 300, maximum=900) if purpose == "otp" else None)
        if purpose == "otp":
            challenge.code_hash = self._digest("decoy-code:" + token)
        self._queue("recovery_request", {"token": token, "allowed": True}, challenge)
        self._wake_delivery()
        return token

    def _prepare_recovery(self, challenge, payload):
        adapter = self._channel(challenge.channel)
        user = challenge.user_id
        website = challenge.website_id
        service = self.with_context(website_id=website.id) if website else self
        if (service._eligible_customer(user) and adapter._can_recover(user) and payload.get("allowed")
                and challenge.value == service._recovery_destination(user, challenge.channel)):
            self._lock("recovery-user:" + str(user.id))
            old = self.env["ab_storefront_auth_challenge"].sudo().search([
                ("user_id", "=", user.id), ("purpose", "in", ["otp", "email_reset", "grant"]),
                ("used_at", "=", False), ("id", "!=", challenge.id),
            ])
            old.write({"used_at": fields.Datetime.now(), "code_hash": False})
            adapter._prepare_recovery(service, challenge, payload["token"])

    def _generate_otp(self, challenge, token):
        code = f"{secrets.randbelow(1000000):06d}"
        challenge.write({"code_hash": self._digest("otp:" + token + ":" + code)})
        return code

    def _verify_recovery(self, token, browser, code=None):
        challenge = self._find(token, ["otp", "email_reset"], browser if code is not None else None)
        if not challenge:
            return False
        if challenge.purpose == "otp":
            challenge.write({"attempts": challenge.attempts + 1})
            if challenge.attempts > self._setting("otp_max_attempts", 5, maximum=10):
                challenge.write({"used_at": fields.Datetime.now()})
                return False
            if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code) or not secrets.compare_digest(challenge.code_hash or "", self._digest("otp:" + token + ":" + code)):
                if challenge.attempts >= self._setting("otp_max_attempts", 5, maximum=10):
                    challenge.write({"used_at": fields.Datetime.now()})
                return False
        if not challenge.user_id or not self._channel(challenge.channel)._can_recover(challenge.user_id):
            return False
        if challenge.value != self._recovery_destination(challenge.user_id, challenge.channel):
            return False
        challenge.write({"used_at": fields.Datetime.now(), "code_hash": False})
        if challenge.purpose == "email_reset":
            self._set_identity(challenge.user_id, "email", challenge.value)
        grant, grant_token = self._new_challenge("grant", challenge.user_id, browser, value=challenge.value, channel=challenge.channel, ttl=300)
        return grant_token

    def _confirm_email(self, token):
        challenge = self._find(token, ["email_verify"])
        if not challenge or not challenge.user_id:
            return False
        self._set_identity(challenge.user_id, "email", challenge.value)
        challenge.user_id.partner_id.write({"email": challenge.value})
        challenge.write({"used_at": fields.Datetime.now()})
        return True

    def _reset_password(self, token, browser, password):
        challenge = self._find(token, ["grant"], browser)
        if not challenge:
            return False
        user = challenge.user_id
        if not self._channel(challenge.channel)._can_recover(user) or challenge.value != self._recovery_destination(user, challenge.channel):
            return False
        self._lock("password-user:" + str(user.id))
        user.invalidate_recordset()
        if not secrets.compare_digest(challenge.credential_stamp, self._credential_stamp(user)):
            return False
        user.write({"password": password})
        user.partner_id.signup_cancel()
        self.env["ab_storefront_auth_challenge"].sudo().search([("user_id", "=", user.id), ("used_at", "=", False)]).write({"used_at": fields.Datetime.now(), "code_hash": False})
        return True

    def _wake_delivery(self):
        return self.env.ref("ab_ecommerce_storefront.cron_auth_delivery").sudo()._trigger()

    def _ingest_update(self, update, wake_delivery=False):
        update_id = update.get("update_id")
        if type(update_id) is not int or update_id < 0:
            return False
        key = str(update_id)
        self._lock("telegram-update:" + key)
        Event = self.env["ab_storefront_auth_event"].sudo()
        if Event.search_count([("update_key", "=", key)], limit=1):
            return True
        callback = update.get("callback_query")
        if callback is not None:
            if not isinstance(callback, dict):
                return False
            self._queue("telegram_update", {"update_id": update_id, "callback_query": {key: callback[key] for key in ("id", "from", "message", "data") if key in callback}}, update_key=key)
            if wake_delivery:
                self._wake_delivery()
            return True
        message = update.get("message", {})
        if not isinstance(message, dict):
            return False
        minimal = {"update_id": update_id, "message": {key: message[key] for key in ("chat", "from", "text", "contact", "date", "forward_origin") if key in message}}
        self._queue("telegram_update", minimal, update_key=key)
        if wake_delivery:
            self._wake_delivery()
        return True

    def _process_telegram_update(self, update):
        if not self._channel("telegram")._enabled():
            return
        if isinstance(update.get("callback_query"), dict):
            callback = update["callback_query"]
            self._process_device_callback(callback)
            if isinstance(callback.get("id"), str):
                self._queue("telegram", {"callback_query_id": callback["id"][:200]})
            return
        message = update.get("message", {})
        sender = message.get("from", {})
        chat = message.get("chat", {})
        if not isinstance(sender, dict) or not isinstance(chat, dict) or chat.get("type") != "private" or sender.get("is_bot") or type(sender.get("id")) is not int or sender.get("id") != chat.get("id"):
            return
        telegram_id = str(sender["id"])
        normalize_identity("telegram", telegram_id)
        if not self._rate_allow("telegram-message", telegram_id, 30, 60):
            return
        language = "ar_001" if (sender.get("language_code") or "ar").startswith("ar") else "en_US"
        translated = self.with_context(lang=language).env
        text = str(message.get("text") or "")[:200]
        command = text.split(" ", 1)[0].split("@", 1)[0]
        reply = translated._("This bot is used by Abdin Pharmacy to verify your account and send security codes. Start linking from the pharmacy website. Never send your password here.")
        markup = {"remove_keyboard": True}
        if command == "/cancel":
            self.env["ab_storefront_auth_challenge"].sudo().search([("telegram_user_id", "=", telegram_id), ("purpose", "in", ["link", "phone_signup"]), ("used_at", "=", False)]).write({"used_at": fields.Datetime.now()})
            reply = translated._("Verification cancelled. Return to the pharmacy website to try again.")
        elif command == "/start" and " " in text:
            token = text.split(" ", 1)[1].strip()
            challenge = self._find(token, ["link", "phone_signup"])
            if not challenge or (challenge.telegram_user_id and challenge.telegram_user_id != telegram_id):
                reply = translated._("This linking request is invalid or expired. Start again from the website.")
            elif challenge.telegram_user_id == telegram_id:
                if challenge.phone_verified:
                    reply = translated._("Phone verified. Return to the pharmacy website and confirm the Telegram connection.")
                else:
                    reply = translated._("Press the “Share my phone number” button below to verify the phone entered on the website. Do not type the number or send another contact. Then return to the website and confirm the connection.")
                    markup = {"keyboard": [[{"text": translated._("Share my phone number"), "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}
            else:
                self._lock("telegram-claim:" + telegram_id)
                existing = self.env["ab_storefront_auth_identity"].sudo().search([("kind", "=", "telegram"), ("value", "=", telegram_id)], limit=1)
                if existing and existing.user_id != challenge.user_id:
                    reply = translated._("This Telegram account cannot be linked. Return to the website.")
                else:
                    self.env["ab_storefront_auth_challenge"].sudo().search([("telegram_user_id", "=", telegram_id), ("purpose", "in", ["link", "phone_signup"]), ("used_at", "=", False)]).write({"used_at": fields.Datetime.now()})
                    challenge.write({"telegram_user_id": telegram_id, "telegram_chat_id": telegram_id})
                    reply = translated._("Press the “Share my phone number” button below to verify the phone entered on the website. Do not type the number or send another contact. Then return to the website and confirm the connection.")
                    markup = {"keyboard": [[{"text": translated._("Share my phone number"), "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}
        elif isinstance(message.get("contact"), dict):
            contact = message["contact"]
            self._lock("telegram-claim:" + telegram_id)
            challenge = self.env["ab_storefront_auth_challenge"].sudo().search([("telegram_user_id", "=", telegram_id), ("purpose", "in", ["link", "phone_signup"]), ("used_at", "=", False), ("expires_at", ">", fields.Datetime.now())], limit=1)
            try:
                phone = normalize_identity("phone", contact.get("phone_number"))
            except ValidationError:
                phone = False
            if challenge and type(contact.get("user_id")) is int and contact["user_id"] == sender["id"] and phone == challenge.value and not message.get("forward_origin"):
                challenge.write({"phone_verified": True})
                reply = translated._("Phone verified. Return to the pharmacy website and confirm the Telegram connection.")
            else:
                reply = translated._("The contact must be your own Telegram contact and match the phone entered on the website.")
        self._queue("telegram", {"chat_id": telegram_id, "text": reply, "reply_markup": markup})

    @api.model
    def _process_queue(self):
        Event = self.env["ab_storefront_auth_event"].sudo()
        deadline = time.monotonic() + 30
        processed = 0
        while processed < 100 and time.monotonic() < deadline:
            domain = [("state", "=", "pending"), ("next_attempt", "<=", fields.Datetime.now())]
            events = Event.search(domain, order="id", limit=10)
            if not events:
                break
            for event in events:
                self._process_event(event)
                processed += 1
                if self.env.context.get("cron_id"):
                    remaining = Event.search_count(domain)
                    if not self.env["ir.cron"]._commit_progress(1, remaining=remaining):
                        return
                if time.monotonic() >= deadline:
                    return

    def _process_event(self, event):
        self._lock("event:" + str(event.id))
        event.invalidate_recordset()
        if event.state != "pending":
            return
        challenge = event.challenge_id
        if challenge:
            self._lock("challenge:" + challenge.token_hash)
            challenge.invalidate_recordset()
        if challenge and (challenge.used_at or challenge.expires_at <= fields.Datetime.now()):
            event.write({"state": "done", "payload": False})
            return
        try:
            with self.env.cr.savepoint():
                payload = json.loads(self._cipher().decrypt(event.payload.encode()).decode())
                if event.channel == "telegram_update":
                    self._process_telegram_update(payload)
                elif event.channel == "recovery_request":
                    self._prepare_recovery(challenge, payload)
                else:
                    self._channel(event.channel)._deliver(payload)
                event.write({"state": "done", "payload": False})
        except (UserError, ValueError, InvalidToken):
            attempts = event.attempts + 1
            event.write({"attempts": attempts, "state": "failed" if attempts >= 3 else "pending", "payload": False if attempts >= 3 else event.payload, "next_attempt": fields.Datetime.now() + timedelta(seconds=30 * attempts)})
            _logger.warning("Storefront authentication delivery deferred: event=%s channel=%s attempt=%s", event.id, event.channel, attempts)
