import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from odoo import api, fields, models
from odoo.exceptions import UserError
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
            ("ready_api", "Ready API"),
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
        base_url = (self.base_url or "").rstrip("/")
        endpoint_path = (self.endpoint_path or "").replace("{model}", self.model_name or "").lstrip("/")
        return "%s/%s" % (base_url, endpoint_path)

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

    def _request_ai_product(self, product_name, lang_code, product_context=None):
        self.ensure_one()
        prompt = self._build_ai_product_prompt(product_name, lang_code, product_context=product_context)
        payload = self._build_ai_payload(prompt)
        response = self._http_json("POST", self._get_endpoint_url(), payload=payload)
        content = self._extract_ai_text(response)
        if not content:
            raise UserError(_("%s returned an empty AI response.") % self.display_name)
        return self._parse_ai_content(content), self._extract_token_usage(response)

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
        elif self.api_key:
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

    def _parse_ai_content(self, content):
        clean_content = self._extract_json_text(content)
        try:
            data = json.loads(clean_content)
        except json.JSONDecodeError as error:
            raise UserError(_("%s did not return valid JSON content.") % self.display_name) from error
        if not isinstance(data, dict):
            raise UserError(_("%s returned JSON but not an object.") % self.display_name)
        return self._normalize_generated_content(data, source_type="assistant")

    def _extract_json_text(self, content):
        clean_content = (content or "").strip()
        if clean_content.startswith("```"):
            clean_content = clean_content.strip()
            lines = clean_content.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_content = "\n".join(lines).strip()
        if clean_content.lower().startswith("json"):
            clean_content = clean_content[4:].strip()
        if clean_content.startswith("{") and clean_content.endswith("}"):
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
            "content_source": "ready_api" if source_type == "drugs_eg" else "assistant",
            "source_summary": _("Generated from %s") % self.display_name,
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
