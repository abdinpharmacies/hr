import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape
from odoo.tools.translate import _


class AbSeoAssistant(models.Model):
    _name = "ab.seo.assistant"
    _description = "SEO Assistant Configuration"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    provider = fields.Selection(
        [
            ("google_gemini", "Google Gemini"),
            ("groq", "Groq"),
            ("openrouter", "OpenRouter"),
            ("huggingface", "Hugging Face"),
            ("alibaba_qwen", "Alibaba Qwen"),
            ("ready_api", "Ready API"),
            ("openfda", "openFDA"),
            ("openfda_cosmetic_event", "openFDA Cosmetic Event"),
            ("openai", "OpenAI"),
            ("other", "Other"),
        ],
        required=True,
        default="google_gemini",
    )
    assistant_type = fields.Selection(
        [
            ("ai", "AI Assistant"),
            ("data_source", "Data Source"),
        ],
        required=True,
        default="ai",
        index=True,
    )
    model_name = fields.Char(required=True, default="gemini-3.5-flash")
    base_url = fields.Char()
    api_key = fields.Char(groups="ab_website_seo_optimization.group_ab_website_seo_optimization_manager")
    api_key_name = fields.Char(
        string="API Key Label",
        help="Reference name for the expected key, for example GOOGLE_API_KEY. Do not store real keys in source code.",
    )
    endpoint_path = fields.Char(default="/chat/completions")
    free_tier = fields.Boolean(default=True)
    daily_limit = fields.Integer(default=300)
    daily_token_limit = fields.Integer(
        string="Daily Token Limit",
        help="Optional daily token cap for AI assistants. Leave zero when the provider does not expose or enforce a token limit.",
    )
    used_today = fields.Integer(readonly=True)
    prompt_tokens_today = fields.Integer(readonly=True)
    completion_tokens_today = fields.Integer(readonly=True)
    total_tokens_today = fields.Integer(readonly=True)
    lifetime_prompt_tokens = fields.Integer(readonly=True)
    lifetime_completion_tokens = fields.Integer(readonly=True)
    lifetime_total_tokens = fields.Integer(readonly=True)
    last_prompt_tokens = fields.Integer(readonly=True)
    last_completion_tokens = fields.Integer(readonly=True)
    last_total_tokens = fields.Integer(readonly=True)
    last_token_usage_at = fields.Datetime(readonly=True)
    last_used_date = fields.Date(readonly=True)
    temperature = fields.Float(default=0.2)
    max_output_tokens = fields.Integer(default=800)
    test_status = fields.Selection(
        [
            ("not_tested", "Not Tested"),
            ("ready", "Ready"),
            ("missing_key", "Missing Key"),
            ("misconfigured", "Misconfigured"),
        ],
        default="not_tested",
        readonly=True,
    )
    last_test_at = fields.Datetime(readonly=True)
    last_test_message = fields.Text(readonly=True)
    notes = fields.Text()

    @api.model
    def _provider_defaults(self):
        return {
            "google_gemini": {
                "assistant_type": "ai",
                "model_name": "gemini-3.5-flash",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "endpoint_path": "/models/{model}:generateContent",
                "api_key_name": "GOOGLE_API_KEY",
                "daily_limit": 300,
                "notes": _(
                    "Recommended first free-tier candidate for Arabic and English SEO drafts. "
                    "Enter a Google AI Studio API key before enabling live generation."
                ),
            },
            "groq": {
                "assistant_type": "ai",
                "model_name": "llama-3.1-8b-instant",
                "base_url": "https://api.groq.com/openai/v1",
                "endpoint_path": "/chat/completions",
                "api_key_name": "GROQ_API_KEY",
                "daily_limit": 1000,
                "notes": _(
                    "Fast OpenAI-compatible endpoint. Good for low-cost draft generation and batch testing."
                ),
            },
            "openrouter": {
                "assistant_type": "ai",
                "model_name": "nex-agi/nex-n2-pro:free",
                "base_url": "https://openrouter.ai/api/v1",
                "endpoint_path": "/chat/completions",
                "api_key_name": "OPENROUTER_API_KEY",
                "daily_limit": 300,
                "notes": _(
                    "Router for free or low-cost models. Confirm the selected :free model is still available before production use."
                ),
            },
            "huggingface": {
                "assistant_type": "ai",
                "model_name": "meta-llama/Llama-3.1-8B-Instruct",
                "base_url": "https://api-inference.huggingface.co/models",
                "endpoint_path": "/{model}",
                "api_key_name": "HF_TOKEN",
                "daily_limit": 300,
                "notes": _(
                    "Useful for experiments with hosted open models. Availability depends on Hugging Face provider limits."
                ),
            },
            "alibaba_qwen": {
                "assistant_type": "ai",
                "model_name": "Qwen",
                "base_url": "https://ws-eish2a8n2iixd1b3.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
                "endpoint_path": "/chat/completions",
                "api_key_name": "ALIBABA_QWEN_API_KEY",
                "daily_limit": 300,
                "notes": _(
                    "Alibaba Model Studio workspace endpoint for the Singapore international deployment scope. "
                    "Uses the OpenAI-compatible chat completions API."
                ),
            },
            "ready_api": {
                "assistant_type": "data_source",
                "model_name": "ready-api",
                "base_url": "https://ready-api.vercel.app",
                "endpoint_path": "/api/drugs-eg",
                "api_key_name": "READY_API_KEY",
                "daily_limit": 300,
                "notes": _(
                    "Pharmaceutical enrichment only. Keep cached, rate-limited, manually controlled, and never source of truth."
                ),
            },
            "openfda": {
                "assistant_type": "data_source",
                "model_name": "openfda-drug-label",
                "base_url": "https://api.fda.gov",
                "endpoint_path": "/drug/label.json",
                "api_key_name": "OPENFDA_API_KEY",
                "daily_limit": 120000,
                "notes": _(
                    "openFDA drug label source. API key is passed as api_key query parameter. "
                    "Use for OTC/Rx label enrichment only, not as product source of truth."
                ),
            },
            "openfda_cosmetic_event": {
                "assistant_type": "data_source",
                "model_name": "openfda-cosmetic-event",
                "base_url": "https://api.fda.gov",
                "endpoint_path": "/cosmetic/event.json",
                "api_key_name": "OPENFDA_API_KEY",
                "daily_limit": 120000,
                "notes": _(
                    "openFDA cosmetic adverse-event reports. Use only for safety signal context. "
                    "Falls back to /home/abdin_04/Downloads/cosmetic-event-0001-of-0001.json when the API is unavailable."
                ),
            },
            "openai": {
                "assistant_type": "ai",
                "model_name": "gpt-4.1-mini",
                "base_url": "https://api.openai.com/v1",
                "endpoint_path": "/chat/completions",
                "api_key_name": "OPENAI_API_KEY",
                "daily_limit": 300,
                "notes": _("Paid/freemium fallback. Do not auto-publish generated medical content."),
            },
        }

    @api.onchange("provider")
    def _onchange_provider(self):
        for assistant in self:
            assistant._apply_provider_defaults(overwrite_notes=False)

    def _apply_provider_defaults(self, overwrite_notes=True):
        defaults_by_provider = self._provider_defaults()
        for assistant in self:
            defaults = defaults_by_provider.get(assistant.provider)
            if not defaults:
                continue
            values = {
                "assistant_type": defaults["assistant_type"],
                "model_name": defaults["model_name"],
                "base_url": defaults["base_url"],
                "endpoint_path": defaults["endpoint_path"],
                "api_key_name": defaults["api_key_name"],
                "daily_limit": defaults["daily_limit"],
            }
            if overwrite_notes or not assistant.notes:
                values["notes"] = defaults["notes"]
            assistant.update(values)

    def action_apply_provider_defaults(self):
        self._apply_provider_defaults()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Assistant Defaults Updated"),
                "message": _("Provider model, endpoint, key label, and limits were refreshed."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_test_configuration(self):
        for assistant in self:
            status, message = assistant._test_configuration()
            assistant.write({
                "test_status": status,
                "last_test_at": fields.Datetime.now(),
                "last_test_message": message,
            })
        notification_type = "success" if all(rec.test_status == "ready" for rec in self) else "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Assistant Configuration Test"),
                "message": "\n".join(self.mapped("last_test_message")),
                "type": notification_type,
                "sticky": notification_type != "success",
            },
        }

    def _test_configuration(self):
        self.ensure_one()
        defaults = self._provider_defaults().get(self.provider)
        expected_type = defaults and defaults.get("assistant_type")
        if self.provider != "other" and (
            not (self.model_name and self.base_url and self.endpoint_path)
            or (expected_type and self.assistant_type != expected_type)
        ):
            self._apply_provider_defaults(overwrite_notes=False)
        if not self.active:
            return "misconfigured", _("%s is archived.") % self.display_name
        if not self.model_name:
            return "misconfigured", _("%s has no model name.") % self.display_name
        if not self.base_url:
            return "misconfigured", _("%s has no base URL.") % self.display_name
        if not self.endpoint_path:
            return "misconfigured", _("%s has no endpoint path.") % self.display_name
        if not self.api_key:
            return "missing_key", _("%s is configured but no API key is stored.") % self.display_name
        return "ready", _("%s is ready: %s") % (self.display_name, self._get_endpoint_url())

    def _get_endpoint_url(self):
        self.ensure_one()
        base_url = self._normalize_base_url(self.base_url)
        endpoint_path = (self.endpoint_path or "").replace("{model}", self.model_name or "").lstrip("/")
        if self._is_alibaba_maas_url(base_url):
            base_url = self._normalize_alibaba_maas_base_url(base_url)
            if "generateContent" in endpoint_path or endpoint_path.startswith("models/"):
                endpoint_path = "chat/completions"
        return "%s/%s" % (base_url, endpoint_path)

    def _normalize_base_url(self, base_url):
        base_url = (base_url or "").strip().rstrip("/")
        if base_url and not base_url.startswith(("http://", "https://")):
            base_url = "https://%s" % base_url
        return base_url

    def _is_alibaba_maas_url(self, base_url):
        return ".maas.aliyuncs.com" in (base_url or "")

    def _normalize_alibaba_maas_base_url(self, base_url):
        base_url = (base_url or "").rstrip("/")
        if "/compatible-mode/" not in base_url:
            base_url = "%s/compatible-mode/v1" % base_url
        return base_url

    def _get_local_data_source_path(self):
        self.ensure_one()
        base_path = Path(self.base_url or "")
        endpoint_path = (self.endpoint_path or "").lstrip("/")
        return base_path / endpoint_path

    def _get_cosmetic_event_fallback_path(self):
        return Path(
            self.env.context.get("cosmetic_event_fallback_path")
            or "/home/abdin_04/Downloads/cosmetic-event-0001-of-0001.json"
        )

    def generate_product_content(self, product_name, lang_code, product_context=None):
        self.ensure_one()
        self._validate_live_request()
        if self.assistant_type == "data_source":
            result = self._request_data_source_product(product_name)
            token_usage = {}
        else:
            result, token_usage = self._request_ai_product(product_name, lang_code, product_context=product_context)
        self._increment_usage(token_usage=token_usage)
        return result

    def generate_seo_component_content(self, component_name, lang_code, component_context=None):
        self.ensure_one()
        if self.assistant_type != "ai":
            raise UserError(_("%s is not an AI assistant.") % self.display_name)
        self._validate_live_request()
        result, token_usage = self._request_ai_seo_component(
            component_name,
            lang_code,
            component_context=component_context,
        )
        self._increment_usage(token_usage=token_usage)
        return result

    def _validate_live_request(self):
        self.ensure_one()
        status, message = self._test_configuration()
        if status != "ready":
            raise UserError(message)
        today = fields.Date.context_today(self)
        used_today = self.used_today if self.last_used_date == today else 0
        if self.daily_limit and used_today >= self.daily_limit:
            raise UserError(_("%s reached the daily request limit of %s.") % (self.display_name, self.daily_limit))
        total_tokens_today = self.total_tokens_today if self.last_used_date == today else 0
        if self.assistant_type == "ai" and self.daily_token_limit and total_tokens_today >= self.daily_token_limit:
            raise UserError(_("%s reached the daily token limit of %s.") % (self.display_name, self.daily_token_limit))

    def _increment_usage(self, token_usage=None):
        self.ensure_one()
        today = fields.Date.context_today(self)
        used_today = self.used_today if self.last_used_date == today else 0
        token_usage = token_usage or {}
        prompt_tokens = int(token_usage.get("prompt_tokens") or 0)
        completion_tokens = int(token_usage.get("completion_tokens") or 0)
        total_tokens = int(token_usage.get("total_tokens") or prompt_tokens + completion_tokens or 0)
        prompt_tokens_today = self.prompt_tokens_today if self.last_used_date == today else 0
        completion_tokens_today = self.completion_tokens_today if self.last_used_date == today else 0
        total_tokens_today = self.total_tokens_today if self.last_used_date == today else 0
        values = {
            "used_today": used_today + 1,
            "last_used_date": today,
            "prompt_tokens_today": prompt_tokens_today + prompt_tokens,
            "completion_tokens_today": completion_tokens_today + completion_tokens,
            "total_tokens_today": total_tokens_today + total_tokens,
            "lifetime_prompt_tokens": self.lifetime_prompt_tokens + prompt_tokens,
            "lifetime_completion_tokens": self.lifetime_completion_tokens + completion_tokens,
            "lifetime_total_tokens": self.lifetime_total_tokens + total_tokens,
        }
        if token_usage:
            values.update({
                "last_prompt_tokens": prompt_tokens,
                "last_completion_tokens": completion_tokens,
                "last_total_tokens": total_tokens,
                "last_token_usage_at": fields.Datetime.now(),
            })
        self.write(values)

    def _request_data_source_product(self, product_name):
        self.ensure_one()
        if self.provider == "openfda":
            return self._request_openfda_product(product_name)
        if self.provider == "openfda_cosmetic_event":
            return self._request_cosmetic_event_product(product_name)
        query = {
            "search": product_name or "",
            "limit": 1,
            "page": 1,
        }
        url = "%s?%s" % (self._get_endpoint_url(), urlencode(query))
        response = self._http_json("GET", url)
        item = self._extract_first_data_source_item(response)
        if not item:
            raise UserError(_("No drug data source result was found for %s.") % (product_name or _("the product")))
        return self._normalize_data_source_item(item)

    def _request_openfda_product(self, product_name):
        self.ensure_one()
        searches = [
            'openfda.brand_name:"%s"' % self._escape_openfda_search_value(product_name),
            product_name or "",
        ]
        response = False
        last_error = False
        for search in searches:
            query = [
                ("api_key", self.api_key),
                ("search", search),
                ("limit", 1),
            ]
            url = "%s?%s" % (self._get_endpoint_url(), urlencode(query))
            try:
                response = self._http_json("GET", url)
            except UserError as error:
                last_error = error
                continue
            item = self._extract_first_data_source_item(response)
            if item:
                return self._normalize_openfda_item(item)
        if last_error:
            raise UserError(_("No openFDA label result was found for %(product)s. Last response: %(error)s") % {
                "product": product_name or _("the product"),
                "error": last_error,
            })
        raise UserError(_("No openFDA label result was found for %s.") % (product_name or _("the product")))

    def _escape_openfda_search_value(self, value):
        return str(value or "").replace("\\", "\\\\").replace('"', '\\"').strip()

    def _request_cosmetic_event_product(self, product_name):
        self.ensure_one()
        search_text = self._normalize_match_text(product_name)
        if not search_text:
            raise UserError(_("No product name was provided for cosmetic event search."))
        api_result = self._request_cosmetic_event_api_product(product_name)
        if api_result:
            return api_result
        return self._request_cosmetic_event_file_product(product_name)

    def _request_cosmetic_event_api_product(self, product_name):
        searches = [
            'products.product_name:"%s"' % self._escape_openfda_search_value(product_name),
            product_name or "",
        ]
        for search in searches:
            query = [
                ("api_key", self.api_key),
                ("search", search),
                ("limit", 25),
            ]
            url = "%s?%s" % (self._get_endpoint_url(), urlencode(query))
            try:
                response = self._http_json("GET", url)
            except UserError:
                continue
            events = response.get("results") if isinstance(response, dict) else []
            if events:
                matched_product_name = self._get_first_cosmetic_product_name(events) or product_name
                return self._normalize_cosmetic_event_items(matched_product_name, events)
        return False

    def _request_cosmetic_event_file_product(self, product_name):
        search_text = self._normalize_match_text(product_name)
        path = self._get_cosmetic_event_fallback_path()
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except OSError as error:
            raise UserError(_("%(assistant)s could not read local cosmetic event file: %(error)s") % {
                "assistant": self.display_name,
                "error": error,
            }) from error
        events = payload.get("results") if isinstance(payload, dict) else []
        matched_events = []
        matched_product_name = product_name
        for event in events:
            for product in event.get("products") or []:
                event_product_name = product.get("product_name") or ""
                if self._cosmetic_event_matches(search_text, event_product_name):
                    matched_events.append(event)
                    matched_product_name = event_product_name or matched_product_name
                    break
            if len(matched_events) >= 25:
                break
        if not matched_events:
            raise UserError(_("No FDA cosmetic event report was found for %s.") % product_name)
        return self._normalize_cosmetic_event_items(matched_product_name, matched_events)

    def _get_first_cosmetic_product_name(self, events):
        for event in events:
            products = event.get("products") or []
            for product in products:
                if product.get("product_name"):
                    return product["product_name"]
        return False

    def _normalize_match_text(self, value):
        return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))

    def _cosmetic_event_matches(self, search_text, product_name):
        product_text = self._normalize_match_text(product_name)
        if not product_text:
            return False
        if search_text in product_text or product_text in search_text:
            return True
        search_terms = {term for term in search_text.split() if len(term) > 2}
        product_terms = {term for term in product_text.split() if len(term) > 2}
        if not search_terms:
            return False
        return len(search_terms & product_terms) >= min(2, len(search_terms))

    def _request_ai_product(self, product_name, lang_code, product_context=None):
        self.ensure_one()
        prompt = self._build_ai_product_prompt(product_name, lang_code, product_context=product_context)
        payload = self._build_ai_payload(prompt)
        response = self._http_json("POST", self._get_endpoint_url(), payload=payload)
        content = self._extract_ai_text(response)
        if not content:
            raise UserError(_("%s returned an empty AI response.") % self.display_name)
        return self._parse_ai_content(content, product_name=product_name, lang_code=lang_code), self._extract_token_usage(response)

    def _request_ai_seo_component(self, component_name, lang_code, component_context=None):
        self.ensure_one()
        prompt = self._build_ai_seo_component_prompt(
            component_name,
            lang_code,
            component_context=component_context,
        )
        payload = self._build_ai_payload(prompt)
        response = self._http_json("POST", self._get_endpoint_url(), payload=payload)
        content = self._extract_ai_text(response)
        if not content:
            raise UserError(_("%s returned an empty AI response.") % self.display_name)
        return self._parse_ai_seo_component_content(
            content,
            component_name=component_name,
            lang_code=lang_code,
        ), self._extract_token_usage(response)

    def _build_ai_product_prompt(self, product_name, lang_code, product_context=None):
        language = "Arabic" if lang_code == "ar_001" else "English"
        context_text = json.dumps(
            self._prepare_prompt_context(product_context),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return (
            "Return compact valid JSON only, no markdown. "
            "Task: pharmacy ecommerce SEO and public product reference for drugs, cosmetics, supplements, devices, and other medical products. "
            "Language=%(language)s. Product=%(product_name)s. Context=%(context)s. "
            "Use the exact product name and context first. If the product is not a medicine, do not invent drug claims; write cosmetic/device/supplement-appropriate content. "
            "Avoid diagnosis, cure guarantees, dosage instructions, or unsafe medical claims. Use pharmacist/leaflet wording when uncertain. "
            "Return this schema exactly: "
            "{"
            "\"meta_title\":\"\","
            "\"meta_description\":\"\","
            "\"keywords\":\"\","
            "\"slug\":\"\","
            "\"short_description\":\"\","
            "\"public_description\":\"\","
            "\"active_ingredient\":\"\","
            "\"warnings\":\"\","
            "\"contraindications\":\"\","
            "\"storage\":\"\","
            "\"drug_data\":{"
            "\"scientific_name\":\"\","
            "\"commercial_names\":\"\","
            "\"active_ingredient\":\"\","
            "\"drug_class\":\"medicine|cosmetic|supplement|medical_device|personal_care|other\","
            "\"regulatory_status\":\"\","
            "\"common_uses\":\"\","
            "\"side_effects\":\"\","
            "\"warnings\":\"\","
            "\"pregnancy\":\"\","
            "\"breastfeeding\":\"\","
            "\"storage\":\"\","
            "\"interactions\":\"\","
            "\"source_label\":\"AI generated educational product summary\""
            "}"
            "}. "
            "For cosmetics/devices, use common_uses as product benefits/use cases, side_effects as possible irritation/sensitivity, interactions as compatibility notes."
        ) % {
            "language": language,
            "product_name": product_name or "",
            "context": context_text,
        }

    def _build_ai_seo_component_prompt(self, component_name, lang_code, component_context=None):
        language = "Arabic" if lang_code == "ar_001" else "English"
        context_text = json.dumps(
            self._prepare_prompt_context(component_context),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return (
            "Return compact valid JSON only, no markdown. "
            "Task: generate safe SEO fields for the Odoo Search Engine Optimization popup. "
            "Target component=%(component_name)s. Language=%(language)s. Context=%(context)s. "
            "Use only the supplied page/product context and broadly safe public knowledge. "
            "Do not invent medical claims, ingredient claims, pricing, stock, dosage, or guarantees. "
            "For medicines, use pharmacist/leaflet wording and avoid treatment promises. "
            "For cosmetics, devices, supplements, and personal-care products, describe product type and general benefits only when supported by context. "
            "This is NOT the product description generator. "
            "Never return meta_title, meta_description, short_description, public_description, active_ingredient, warnings, storage, or drug_data. "
            "Return this schema exactly: "
            "{"
            "\"title\":\"\","
            "\"description\":\"\","
            "\"keywords\":[\"\"],"
            "\"slug\":\"\""
            "}. "
            "Do not put JSON text inside any field. "
            "Description must be one plain meta-description sentence, not a formatted product overview and not bullet points. "
            "Ignore stock quantity, price, shipping, cart, and terms text from the page body. "
            "Title max 70 characters. Description 50-160 characters. Keywords max 7 concise phrases. Slug lowercase URL text without the database id."
        ) % {
            "component_name": component_name or "",
            "language": language,
            "context": context_text,
        }

    def _prepare_prompt_context(self, product_context):
        compact = {}
        for key, value in (product_context or {}).items():
            if value in (None, False, "", 0):
                continue
            text = str(value).strip()
            if key in ("notes", "group_path") and len(text) > 300:
                text = text[:300]
            elif len(text) > 160:
                text = text[:160]
            compact[key] = text
        return compact

    def _build_ai_payload(self, prompt):
        self.ensure_one()
        if self.provider == "google_gemini":
            return {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": self.max_output_tokens,
                    "responseMimeType": "application/json",
                },
            }
        if self.provider == "huggingface":
            return {
                "inputs": prompt,
                "parameters": {
                    "temperature": self.temperature,
                    "max_new_tokens": self.max_output_tokens,
                    "return_full_text": False,
                },
            }
        return {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "Return strict JSON only. Do not include markdown fences.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
        }

    def _http_json(self, method, url, payload=None):
        headers = {
            "Accept": "application/json",
            "User-Agent": "ab-website-seo-optimization/19.0",
        }
        if self.api_key and self.provider == "google_gemini":
            headers["x-goog-api-key"] = self.api_key
        elif self.api_key and self.provider not in ("openfda", "openfda_cosmetic_event"):
            headers["Authorization"] = "Bearer %s" % self.api_key
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=8) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            raise UserError(self._format_http_error(error)) from error
        except URLError as error:
            raise UserError(_("Could not connect to %s: %s") % (self.display_name, error.reason)) from error
        except ValueError as error:
            raise UserError(_("%(assistant)s has an invalid endpoint URL: %(url)s. Check that the base URL starts with https://.") % {
                "assistant": self.display_name,
                "url": url,
            }) from error
        except TimeoutError as error:
            raise UserError(_("%s request timed out.") % self.display_name) from error
        try:
            return json.loads(body or "{}")
        except json.JSONDecodeError as error:
            raise UserError(_("%s returned invalid JSON.") % self.display_name) from error

    def _format_http_error(self, error):
        detail = self._get_http_error_detail(error)
        if error.code == 401:
            return _("%s rejected the API key. Check the Authorization bearer token.%s") % (
                self.display_name,
                detail,
            )
        if error.code == 404:
            if self.provider == "openrouter":
                return _(
                    "%(assistant)s returned 404 from OpenRouter. Check that model '%(model)s' is still available and routed, and verify the endpoint path.%(detail)s"
                ) % {
                    "assistant": self.display_name,
                    "model": self.model_name,
                    "detail": detail,
                }
            return _("%s endpoint was not found. Check base URL and endpoint path.%s") % (
                self.display_name,
                detail,
            )
        if error.code == 429:
            return _("%s rate limit was exceeded. Reduce batch size or wait for quota reset.%s") % (
                self.display_name,
                detail,
            )
        return _("%(assistant)s returned HTTP %(code)s: %(reason)s") % {
            "assistant": self.display_name,
            "code": error.code,
            "reason": "%s%s" % (error.reason, detail),
        }

    def _get_http_error_detail(self, error):
        try:
            body = error.read().decode("utf-8")
        except Exception:
            body = ""
        body = (body or "").strip()
        if not body:
            return ""
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return " Details: %s" % body[:500]
        message = data.get("message")
        if not message and isinstance(data.get("error"), dict):
            message = data["error"].get("message") or data["error"].get("code")
        if not message:
            message = body
        return " Details: %s" % str(message)[:500]

    def _extract_ai_text(self, response):
        self.ensure_one()
        if isinstance(response, list) and response:
            first = response[0]
            if isinstance(first, dict):
                return first.get("generated_text") or first.get("summary_text") or ""
        candidates = response.get("candidates") if isinstance(response, dict) else False
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            return "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
        choices = response.get("choices") if isinstance(response, dict) else False
        if choices:
            message = choices[0].get("message", {})
            return message.get("content") or choices[0].get("text") or ""
        return response.get("content", "") if isinstance(response, dict) else ""

    def _extract_token_usage(self, response):
        if not isinstance(response, dict):
            return {}
        usage = response.get("usage") or response.get("usage_metadata") or response.get("usageMetadata") or {}
        if not isinstance(usage, dict):
            return {}
        prompt_tokens = self._first_int(
            usage,
            "prompt_tokens",
            "promptTokens",
            "input_tokens",
            "inputTokens",
            "promptTokenCount",
        )
        completion_tokens = self._first_int(
            usage,
            "completion_tokens",
            "completionTokens",
            "output_tokens",
            "outputTokens",
            "candidatesTokenCount",
        )
        total_tokens = self._first_int(
            usage,
            "total_tokens",
            "totalTokens",
            "totalTokenCount",
        )
        if not total_tokens:
            total_tokens = prompt_tokens + completion_tokens
        if not any((prompt_tokens, completion_tokens, total_tokens)):
            return {}
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def _parse_ai_content(self, content, product_name=False, lang_code=False):
        clean_content = self._extract_json_text(content)
        data = self._loads_ai_json(clean_content)
        if isinstance(data, str):
            data = self._loads_ai_json(data)
        if isinstance(data, list):
            data = next((item for item in data if isinstance(item, dict)), {})
        if not isinstance(data, dict) or not data:
            data = self._fallback_content_from_text(content, product_name=product_name, lang_code=lang_code)
        normalized = self._normalize_generated_content(data, source_type="assistant")
        return self._ensure_product_content_minimums(
            normalized,
            product_name=product_name,
            lang_code=lang_code,
            raw_content=content,
        )

    def _parse_ai_seo_component_content(self, content, component_name=False, lang_code=False):
        data = self._extract_first_ai_dict(content)
        data = self._unwrap_json_field_payload(data)
        if not isinstance(data, dict) or not data:
            data = self._extract_seo_component_fields_from_text(content)
        keywords = self._first_value(data, "keywords", "keyword_text")
        if isinstance(data.get("keywords"), list):
            keywords = ", ".join(str(keyword) for keyword in data["keywords"] if keyword)
        title = self._clean_seo_component_text(self._first_value(data, "title", "meta_title")) or component_name
        description = self._clean_seo_component_text(self._first_value(data, "description", "meta_description", "short_description"))
        if not description:
            description = self._build_default_seo_component_description(title, lang_code)
        return {
            "title": (title or "")[:70],
            "description": (description or "")[:160],
            "keywords": self._split_keywords(keywords),
            "slug": self._clean_seo_component_text(self._first_value(data, "slug", "seo_name")) or component_name or "",
            "assistant_id": self.id,
            "assistant_name": self.display_name,
        }

    def _extract_seo_component_fields_from_text(self, content):
        text = self._strip_ai_formatting(content)
        return {
            "title": self._extract_json_string_field(text, "title") or self._extract_json_string_field(text, "meta_title"),
            "description": (
                self._extract_json_string_field(text, "description")
                or self._extract_json_string_field(text, "meta_description")
                or self._extract_json_string_field(text, "short_description")
            ),
            "keywords": self._extract_json_list_or_string_field(text, "keywords"),
            "slug": self._extract_json_string_field(text, "slug") or self._extract_json_string_field(text, "seo_name"),
        }

    def _extract_json_string_field(self, text, field_name):
        pattern = r'"%s"\s*:\s*"((?:\\.|[^"\\])*)"' % re.escape(field_name)
        match = re.search(pattern, text or "", flags=re.DOTALL)
        if not match:
            return False
        value = match.group(1)
        try:
            return json.loads('"%s"' % value)
        except json.JSONDecodeError:
            return value.replace('\\"', '"').replace("\\n", " ").strip()

    def _extract_json_list_or_string_field(self, text, field_name):
        string_value = self._extract_json_string_field(text, field_name)
        if string_value:
            return string_value
        pattern = r'"%s"\s*:\s*\[(.*?)\]' % re.escape(field_name)
        match = re.search(pattern, text or "", flags=re.DOTALL)
        if not match:
            return False
        values = re.findall(r'"((?:\\.|[^"\\])*)"', match.group(1))
        return ", ".join(value.replace('\\"', '"') for value in values if value)

    def _build_default_seo_component_description(self, title, lang_code=False):
        return _("Shop %(product)s from Abdin Pharmacies with clear and updated product information.") % {
            "product": title or _("this product"),
        }

    def _extract_first_ai_dict(self, content):
        values = [self._strip_ai_formatting(content), self._extract_json_text(content)]
        for value in values:
            data = self._loads_ai_json(value)
            for _index in range(3):
                if isinstance(data, str):
                    data = self._loads_ai_json(data)
                    continue
                if isinstance(data, list):
                    data = next((item for item in data if isinstance(item, dict)), {})
                if isinstance(data, dict):
                    return data
                break
        text = self._strip_ai_formatting(content)
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                data, _end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
        return {}

    def _unwrap_json_field_payload(self, data):
        if not isinstance(data, dict):
            return data
        for key in ("title", "description", "meta_title", "meta_description"):
            value = data.get(key)
            if not isinstance(value, str):
                continue
            nested = self._extract_first_ai_dict(value)
            if isinstance(nested, dict) and nested:
                merged = dict(data)
                merged.update({nested_key: nested_value for nested_key, nested_value in nested.items() if nested_value not in (None, False, "", [])})
                return merged
        return data

    def _clean_seo_component_text(self, value):
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            return ""
        nested = self._loads_ai_json(self._extract_json_text(text))
        if isinstance(nested, dict) and nested:
            return self._clean_seo_component_text(
                nested.get("description")
                or nested.get("meta_description")
                or nested.get("title")
                or nested.get("meta_title")
            )
        text = re.sub(r"^```(?:json)?|```$", "", text).strip()
        if text.startswith("{") or text.startswith("["):
            return ""
        return text

    def _split_keywords(self, keywords):
        if isinstance(keywords, (list, tuple)):
            values = keywords
        else:
            values = str(keywords or "").split(",")
        clean_values = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in clean_values:
                clean_values.append(text[:60])
            if len(clean_values) >= 7:
                break
        return clean_values

    def _loads_ai_json(self, content):
        try:
            return json.loads(content or "")
        except (TypeError, json.JSONDecodeError):
            pass
        repaired = self._repair_json_text(content)
        if repaired != content:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        return {}

    def _repair_json_text(self, content):
        text = (content or "").strip()
        text = re.sub(r",(\s*[}\]])", r"\1", text)
        return text

    def _fallback_content_from_text(self, content, product_name=False, lang_code=False):
        clean_text = self._strip_ai_formatting(content)
        compact_text = re.sub(r"\s+", " ", clean_text).strip()
        if not compact_text:
            compact_text = product_name or _("Product information is available from Abdin Pharmacies.")
        title = product_name or self._first_sentence(compact_text, max_length=70)
        description = self._first_sentence(compact_text, max_length=255)
        public_description = "<p>%s</p>" % html_escape(compact_text[:1200])
        source_label = _("AI generated educational product summary")
        return {
            "meta_title": title,
            "meta_description": description,
            "keyword_text": ", ".join(part for part in [product_name, self.display_name] if part),
            "seo_name": product_name or title,
            "short_description": description,
            "public_description": public_description,
            "content_source": "assistant",
            "source_summary": _("%s returned non-JSON content; safe SEO fallback was generated.") % self.display_name,
            "drug_data": {
                "commercial_names": product_name or title,
                "common_uses": description,
                "warnings": _("Review the product leaflet and ask a pharmacist before use."),
                "storage": _("Follow the storage instructions on the package or leaflet."),
                "source_label": source_label,
                "source_type": "assistant",
            },
        }

    def _strip_ai_formatting(self, content):
        text = (content or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
        return text

    def _first_sentence(self, text, max_length=160):
        clean_text = re.sub(r"\s+", " ", text or "").strip()
        if not clean_text:
            return ""
        sentence_end = re.search(r"(?<=[.!؟。])\s", clean_text)
        sentence = clean_text[:sentence_end.start()].strip() if sentence_end else clean_text
        return sentence[:max_length].strip()

    def _extract_json_text(self, content):
        clean_content = self._strip_ai_formatting(content)
        if clean_content.startswith("{") and clean_content.endswith("}"):
            return clean_content
        if clean_content.startswith("[") and clean_content.endswith("]"):
            return clean_content
        start = clean_content.find("{")
        end = clean_content.rfind("}")
        if start != -1 and end > start:
            return clean_content[start:end + 1]
        return clean_content

    def _extract_first_data_source_item(self, response):
        if isinstance(response, list):
            return response[0] if response else False
        if not isinstance(response, dict):
            return False
        for key in ("data", "items", "results", "drugs", "products"):
            values = response.get(key)
            if isinstance(values, list) and values:
                return values[0]
        return response if response else False

    def _normalize_data_source_item(self, item):
        data = self._normalize_generated_content(item, source_type="drugs_eg")
        data["source_url"] = self._get_endpoint_url()
        data["source_label"] = data.get("source_label") or _("Ready API Drugs Egypt")
        return data

    def _normalize_openfda_item(self, item):
        get = self._first_value
        openfda = item.get("openfda") if isinstance(item.get("openfda"), dict) else {}
        brand_name = get(openfda, "brand_name") or get(item, "brand_name")
        generic_name = get(openfda, "generic_name", "substance_name") or get(item, "generic_name")
        manufacturer = get(openfda, "manufacturer_name", "labeler_name") or get(item, "manufacturer")
        active_ingredient = get(item, "active_ingredient", "active_ingredients") or generic_name
        inactive_ingredients = get(item, "inactive_ingredient", "inactive_ingredients")
        common_uses = get(item, "indications_and_usage", "purpose")
        warnings = " ".join(part for part in [
            get(item, "warnings"),
            get(item, "do_not_use"),
            get(item, "ask_doctor"),
            get(item, "ask_doctor_or_pharmacist"),
            get(item, "stop_use"),
        ] if part)
        storage = get(item, "storage_and_handling")
        interactions = get(item, "drug_interactions")
        side_effects = get(item, "adverse_reactions")
        pregnancy = get(item, "pregnancy", "pregnancy_or_breast_feeding")
        route = get(openfda, "route")
        product_type = get(openfda, "product_type")
        description = common_uses or get(item, "description") or get(item, "spl_product_data_elements")
        public_parts = [
            description,
            _("Active ingredient: %s") % active_ingredient if active_ingredient else "",
            _("Inactive ingredients: %s") % inactive_ingredients if inactive_ingredients else "",
            _("Warnings: %s") % warnings if warnings else "",
            _("Storage: %s") % storage if storage else "",
        ]
        data = {
            "name": brand_name,
            "scientific_name": generic_name,
            "manufacturer": manufacturer,
            "drug_class": product_type,
            "description": description,
            "keywords": ", ".join(part for part in [brand_name, generic_name, manufacturer, product_type, route] if part),
            "public_description": self._html_paragraph("\n".join(part for part in public_parts if part)),
            "active_ingredient": active_ingredient,
            "warnings": warnings,
            "storage": storage,
            "source_summary": _("Generated from openFDA drug label data."),
            "drug_data": {
                "scientific_name": generic_name,
                "commercial_names": brand_name,
                "active_ingredient": active_ingredient,
                "drug_class": product_type,
                "regulatory_status": get(openfda, "product_type"),
                "common_uses": common_uses,
                "side_effects": side_effects,
                "warnings": warnings,
                "pregnancy": pregnancy,
                "breastfeeding": pregnancy,
                "storage": storage,
                "interactions": interactions,
                "source_label": "openFDA Drug Label",
            },
        }
        normalized = self._normalize_generated_content(data, source_type="openfda")
        normalized["source_url"] = self._get_endpoint_url()
        normalized["source_label"] = _("openFDA Drug Label")
        return normalized

    def _normalize_cosmetic_event_items(self, product_name, events):
        reactions = []
        outcomes = []
        for event in events:
            reactions += event.get("reactions") or []
            outcomes += event.get("outcomes") or []
        reaction_summary = self._summarize_terms(reactions)
        outcome_summary = self._summarize_terms(outcomes)
        report_count = len(events)
        description = _(
            "FDA cosmetic adverse-event reports were found for %(product)s. Reported reactions include: %(reactions)s."
        ) % {
            "product": product_name,
            "reactions": reaction_summary or _("not specified"),
        }
        public_description = "\n".join(part for part in [
            description,
            _("Report count reviewed: %s") % report_count,
            _("Reported outcomes: %s") % outcome_summary if outcome_summary else "",
            _("This source is for safety signal context only and does not prove the product caused the reported event."),
        ] if part)
        data = {
            "name": product_name,
            "drug_class": "cosmetic",
            "description": description,
            "keywords": ", ".join(part for part in [product_name, "cosmetic safety", reaction_summary] if part),
            "public_description": self._html_paragraph(public_description),
            "warnings": description,
            "source_summary": _("Generated from local openFDA cosmetic adverse-event report data."),
            "drug_data": {
                "commercial_names": product_name,
                "drug_class": "cosmetic",
                "common_uses": _("Cosmetic product safety reference."),
                "side_effects": reaction_summary,
                "warnings": description,
                "source_label": "openFDA Cosmetic Event Reports",
            },
        }
        normalized = self._normalize_generated_content(data, source_type="openfda_cosmetic_event")
        normalized["source_url"] = self._get_endpoint_url()
        normalized["source_label"] = _("openFDA Cosmetic Event Reports")
        return normalized

    def _summarize_terms(self, values, limit=8):
        counts = {}
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            counts[text] = counts.get(text, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
        return ", ".join("%s (%s)" % (term, count) for term, count in ordered[:limit])

    def _normalize_generated_content(self, data, source_type):
        get = self._first_value
        nested = data.get("drug_data") if isinstance(data, dict) and isinstance(data.get("drug_data"), dict) else {}
        scientific = get(data, "scientific_name", "scientificName", "generic_name", "active_ingredient", "ingredient") or get(nested, "scientific_name", "scientificName", "generic_name")
        product_name = get(data, "name", "product_name", "trade_name", "brand_name", "commercial_name") or get(nested, "commercial_names", "commercial_name", "brand_name")
        manufacturer = get(data, "manufacturer", "company", "company_name")
        drug_class = get(data, "drug_class", "class", "therapeutic_category", "category", "product_type") or get(nested, "drug_class", "product_type", "category")
        common_uses = get(data, "common_uses", "uses", "indications", "description", "benefits", "use_cases") or get(nested, "common_uses", "uses", "benefits", "use_cases")
        warnings = get(data, "warnings", "warning", "precautions") or get(nested, "warnings", "warning", "precautions")
        storage = get(data, "storage", "storage_conditions") or get(nested, "storage", "storage_conditions")
        side_effects = get(data, "side_effects", "adverse_effects", "sensitivity_notes") or get(nested, "side_effects", "adverse_effects", "sensitivity_notes")
        interactions = get(data, "interactions", "drug_interactions", "compatibility_notes") or get(nested, "interactions", "drug_interactions", "compatibility_notes")
        description = get(data, "meta_description", "description", "notes", "short_description", "common_uses") or common_uses
        keywords = get(data, "keywords", "keyword_text")
        if isinstance(keywords, list):
            keywords = ", ".join(str(keyword) for keyword in keywords if keyword)
        return {
            "meta_title": get(data, "meta_title", "title") or " | ".join(part for part in [product_name, scientific] if part),
            "meta_description": description,
            "keyword_text": keywords or ", ".join(part for part in [product_name, scientific, manufacturer, drug_class] if part),
            "seo_name": get(data, "slug", "seo_name") or product_name,
            "short_description": get(data, "short_description", "summary") or description,
            "public_description": get(data, "public_description", "html_description") or description,
            "active_ingredient": get(data, "active_ingredient", "ingredient") or scientific,
            "warnings": warnings,
            "contraindications": get(data, "contraindications"),
            "storage": storage,
            "content_source": "ready_api" if source_type in ("drugs_eg", "openfda") else "assistant",
            "source_summary": get(data, "source_summary") or _("Generated from %s") % self.display_name,
            "drug_data": {
                "scientific_name": scientific,
                "commercial_names": get(data, "commercial_names", "brand_names") or get(nested, "commercial_names", "brand_names") or product_name,
                "active_ingredient": get(data, "active_ingredient", "ingredient") or get(nested, "active_ingredient", "ingredient") or scientific,
                "drug_class": drug_class,
                "regulatory_status": get(data, "regulatory_status", "legal_status", "otc_status") or get(nested, "regulatory_status", "legal_status", "otc_status"),
                "common_uses": common_uses,
                "side_effects": side_effects,
                "warnings": warnings,
                "pregnancy": get(data, "pregnancy", "pregnancy_warning") or get(nested, "pregnancy", "pregnancy_warning"),
                "breastfeeding": get(data, "breastfeeding", "lactation") or get(nested, "breastfeeding", "lactation"),
                "storage": storage,
                "interactions": interactions,
                "source_label": get(data, "source_label") or get(nested, "source_label") or self.display_name,
                "source_type": source_type,
            },
        }

    def _ensure_product_content_minimums(self, content, product_name=False, lang_code=False, raw_content=False):
        title = content.get("meta_title") or product_name or self._first_sentence(raw_content, max_length=70)
        description = content.get("meta_description") or content.get("short_description") or self._first_sentence(raw_content, max_length=255)
        if not description:
            description = _("Buy %(product)s from Abdin Pharmacies with updated product information.") % {
                "product": product_name or title or _("this product"),
            }
        content["meta_title"] = title or description[:70]
        content["meta_description"] = description
        content["keyword_text"] = content.get("keyword_text") or ", ".join(part for part in [product_name, content.get("active_ingredient")] if part)
        content["seo_name"] = content.get("seo_name") or product_name or title
        content["short_description"] = content.get("short_description") or description
        content["public_description"] = content.get("public_description") or "<p>%s</p>" % html_escape(description)
        content["content_source"] = content.get("content_source") or "assistant"
        return content

    def _html_paragraph(self, text):
        if not text:
            return False
        lines = str(html_escape(text)).splitlines() or [""]
        return "<p>%s</p>" % "<br/>".join(lines)

    def _first_value(self, data, *keys):
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else False
            if value not in (None, False, "", []):
                if isinstance(value, (list, tuple)):
                    return ", ".join(str(item) for item in value if item)
                return str(value)
        return False

    def _first_int(self, data, *keys):
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else False
            if value in (None, False, ""):
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return 0

    def unlink(self):
        raise UserError(_("Assistant configurations must be archived instead of deleted."))
