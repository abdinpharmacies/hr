import json
import logging
import re
import secrets
import urllib.error
import urllib.request

from odoo import api, fields, models
from odoo.exceptions import AccessDenied, AccessError, ValidationError
from odoo.tools import config as odoo_config

_logger = logging.getLogger(__name__)

class AbUserTelegramLink(models.Model):
    _name = "ab_user_telegram_link"
    _description = "Telegram User Link"
    _order = "write_date desc, id desc"

    _telegram_user_id_key = models.Constraint(
        "UNIQUE(telegram_user_id)",
        "This Telegram account is already linked.",
    )
    _user_id_key = models.Constraint(
        "UNIQUE(user_id)",
        "This Odoo user is already linked to another Telegram account.",
    )

    telegram_user_id = fields.Char(required=True, index=True, copy=False)
    telegram_chat_id = fields.Char(index=True, copy=False)
    telegram_username = fields.Char(index=True, copy=False)
    telegram_first_name = fields.Char(copy=False)
    telegram_last_name = fields.Char(copy=False)
    telegram_full_name = fields.Char(compute="_compute_telegram_full_name", store=True)
    telegram_phone = fields.Char(copy=False)
    telegram_language_code = fields.Char(copy=False)
    status = fields.Selection(
        [
            ("new", "New"),
            ("awaiting_email", "Awaiting Email"),
            ("awaiting_password", "Awaiting Secret"),
            ("linked", "Linked"),
            ("stale", "Stale (Password Changed)"),
        ],
        required=True,
        default="new",
        index=True,
    )
    pending_action = fields.Selection(
        [("link", "Link"), ("unlink", "Unlink")],
        copy=False,
        index=True,
    )
    pending_email = fields.Char(copy=False)

    user_id = fields.Many2one("res.users", ondelete="set null", index=True)
    login_email = fields.Char(index=True, copy=False)

    pin = fields.Char(required=True, copy=False, default=lambda self: self._generate_pin())
    pin_generated_at = fields.Datetime(copy=False)
    linked_at = fields.Datetime(copy=False)
    last_verified_at = fields.Datetime(copy=False)
    last_error = fields.Char(copy=False)
    ai_context_token_limit = fields.Integer(default=1000, copy=False)
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.constrains("pin")
    def _check_pin(self):
        for rec in self:
            if not rec.pin or len(rec.pin) != 4 or not rec.pin.isdigit():
                raise ValidationError("PIN must contain exactly 4 digits.")

    @api.constrains("ai_context_token_limit")
    def _check_ai_context_token_limit(self):
        for rec in self:
            if rec.ai_context_token_limit <= 0:
                raise ValidationError("Context token limit must be greater than zero.")

    @api.depends("telegram_user_id", "user_id", "user_id.name")
    def _compute_display_name(self):
        for rec in self:
            if rec.user_id:
                rec.display_name = f"{rec.user_id.name} ({rec.telegram_user_id})"
            else:
                rec.display_name = rec.telegram_user_id or "-"

    @api.depends("telegram_first_name", "telegram_last_name", "telegram_username", "telegram_user_id")
    def _compute_telegram_full_name(self):
        for rec in self:
            name = " ".join(part for part in (rec.telegram_first_name, rec.telegram_last_name) if part)
            if not name and rec.telegram_username:
                name = f"@{rec.telegram_username}"
            rec.telegram_full_name = name or rec.telegram_user_id or "-"

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        prepared_vals_list = []
        for vals in vals_list:
            vals = dict(vals or {})
            if not vals.get("pin"):
                vals["pin"] = self._generate_pin()
            if not vals.get("pin_generated_at"):
                vals["pin_generated_at"] = now
            vals = self._prepare_manual_link_vals(vals, now=now)
            prepared_vals_list.append(vals)
        return super().create(prepared_vals_list)

    def write(self, vals):
        now = fields.Datetime.now()
        if not isinstance(vals, dict) or "user_id" not in vals:
            return super().write(vals)

        for rec in self:
            rec_vals = self._prepare_manual_link_vals(dict(vals), now=now, record=rec)
            super(AbUserTelegramLink, rec).write(rec_vals)
        return True

    @api.model
    def _generate_pin(self):
        return f"{secrets.randbelow(10000):04d}"

    @staticmethod
    def _is_truthy_id(value):
        return bool(value and str(value).strip() not in {"0", "False", "false"})

    def _prepare_manual_link_vals(self, vals, now=None, record=None):
        values = dict(vals or {})
        now = now or fields.Datetime.now()

        if "user_id" not in values:
            return values

        if not self._is_truthy_id(values.get("user_id")):
            values.setdefault("status", "new")
            values.setdefault("pending_action", False)
            values.setdefault("pending_email", False)
            values.setdefault("login_email", False)
            values.setdefault("linked_at", False)
            return values

        user = self.env["res.users"].sudo().browse(int(values["user_id"])).exists()
        if not user:
            return values

        values["status"] = "linked"
        values.setdefault("pending_action", False)
        values.setdefault("pending_email", False)
        values.setdefault("last_error", False)
        values.setdefault("login_email", user.login)
        values.setdefault("last_verified_at", now)

        linked_at_present = bool(values.get("linked_at")) or bool(record and record.linked_at)
        if not linked_at_present:
            values.setdefault("linked_at", now)

        return values

    def _is_link_active(self):
        self.ensure_one()
        return bool(self.user_id and self.status in {"linked", "stale"})

    @staticmethod
    def _normalize_text(text):
        cleaned = (text or "").strip().lower().replace("_", " ").replace("-", " ")
        return " ".join(cleaned.split())

    @api.model
    def _default_keyboard_rows(self):
        return [
            ["Get My ID", "User Settings"],
            ["AI Session", "Help"],
        ]

    @api.model
    def _cancel_keyboard_rows(self):
        return [["Cancel"]]

    @api.model
    def _session_keyboard_rows(self):
        return [
            ["Status", "New Session"],
            ["Back"],
        ]

    @api.model
    def _user_settings_keyboard_rows(self):
        return [
            ["Link Odoo Account", "Unlink Odoo Account"],
            ["My PIN", "Back"],
        ]

    @api.model
    def _payload(self, text, note, keyboard_rows=None):
        return {
            "handled": True,
            "text": text,
            "note": note,
            "keyboard_rows": keyboard_rows if keyboard_rows is not None else self._default_keyboard_rows(),
        }

    @staticmethod
    def _estimate_text_tokens(text):
        text_value = str(text or "").strip()
        if not text_value:
            return 0
        words = len(re.findall(r"\S+", text_value))
        chars = len(text_value) // 4
        return max(words, chars)

    @classmethod
    def _estimate_messages_tokens(cls, messages):
        total = 0
        for item in messages or []:
            if not isinstance(item, dict):
                continue
            total += cls._estimate_text_tokens(item.get("content"))
            total += 4
        return total

    @staticmethod
    def _session_messages(session_json):
        if isinstance(session_json, dict):
            messages = session_json.get("messages")
            return list(messages) if isinstance(messages, list) else []
        if isinstance(session_json, list):
            return list(session_json)
        return []

    def _active_ai_session(self):
        self.ensure_one()
        Chat = self.env["ab_telegram_chat_message"].sudo()
        return Chat.search(
            [
                ("telegram_user_id", "=", self.telegram_user_id),
                ("linked_user_id", "=", self.user_id.id),
                ("session_status", "=", "open"),
            ],
            order="id desc",
            limit=1,
        )

    def _open_ai_session(self):
        self.ensure_one()
        Chat = self.env["ab_telegram_chat_message"].sudo()
        return Chat.create(
            {
                "direction": "out",
                "echo_status": "echoed",
                "processing_note": "ai_session_opened",
                "telegram_chat_id": self.telegram_chat_id or self.telegram_user_id or "-",
                "telegram_user_id": self.telegram_user_id,
                "chat_type": "private",
                "content_type": "json_context",
                "content_text": "",
                "message_datetime": fields.Datetime.now(),
                "username": self.telegram_username,
                "first_name": self.telegram_first_name,
                "last_name": self.telegram_last_name,
                "phone": self.telegram_phone,
                "language_code": self.telegram_language_code,
                "linked_user_id": self.user_id.id or False,
                "session_status": "open",
                "token_limit": int(self.ai_context_token_limit or 1000),
                "token_count": 0,
                "openai_messages_json": {"messages": []},
                "started_at": fields.Datetime.now(),
                "last_message_datetime": fields.Datetime.now(),
            }
        )

    def _store_ai_turn(self, session, user_prompt, assistant_reply):
        self.ensure_one()
        messages = self._session_messages(session.openai_messages_json)
        messages.append({"role": "user", "content": user_prompt or ""})
        messages.append({"role": "assistant", "content": assistant_reply or ""})
        token_count = self._estimate_messages_tokens(messages)
        session.write(
            {
                "processing_note": "ai_turn_stored",
                "content_text": False,
                "openai_messages_json": {"messages": messages},
                "token_count": token_count,
                "token_limit": int(self.ai_context_token_limit or 1000),
                "last_message_datetime": fields.Datetime.now(),
                "linked_user_id": self.user_id.id or False,
                "username": self.telegram_username,
                "first_name": self.telegram_first_name,
                "last_name": self.telegram_last_name,
                "phone": self.telegram_phone,
                "language_code": self.telegram_language_code,
            }
        )

    def _rotate_ai_session_if_needed(self, incoming_user_prompt):
        self.ensure_one()
        session = self._active_ai_session()
        if not session:
            return self._open_ai_session(), False

        token_limit = int(self.ai_context_token_limit or 1000)
        pending_messages = self._session_messages(session.openai_messages_json) + [
            {"role": "user", "content": incoming_user_prompt or ""}
        ]
        if self._estimate_messages_tokens(pending_messages) <= token_limit:
            return session, False

        session.write(
            {
                "session_status": "closed",
                "close_reason": "token_limit_reached",
                "processing_note": "ai_session_closed_by_limit",
            }
        )
        return self._open_ai_session(), True

    @api.model
    def _get_openai_settings(self):
        api_key = (
            (odoo_config.get("openai_api_token") or "").strip()
            or (odoo_config.get("openai_api_key") or "").strip()
        )
        base_url = (odoo_config.get("openai_base_url") or "https://api.openai.com/v1").strip()
        configured_model = (odoo_config.get("openai_model") or "").strip()

        model_candidates = []
        if configured_model:
            model_candidates.append(configured_model)
        model_candidates.extend(["gpt-5.2", "gpt-5.1", "gpt-4.1-mini", "gpt-4.1"])

        deduplicated_models = []
        for model_name in model_candidates:
            if model_name and model_name not in deduplicated_models:
                deduplicated_models.append(model_name)

        return {
            "api_key": api_key,
            "base_url": base_url,
            "models": deduplicated_models,
        }

    @api.model
    def _openai_chat_completions_url(self, base_url):
        base = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    @api.model
    def _extract_text_from_chat_completion(self, payload):
        choices = payload.get("choices") or []
        if not choices:
            return ""

        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get("type") == "text" and chunk.get("text"):
                    parts.append(chunk["text"])
            return "\n".join(parts).strip()
        return ""

    @api.model
    def _call_openai_chat_completion(self, settings, messages, model_name):
        url = self._openai_chat_completions_url(settings["base_url"])
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.1,
        }
        request = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {settings['api_key']}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=45) as response:  # noqa: S310
            response_body = response.read().decode("utf-8")
        completion_payload = json.loads(response_body or "{}")
        return self._extract_text_from_chat_completion(completion_payload)

    @api.model
    def _call_openai_with_fallback(self, settings, messages):
        last_error = ""
        for model_name in settings["models"]:
            try:
                content = self._call_openai_chat_completion(settings, messages, model_name)
                if content:
                    return content, model_name
            except urllib.error.HTTPError as exc:
                try:
                    error_body = exc.read().decode("utf-8")
                except Exception:
                    error_body = str(exc)
                last_error = f"{exc.code}: {error_body}"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)

        if last_error:
            _logger.warning("ab_user_extra: OpenAI call failed. %s", last_error)
        return "", ""

    @staticmethod
    def _extract_json_object(text):
        raw_text = (text or "").strip()
        if not raw_text:
            return {}

        try:
            return json.loads(raw_text)
        except Exception:
            pass

        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            return json.loads(raw_text[start : end + 1])
        except Exception:
            return {}

    @api.model
    def _get_accessible_ai_models(self, user):
        model_names = self.env["ir.model"].sudo().search([("model", "=like", "ab%")], order="model").mapped("model")
        accessible = []
        for model_name in model_names:
            if model_name not in self.env:
                continue
            model_obj = self.env[model_name].with_user(user)
            if model_obj.check_access_rights("read", raise_exception=False):
                accessible.append(model_name)
        return accessible

    @staticmethod
    def _extract_model_hints(prompt_text, allowed_models):
        tokens = re.findall(r"\bab[\w.]+\b", (prompt_text or "").lower())
        hinted_models = []
        allowed_set = set(allowed_models or [])
        for token in tokens:
            variants = {token, token.replace(".", "_"), token.replace("_", ".")}
            for variant in variants:
                if variant in allowed_set and variant not in hinted_models:
                    hinted_models.append(variant)
        return hinted_models

    @api.model
    def _ai_plan(self, settings, prompt_text, allowed_models, history_messages=None):
        hinted_models = self._extract_model_hints(prompt_text, allowed_models)
        if not allowed_models:
            return {}

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an Odoo query planner. Return JSON only.\n"
                    "Allowed actions: query, clarify.\n"
                    "For query return keys: action, model, domain, fields, limit.\n"
                    "Rules: model must be from AVAILABLE_MODELS, read-only. "
                    "Limit is optional; if missing or <= 0 then return all matching records."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "request": prompt_text,
                        "conversation_history": history_messages or [],
                        "available_models": allowed_models[:120],
                        "model_hints": hinted_models,
                        "json_examples": [
                            {
                                "action": "query",
                                "model": "ab_hr_employee",
                                "domain": [["name", "ilike", "ahmed"]],
                                "fields": ["name", "work_email", "job_id"],
                                "limit": 10,
                            },
                            {"action": "clarify", "message": "Please mention model name."},
                        ],
                    }
                ),
            },
        ]
        content, _model_used = self._call_openai_with_fallback(settings, messages)
        plan = self._extract_json_object(content)
        if plan:
            return plan

        if hinted_models:
            fallback_search_value = (prompt_text or "").strip()
            return {
                "action": "query",
                "model": hinted_models[0],
                "domain": [["display_name", "ilike", fallback_search_value]] if fallback_search_value else [],
                "fields": [],
                "limit": 5,
            }
        return {}

    @staticmethod
    def _field_read_allowed(model_obj, field_name):
        field = model_obj._fields.get(field_name)
        if not field:
            return False
        group_spec = (getattr(field, "groups", None) or "").strip()
        if not group_spec:
            return True
        user = model_obj.env.user
        for xmlid in [item.strip() for item in group_spec.split(",") if item.strip()]:
            try:
                if user.has_group(xmlid):
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    @classmethod
    def _sanitize_domain(cls, raw_domain, model_obj):
        allowed_ops = {
            "=",
            "!=",
            ">",
            ">=",
            "<",
            "<=",
            "ilike",
            "=ilike",
            "like",
            "=like",
            "in",
            "not in",
            "child_of",
        }
        if not isinstance(raw_domain, list):
            return []

        cleaned = []
        for token in raw_domain:
            if token in ("|", "&", "!"):
                cleaned.append(token)
                continue
            if not isinstance(token, (list, tuple)) or len(token) != 3:
                continue

            field_name, operator, value = token
            if (
                isinstance(field_name, str)
                and isinstance(operator, str)
                and field_name in model_obj._fields
                and operator in allowed_ops
                and cls._field_read_allowed(model_obj, field_name)
            ):
                cleaned.append((field_name, operator, value))
        return cleaned

    @classmethod
    def _safe_field_candidates(cls, model_obj, requested_fields):
        safe_types = {
            "char",
            "text",
            "integer",
            "float",
            "monetary",
            "boolean",
            "date",
            "datetime",
            "selection",
            "many2one",
        }
        blocked_name_parts = ("password", "passwd", "secret", "token", "api_key")

        def is_safe_field(field_name):
            field = model_obj._fields.get(field_name)
            if not field:
                return False
            if not cls._field_read_allowed(model_obj, field_name):
                return False
            field_type = getattr(field, "type", None) or getattr(field, "ttype", None)
            if field_type not in safe_types:
                return False
            lowered = field_name.lower()
            return not any(part in lowered for part in blocked_name_parts)

        valid_fields = []
        for name in requested_fields or []:
            if isinstance(name, str) and is_safe_field(name) and name not in valid_fields:
                valid_fields.append(name)

        if valid_fields:
            return valid_fields

        preferred_fields = [
            "display_name",
            "name",
            "english_name",
            "work_email",
            "email",
            "mobile_phone",
            "work_phone",
            "job_id",
            "department_id",
            "active",
        ]
        rec_name = model_obj._rec_name or "display_name"
        if rec_name not in preferred_fields:
            preferred_fields.insert(0, rec_name)

        for field_name in preferred_fields:
            if is_safe_field(field_name) and field_name not in valid_fields:
                valid_fields.append(field_name)
            if len(valid_fields) >= 8:
                break
        return valid_fields

    @staticmethod
    def _format_records_as_text(model_name, records, max_rows=10):
        if not records:
            return "No records found."

        lines = [f"Model: {model_name}", f"Rows: {len(records)}"]
        for idx, row in enumerate(records[:max_rows], start=1):
            rendered = []
            for key, value in row.items():
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    value = value[1]
                rendered.append(f"{key}={value}")
            lines.append(f"{idx}. " + ", ".join(rendered))
        return "\n".join(lines)

    def _ai_answer_for_prompt(self, prompt_text):
        self.ensure_one()
        self._sync_password_state()
        if not self._is_link_active():
            return self._payload(
                "Your account is not linked. Select \"Link Odoo Account\" first.",
                note="not_linked",
            )

        settings = self._get_openai_settings()
        if not settings["api_key"]:
            return self._payload(
                "AI integration is not configured. Missing openai_api_token (or openai_api_key fallback) in server config.",
                note="ai_not_configured",
            )

        session, is_new_session = self._rotate_ai_session_if_needed(prompt_text)
        history_messages = self._session_messages(session.openai_messages_json)

        allowed_models = self._get_accessible_ai_models(self.user_id)
        if not allowed_models:
            return self._payload(
                "No readable business models found for your account.",
                note="no_readable_models",
            )

        plan = self._ai_plan(
            settings=settings,
            prompt_text=prompt_text,
            allowed_models=allowed_models,
            history_messages=history_messages,
        )
        if not plan:
            return self._payload(
                "I could not understand your request. Please mention model name and what data you need.",
                note="ai_clarify",
            )

        if plan.get("action") != "query":
            clarify_msg = (plan.get("message") or "").strip() or (
                "Please mention model name and what data you need."
            )
            return self._payload(clarify_msg, note="ai_clarify")

        model_name = (plan.get("model") or "").strip()
        if model_name not in allowed_models:
            return self._payload(
                "Requested model is not allowed for your account.",
                note="ai_model_not_allowed",
            )

        model_obj = self.env[model_name].with_user(self.user_id)
        if not model_obj.check_access_rights("read", raise_exception=False):
            return self._payload(
                "You do not have read access to this model.",
                note="ai_access_denied",
            )

        domain = self._sanitize_domain(plan.get("domain"), model_obj)
        fields_to_read = self._safe_field_candidates(model_obj, plan.get("fields"))
        limit_value = plan.get("limit")
        try:
            limit = int(limit_value) if limit_value not in (None, "", False) else 0
        except (TypeError, ValueError):
            limit = 0
        limit = limit if limit > 0 else False

        try:
            records = model_obj.search_read(domain=domain, fields=fields_to_read, limit=limit)
        except (AccessDenied, AccessError):
            return self._payload(
                "You do not have access to the requested records.",
                note="ai_access_denied",
            )
        except Exception:  # noqa: BLE001
            _logger.exception("ab_user_extra: AI query execution failed.")
            return self._payload(
                "Failed to read requested data. Try a simpler request.",
                note="ai_query_failed",
            )

        raw_result_text = self._format_records_as_text(model_name, records)
        if not records:
            return self._payload(raw_result_text, note="ai_no_data")

        summarize_messages = [
            {
                "role": "system",
                "content": (
                    "Answer using only the provided records. "
                    "Do not invent data. Keep answer concise."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "request": prompt_text,
                        "model": model_name,
                        "conversation_history": history_messages,
                        "records": records,
                    }
                ),
            },
        ]
        summary_text, _model_used = self._call_openai_with_fallback(settings, summarize_messages)
        response_text = (summary_text or "").strip() or raw_result_text
        if is_new_session:
            response_text = (
                "Context limit reached. I opened a new chat session for you.\n\n"
                + response_text
            )
        self._store_ai_turn(session, prompt_text, response_text)
        return self._payload(response_text, note="ai_answer_sent")

    @api.model
    def _find_user_by_email_or_login(self, email_or_login):
        login_value = (email_or_login or "").strip()
        if not login_value:
            return self.env["res.users"]

        Users = self.env["res.users"].sudo().with_context(active_test=False)
        domain = fields.Domain.OR(
            [[("login", "=", login_value)], [("email", "=", login_value)]]
        )
        return Users.search(domain, limit=1)

    @api.model
    def _validate_credentials(self, email_or_login, secret):
        user = self._find_user_by_email_or_login(email_or_login)
        if not user or not user.active:
            return self.env["res.users"]
        if not secret:
            return self.env["res.users"]

        credential = {"type": "password", "login": user.login, "password": secret}
        try:
            user.with_user(user)._check_credentials(credential, {"interactive": False})
            return user
        except AccessDenied:
            pass

        # Fallback for environments adding extra login gates (e.g. IP checks in _check_credentials).
        # For Telegram bot linking we still need strict credential validation against the target user.
        self.env.cr.execute("SELECT COALESCE(password, '') FROM res_users WHERE id=%s", (user.id,))
        row = self.env.cr.fetchone()
        hashed = (row[0] if row else "") or ""
        if hashed and user._crypt_context().verify(secret, hashed):
            return user

        try:
            uid = self.env["res.users.apikeys"].sudo()._check_credentials(scope="rpc", key=secret)
            if uid and int(uid) == user.id:
                return user
        except Exception:  # noqa: BLE001
            pass

        return self.env["res.users"]

    @api.model
    @staticmethod
    def _sanitize_profile_vals(profile_vals):
        return {
            "telegram_username": (profile_vals.get("username") or "").strip() or False,
            "telegram_first_name": (profile_vals.get("first_name") or "").strip() or False,
            "telegram_last_name": (profile_vals.get("last_name") or "").strip() or False,
            "telegram_phone": (profile_vals.get("phone") or "").strip() or False,
            "telegram_language_code": (profile_vals.get("language_code") or "").strip() or False,
        }

    @api.model
    def _get_or_create_link(self, telegram_user_id, telegram_chat_id, profile_vals=None):
        link = self.sudo().search([("telegram_user_id", "=", telegram_user_id)], limit=1)
        profile_clean = self._sanitize_profile_vals(profile_vals or {})
        if not link:
            create_vals = {
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": telegram_chat_id or False,
            }
            create_vals.update(profile_clean)
            return self.sudo().create(
                {
                    **create_vals,
                }
            )

        write_vals = {}
        if telegram_chat_id and link.telegram_chat_id != telegram_chat_id:
            write_vals["telegram_chat_id"] = telegram_chat_id
        for key, value in profile_clean.items():
            if value and link[key] != value:
                write_vals[key] = value
        if write_vals:
            link.write(write_vals)
        return link

    def _sync_password_state(self):
        # Password changes must not modify Telegram link state.
        if len(self) == 1 and self.status == "stale" and self.user_id:
            self.write(
                {
                    "status": "linked",
                    "pending_action": False,
                    "pending_email": False,
                    "last_error": False,
                }
            )
        return

    def _build_menu_text(self):
        self.ensure_one()
        if self._is_link_active():
            return (
                "Telegram account is linked.\n"
                f"Odoo user: {self.user_id.login}\n"
                "Use menu options below (User Settings, AI Session)."
            )
        return "Welcome. Use User Settings to link your Odoo account or manage PIN."

    def _build_user_settings_menu_text(self):
        self.ensure_one()
        if self._is_link_active():
            return (
                "User Settings\n"
                f"Linked Odoo user: {self.user_id.login}\n"
                "Choose an option below."
            )
        return (
            "User Settings\n"
            "Your account is not linked.\n"
            "Choose an option below."
        )

    def _build_ai_session_menu_text(self):
        self.ensure_one()
        return (
            "AI Session Menu\n"
            "- Status: show consumed/remaining tokens\n"
            "- New Session: start a fresh AI context"
        )

    def _handle_ai_status_request(self):
        self.ensure_one()
        self._sync_password_state()
        if not self._is_link_active():
            return self._payload(
                "Your account is not linked yet. Select \"Link Odoo Account\" first.",
                note="not_linked",
                keyboard_rows=self._session_keyboard_rows(),
            )

        session = self._active_ai_session()
        token_limit = int(self.ai_context_token_limit or 1000)
        token_count = 0
        if session:
            token_limit = int(session.token_limit or token_limit)
            token_count = int(session.token_count or 0)

        remain = max(token_limit - token_count, 0)
        return self._payload(
            f"Token usage: {token_count}/{token_limit}\nRemain: {remain}",
            note="ai_status_sent",
            keyboard_rows=self._session_keyboard_rows(),
        )

    def _handle_new_session_request(self):
        self.ensure_one()
        self._sync_password_state()
        if not self._is_link_active():
            return self._payload(
                "Your account is not linked yet. Select \"Link Odoo Account\" first.",
                note="not_linked",
                keyboard_rows=self._session_keyboard_rows(),
            )

        active = self._active_ai_session()
        if active:
            active.write(
                {
                    "session_status": "closed",
                    "close_reason": "manual_new_session",
                    "processing_note": "ai_session_closed_manually",
                }
            )

        self._open_ai_session()
        return self._payload(
            "Started a new AI session. Previous context will not be used.",
            note="ai_new_session_opened",
            keyboard_rows=self._session_keyboard_rows(),
        )

    def _start_link_flow(self):
        self.ensure_one()
        self.write(
            {
                "status": "awaiting_email",
                "pending_action": "link",
                "pending_email": False,
                "last_error": False,
            }
        )
        return self._payload(
            "Send your Odoo email/login.",
            note="awaiting_email",
            keyboard_rows=self._cancel_keyboard_rows(),
        )

    def _start_unlink_flow(self):
        self.ensure_one()
        self._sync_password_state()
        if not self._is_link_active():
            return self._payload(
                "Your account is not linked yet.",
                note="not_linked",
                keyboard_rows=self._user_settings_keyboard_rows(),
            )

        self.write(
            {
                "status": "awaiting_email",
                "pending_action": "unlink",
                "pending_email": False,
                "last_error": False,
            }
        )
        return self._payload(
            "To unlink, send your Odoo email/login.",
            note="awaiting_email",
            keyboard_rows=self._cancel_keyboard_rows(),
        )

    def _handle_pin_request(self):
        self.ensure_one()
        self._sync_password_state()
        if self._is_link_active():
            self.write({"last_verified_at": fields.Datetime.now()})
            return self._payload(
                f"Your 4-digit PIN is: {self.pin}",
                note="pin_sent",
                keyboard_rows=self._user_settings_keyboard_rows(),
            )

        return self._payload(
            "Your account is not linked yet. Select \"Link Odoo Account\" first.",
            note="not_linked",
            keyboard_rows=self._user_settings_keyboard_rows(),
        )

    def _handle_email_input(self, text):
        self.ensure_one()
        action = self.pending_action or "link"
        email_or_login = (text or "").strip()
        if not email_or_login:
            return self._payload(
                "Invalid email/login. Please send a valid value.",
                note="awaiting_email",
                keyboard_rows=self._cancel_keyboard_rows(),
            )

        if action == "unlink" and (self.status != "awaiting_email" or not self.user_id):
            return self._payload(
                "Your account is not linked yet.",
                note="not_linked",
                keyboard_rows=self._user_settings_keyboard_rows(),
            )

        self.write(
            {
                "pending_email": email_or_login,
                "status": "awaiting_password",
                "last_error": False,
            }
        )
        return self._payload(
            "Email/login received. Now send your password or API key.",
            note="awaiting_secret",
            keyboard_rows=self._cancel_keyboard_rows(),
        )

    def _close_open_ai_sessions(self, linked_user_id):
        self.ensure_one()
        if not linked_user_id:
            return
        Chat = self.env["ab_telegram_chat_message"].sudo()
        sessions = Chat.search(
            [
                ("telegram_user_id", "=", self.telegram_user_id),
                ("linked_user_id", "=", linked_user_id),
                ("session_status", "=", "open"),
            ]
        )
        if sessions:
            sessions.write(
                {
                    "session_status": "closed",
                    "close_reason": "manual_unlink",
                    "processing_note": "ai_session_closed_by_unlink",
                }
            )

    def _handle_password_input(self, text, telegram_chat_id):
        self.ensure_one()
        action = self.pending_action or "link"
        secret = text or ""
        email_or_login = (self.pending_email or "").strip()
        if not email_or_login:
            self.write({"status": "awaiting_email", "pending_action": action})
            return self._payload(
                "Email/login is missing. Send your Odoo email/login.",
                note="awaiting_email",
                keyboard_rows=self._cancel_keyboard_rows(),
            )

        user = self._validate_credentials(email_or_login, secret)
        if not user:
            self.write(
                {
                    "status": "awaiting_email",
                    "pending_action": action,
                    "pending_email": False,
                    "last_error": "invalid_credentials",
                }
            )
            return self._payload(
                "Invalid credentials. Send your email/login again.",
                note="invalid_credentials",
                keyboard_rows=self._cancel_keyboard_rows(),
            )

        if action == "unlink":
            if self.status not in {"awaiting_password", "awaiting_email", "linked", "stale"} or not self.user_id:
                self.write(
                    {
                        "status": "new",
                        "pending_action": False,
                        "pending_email": False,
                    }
                )
                return self._payload(
                    "Your account is not linked.",
                    note="not_linked",
                    keyboard_rows=self._user_settings_keyboard_rows(),
                )

            if user != self.user_id:
                self.write(
                    {
                        "status": "awaiting_email",
                        "pending_action": "unlink",
                        "pending_email": False,
                        "last_error": "unlink_user_mismatch",
                    }
                )
                return self._payload(
                    "Credentials must match the currently linked Odoo user. Send login again.",
                    note="invalid_credentials",
                    keyboard_rows=self._cancel_keyboard_rows(),
                )

            linked_user_id = self.user_id.id
            self._close_open_ai_sessions(linked_user_id)
            self.write(
                {
                    "status": "new",
                    "pending_action": False,
                    "pending_email": False,
                    "user_id": False,
                    "login_email": False,
                    "linked_at": False,
                    "last_verified_at": fields.Datetime.now(),
                    "last_error": False,
                }
            )
            return self._payload(
                "Unlinked successfully.",
                note="unlink_success",
                keyboard_rows=self._user_settings_keyboard_rows(),
            )

        existing_other_link = self.sudo().search(
            [("user_id", "=", user.id), ("id", "!=", self.id)],
            limit=1,
        )
        if existing_other_link:
            self.write(
                {
                    "status": "awaiting_email",
                    "pending_action": "link",
                    "pending_email": False,
                    "last_error": "user_already_linked",
                }
            )
            return self._payload(
                "This Odoo user is already linked to another Telegram account.",
                note="user_already_linked",
                keyboard_rows=self._cancel_keyboard_rows(),
            )

        was_linked = bool(self.linked_at)
        vals = {
            "status": "linked",
            "pending_action": False,
            "user_id": user.id,
            "login_email": user.login,
            "pending_email": False,
            "last_error": False,
            "last_verified_at": fields.Datetime.now(),
            "telegram_chat_id": telegram_chat_id or self.telegram_chat_id,
        }
        if not self.linked_at:
            vals["linked_at"] = fields.Datetime.now()
        if not self.pin:
            vals["pin"] = self._generate_pin()
            vals["pin_generated_at"] = fields.Datetime.now()

        self.write(vals)
        if was_linked:
            message = f"Relinked successfully. Your PIN is: {self.pin}"
        else:
            message = f"Linked successfully. Your PIN is: {self.pin}"

        return self._payload(message, note="linked_success", keyboard_rows=self._user_settings_keyboard_rows())

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
    ):
        telegram_user_id = str(telegram_user_id or "").strip()
        telegram_chat_id = str(telegram_chat_id or "").strip()
        text = (text or "").strip()
        if not telegram_user_id:
            return {"handled": False}

        link = self._get_or_create_link(
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            profile_vals={
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
                "language_code": language_code,
            },
        )
        link._sync_password_state()
        normalized = self._normalize_text(text)

        if normalized in {"cancel", "/cancel"}:
            if link.status not in {"awaiting_email", "awaiting_password"}:
                return self._payload(link._build_menu_text(), note="menu_sent")

            status_after_cancel = "linked" if link.user_id else "new"
            link.write(
                {
                    "status": status_after_cancel,
                    "pending_action": False,
                    "pending_email": False,
                    "last_error": False,
                }
            )
            keyboard = link._user_settings_keyboard_rows() if status_after_cancel == "linked" else None
            return self._payload("Cancelled.", note="flow_cancelled", keyboard_rows=keyboard)

        if link.status == "awaiting_email":
            return link._handle_email_input(text)
        if link.status == "awaiting_password":
            return link._handle_password_input(text, telegram_chat_id)

        if normalized in {"start", "/start", "menu", "/menu"}:
            return self._payload(link._build_menu_text(), note="menu_sent")

        if normalized in {"help", "/help"}:
            return self._payload(
                (
                    "Commands:\n"
                    "- Get My ID: show Telegram user ID\n"
                    "- User Settings: open account settings menu\n"
                    "- Link Odoo Account: link with login + password/API key\n"
                    "- Unlink Odoo Account: unlink after credentials check\n"
                    "- My PIN: show your 4-digit PIN (inside User Settings)\n"
                    "- AI Session: open session submenu\n"
                    "- Status: show token usage for current AI session\n"
                    "- New Session: start fresh AI context\n"
                    "- After linking, send any data question (example: list 5 employees from ab_hr_employee)"
                ),
                note="help_sent",
            )

        if normalized in {"id", "/id", "my id", "get my id", "user id", "userid"}:
            return self._payload(f"Your Telegram user ID is: {telegram_user_id}", note="user_id_sent")

        if normalized in {"user settings", "settings", "/settings", "account settings"}:
            return self._payload(
                link._build_user_settings_menu_text(),
                note="user_settings_menu_sent",
                keyboard_rows=link._user_settings_keyboard_rows(),
            )

        if normalized in {"pin", "/pin", "my pin", "get my pin"}:
            return link._handle_pin_request()

        if normalized in {"ai session", "session", "session menu", "/session"}:
            return self._payload(
                link._build_ai_session_menu_text(),
                note="ai_session_menu_sent",
                keyboard_rows=link._session_keyboard_rows(),
            )

        if normalized in {"status", "/status", "session status", "ai status"}:
            return link._handle_ai_status_request()

        if normalized in {"new session", "/newsession", "/new_session", "start new session"}:
            return link._handle_new_session_request()

        if normalized in {"back", "/back"}:
            return self._payload(link._build_menu_text(), note="menu_sent")

        if normalized in {
            "link odoo account",
            "link account",
            "link",
            "/link",
            "relink",
            "/relink",
        }:
            return link._start_link_flow()

        if normalized in {
            "unlink odoo account",
            "unlink account",
            "unlink",
            "/unlink",
        }:
            return link._start_unlink_flow()

        if link._is_link_active():
            return link._ai_answer_for_prompt(text)

        return self._payload(link._build_menu_text(), note="menu_sent")
