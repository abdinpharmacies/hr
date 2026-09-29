import json
import io
import os
import time
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import requests
from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services.catalog import CATALOG
from ..services.seo_templates import contract_prompt, validate as validate_template
from ..services.datasets import spl_records
from ..services.providers import ProviderFailure, adapter, ai_payload, ai_response, build_prompt, digest, validate_draft


MANAGER = "ab_website_seo_optimization.group_ab_website_seo_optimization_manager"
PROVIDER_TYPES = [(v, v.replace("_", " ").title()) for v in ("DATA_SOURCE", "AI_GENERATOR", "SAFETY_REGULATORY", "BARCODE_LOOKUP", "LOCAL_MODEL")]
NEW_PROVIDERS = [(k, v["name"]) for k, v in CATALOG.items() if k not in ("google_gemini", "groq", "openrouter", "huggingface", "alibaba_qwen", "ready_api", "openfda", "openfda_cosmetic_event", "openai", "other")]


class EnrichmentProvider(models.Model):
    _inherit = "ab.seo.assistant"

    provider = fields.Selection(selection_add=NEW_PROVIDERS, ondelete={k: "set default" for k, _label in NEW_PROVIDERS})
    model_name = fields.Char(required=False)
    provider_type = fields.Selection(PROVIDER_TYPES, compute="_compute_capabilities", store=True, index=True)
    supports_bulk = fields.Boolean(compute="_compute_capabilities", store=True)
    supports_api = fields.Boolean(compute="_compute_capabilities", store=True)
    source_scope = fields.Char(compute="_compute_capabilities", store=True)
    metadata = fields.Json(compute="_compute_source_metadata")
    supported_domains = fields.Char(compute="_compute_source_metadata")
    official_url = fields.Char(compute="_compute_source_metadata")
    license_name = fields.Char(compute="_compute_source_metadata")
    license_reviewed = fields.Boolean(default=False, groups=MANAGER)
    license_review_note = fields.Text(groups=MANAGER)
    commercial_permission = fields.Boolean(default=False, groups=MANAGER)
    attribution_required = fields.Boolean(compute="_compute_source_metadata")
    redistribution_allowed = fields.Selection([("unknown", "Review Required"), ("yes", "Allowed"), ("conditional", "Conditional")], default="unknown")
    reliability = fields.Json(compute="_compute_source_metadata")
    api_key_configured = fields.Boolean(compute="_compute_key_status", compute_sudo=True)
    allow_remote = fields.Boolean(default=False)
    authentication_required = fields.Boolean(default=False)
    monthly_limit = fields.Integer(default=0)
    token_limit = fields.Integer(default=0)
    monthly_token_limit = fields.Integer(default=0)
    rpm_limit = fields.Integer(default=10)
    tpm_limit = fields.Integer(default=0)
    quota_group_id = fields.Many2one("ab.seo.assistant", ondelete="restrict")
    requests_used = fields.Integer(readonly=True)
    monthly_requests_used = fields.Integer(readonly=True)
    monthly_tokens_used = fields.Integer(readonly=True)
    last_reset = fields.Datetime(readonly=True)
    month_start = fields.Date(readonly=True)
    minute_start = fields.Datetime(readonly=True)
    minute_requests = fields.Integer(readonly=True)
    minute_tokens = fields.Integer(readonly=True)
    quota_remaining = fields.Integer(compute="_compute_quota")
    disabled_until = fields.Datetime(readonly=True, index=True)
    health = fields.Selection([(v, label) for v, label in (("untested", "Not Tested"), ("ready", "Ready"), ("quota", "Quota Exhausted"), ("cooldown", "Cooling Down"), ("auth", "Authentication Failed"), ("unavailable", "Unavailable"), ("manual", "Manual Verification"))], default="untested", readonly=True)
    last_success = fields.Datetime(readonly=True)
    last_failure = fields.Datetime(readonly=True)
    last_error = fields.Char(readonly=True)
    error_count = fields.Integer(readonly=True)
    timeout_seconds = fields.Integer(default=15)
    retry_count = fields.Integer(default=2)
    backoff_seconds = fields.Float(default=.25)
    cooldown_seconds = fields.Integer(default=60)
    model_names = fields.Text()
    model_metadata = fields.Json(readonly=True)
    models_checked_at = fields.Datetime(readonly=True)
    models_endpoint = fields.Char(default="/models")
    account_id = fields.Char()
    region = fields.Char()
    daily_unit_limit = fields.Float(default=0)
    units_per_input_token = fields.Float(default=0)
    units_per_output_token = fields.Float(default=0)
    units_used_today = fields.Float(readonly=True)
    cache_days = fields.Integer(default=7)
    failure_cache_minutes = fields.Integer(default=5)
    dataset_url = fields.Char()
    dataset_format_name = fields.Char(default="dataset.json")
    dataset_json_prefix = fields.Char()
    dataset_checksum = fields.Char()
    dataset_version = fields.Char()
    sync_interval_days = fields.Integer(default=0)
    next_sync_at = fields.Datetime()
    last_successful_sync = fields.Datetime(readonly=True)
    index_revision = fields.Integer(readonly=True)
    lookup_identity = fields.Json()
    last_lookup_result = fields.Json(readonly=True)

    @api.depends("provider")
    def _compute_capabilities(self):
        for rec in self:
            spec = CATALOG.get(rec.provider, CATALOG["other"])
            rec.provider_type = spec["provider_type"]
            rec.supports_bulk = bool(spec.get("bulk_url"))
            rec.supports_api = bool(spec.get("api_url"))
            rec.source_scope = spec["scope"]

    @api.depends("provider", "last_successful_sync")
    def _compute_source_metadata(self):
        for rec in self:
            spec = CATALOG.get(rec.provider, CATALOG["other"])
            rec.metadata = spec
            rec.supported_domains = spec["domain"]
            rec.official_url = spec["official_url"]
            rec.license_name = spec["license"]
            rec.attribution_required = spec["commercial_use"] != "allowed" or "ODbL" in spec["license"]
            rec.reliability = {"authority": spec["authority"], "market_relevance": spec["market_relevance"], "identifier_quality": spec["identifiers"], "freshness": str(rec.last_successful_sync or "unknown"), "completeness": "record-dependent", "license": spec["commercial_use"]}

    def _compute_key_status(self):
        for rec in self:
            rec.api_key_configured = bool(rec.api_key or (rec.api_key_name and os.environ.get(rec.api_key_name)))

    @api.depends("daily_limit", "used_today", "last_used_date")
    def _compute_quota(self):
        for rec in self:
            rec.quota_remaining = max(rec.daily_limit - (rec.used_today if rec.last_used_date == fields.Date.today() else 0), 0) if rec.daily_limit else -1

    @api.constrains("quota_group_id")
    def _check_quota_group(self):
        for rec in self:
            if rec.quota_group_id and (rec.quota_group_id == rec or rec.quota_group_id.quota_group_id):
                raise ValidationError(_("Quota groups must point directly to a separate root provider."))

    @api.constrains("daily_limit", "monthly_limit", "retry_count", "timeout_seconds", "rpm_limit", "backoff_seconds", "sync_interval_days", "cache_days", "token_limit", "daily_token_limit", "monthly_token_limit", "tpm_limit", "daily_unit_limit", "units_per_input_token", "units_per_output_token")
    def _check_limits(self):
        for rec in self:
            if any(rec[k] < 0 for k in ("daily_limit", "monthly_limit", "rpm_limit", "backoff_seconds", "sync_interval_days", "cache_days", "token_limit", "daily_token_limit", "monthly_token_limit", "tpm_limit", "daily_unit_limit", "units_per_input_token", "units_per_output_token")) or not 0 <= rec.retry_count <= 3 or not 1 <= rec.timeout_seconds <= 120:
                raise ValidationError(_("Limits must be nonnegative; retries must be 0–3 and timeout 1–120 seconds."))

    def _require_enrichment_manager(self):
        if not self.env.su and not self.env.user.has_group(MANAGER):
            raise AccessError(_("Only SEO managers can configure or execute enrichment providers."))

    def _provider_defaults(self):
        defaults = super()._provider_defaults()
        for key, spec in CATALOG.items():
            defaults.setdefault(key, {})
            defaults[key].update(assistant_type="ai" if spec["scope"] == "generation" else "data_source", model_name=spec.get("model") or key,
                                 base_url=spec.get("api_url", ""), endpoint_path="/chat/completions" if spec["scope"] == "generation" else "",
                                 api_key_name=defaults[key].get("api_key_name", ""), daily_limit=100,
                                 notes=spec["current_limits"])
        defaults["google_gemini"]["endpoint_path"] = "/models/{model}:generateContent"
        defaults["cohere"]["endpoint_path"] = "/chat"
        defaults["groq"]["model_name"] = "openai/gpt-oss-20b"
        defaults["cloudflare"]["endpoint_path"] = "/run/{model}"
        defaults["openfda"].update(base_url="https://api.fda.gov", endpoint_path="/drug/label.json")
        defaults["openfda_cosmetic_event"].update(base_url="https://api.fda.gov", endpoint_path="/cosmetic/event.json")
        return defaults

    def action_apply_provider_defaults(self):
        self._require_enrichment_manager()
        return super().action_apply_provider_defaults()

    def _test_configuration(self):
        self.ensure_one()
        if not self.active:
            return "misconfigured", _("%s is archived.") % self.display_name
        if CATALOG[self.provider].get("mode") == "manual" or not self.supports_api:
            return "ready", _("Use the official verification page and record the source evidence.")
        if self.source_scope == "generation" and not self.model_name:
            return "misconfigured", _("%s has no model name.") % self.display_name
        if (self.source_scope == "generation" and self.provider != "local_ai" or self.provider in ("ready_api", "usda_fdc") or self.authentication_required) and not self._credential():
            return "missing_key", _("%s is configured but no API key is stored.") % self.display_name
        try:
            self._endpoint(generation=self.source_scope == "generation")
        except ProviderFailure:
            return "misconfigured", _("%s has no base URL.") % self.display_name
        return "ready", _("Configuration is valid. Use Test Connection to verify live access.")

    def _credential(self):
        self.ensure_one()
        return self.api_key or (os.environ.get(self.api_key_name, "") if self.api_key_name else "")

    def _allowed_for_commercial(self):
        self.ensure_one()
        spec = CATALOG[self.provider]
        return spec["commercial_use"] == "allowed" or (self.license_reviewed and bool(self.license_review_note) and (spec["commercial_use"] != "permission" or self.commercial_permission))

    def _reset_windows(self, now):
        vals = {}
        if self.last_used_date != now.date():
            vals.update(last_used_date=now.date(), used_today=0, total_tokens_today=0, prompt_tokens_today=0, completion_tokens_today=0, units_used_today=0, last_reset=now)
        if not self.month_start or self.month_start.replace(day=1) != now.date().replace(day=1):
            vals.update(month_start=now.date().replace(day=1), monthly_requests_used=0, monthly_tokens_used=0)
        if not self.minute_start or (now - self.minute_start).total_seconds() >= 60:
            vals.update(minute_start=now, minute_requests=0, minute_tokens=0)
        if vals:
            self.write(vals)

    def _reserve(self, tokens=0, units=0):
        self.ensure_one()
        if not self.try_lock_for_update(allow_referencing=True):
            raise ProviderFailure("provider_busy", retry_after=5)
        self.invalidate_recordset()
        now = fields.Datetime.now()
        self._reset_windows(now)
        if not self.active:
            raise ProviderFailure("disabled")
        if self.disabled_until and self.disabled_until > now:
            raise ProviderFailure("quota_exhausted" if self.health == "quota" else "cooldown", retry_after=(self.disabled_until - now).total_seconds())
        limits = [(self.daily_limit, self.used_today, 1, "day"), (self.monthly_limit, self.monthly_requests_used, 1, "month"),
                  (self.daily_token_limit, self.total_tokens_today, tokens, "day"), (self.monthly_token_limit, self.monthly_tokens_used, tokens, "month"),
                  (self.token_limit, self.lifetime_total_tokens, tokens, "lifetime"), (self.rpm_limit, self.minute_requests, 1, "minute"),
                  (self.tpm_limit, self.minute_tokens, tokens, "minute"), (self.daily_unit_limit, self.units_used_today, units, "day")]
        for limit, used, requested, window in limits:
            if limit and used + requested > limit:
                end = self.minute_start + timedelta(seconds=60) if window == "minute" else datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
                if window == "month":
                    end = datetime.combine((now.date().replace(day=28) + timedelta(days=4)).replace(day=1), datetime.min.time())
                if window == "lifetime":
                    end = now + timedelta(days=3650)
                self.write({"health": "quota", "disabled_until": end})
                raise ProviderFailure("quota_exhausted", retry_after=(end - now).total_seconds())
        if self.quota_group_id:
            self.quota_group_id._reserve(tokens, units)
        self.write({"used_today": self.used_today + 1, "requests_used": self.requests_used + 1,
                    "monthly_requests_used": self.monthly_requests_used + 1, "minute_requests": self.minute_requests + 1,
                    "total_tokens_today": self.total_tokens_today + tokens, "monthly_tokens_used": self.monthly_tokens_used + tokens,
                    "minute_tokens": self.minute_tokens + tokens, "lifetime_total_tokens": self.lifetime_total_tokens + tokens,
                    "units_used_today": self.units_used_today + units})

    def _account_units(self, actual, reserved):
        self.units_used_today = max(0, self.units_used_today + actual - reserved)
        if self.quota_group_id:
            self.quota_group_id._account_units(actual, reserved)

    def _account_tokens(self, usage, reserved):
        prompt = max(int(usage.get("prompt_tokens") or 0), 0)
        completion = max(int(usage.get("completion_tokens") or 0), 0)
        total = int(usage.get("total_tokens") or prompt + completion or reserved)
        delta = total - reserved
        self.write({"total_tokens_today": max(0, self.total_tokens_today + delta), "monthly_tokens_used": max(0, self.monthly_tokens_used + delta),
                    "minute_tokens": max(0, self.minute_tokens + delta), "lifetime_total_tokens": max(0, self.lifetime_total_tokens + delta),
                    "prompt_tokens_today": self.prompt_tokens_today + prompt, "completion_tokens_today": self.completion_tokens_today + completion,
                    "lifetime_prompt_tokens": self.lifetime_prompt_tokens + prompt, "lifetime_completion_tokens": self.lifetime_completion_tokens + completion,
                    "last_prompt_tokens": prompt, "last_completion_tokens": completion, "last_total_tokens": total, "last_token_usage_at": fields.Datetime.now()})
        if self.quota_group_id:
            self.quota_group_id._account_tokens(usage, reserved)

    def _endpoint(self, path="", model=None, generation=False):
        if path == "__cohere_models__" and self.provider == "cohere":
            return "https://api.cohere.com/v1/models"
        if path == "__openfda_manifest__" and self.provider in ("openfda", "fda_ndc", "openfda_cosmetic_event"):
            return "https://api.fda.gov/download.json"
        spec = CATALOG[self.provider]
        base = self.base_url or spec.get("api_url", "")
        if self.provider == "huggingface" and "api-inference.huggingface.co" in base:
            base = spec["api_url"]
        if not generation and self.provider in ("openfda", "fda_ndc", "openfda_cosmetic_event", "ready_api"):
            base = self._get_endpoint_url() if self.base_url and self.endpoint_path and self.endpoint_path != "/chat/completions" else spec["api_url"]
        if generation:
            path = self.endpoint_path or "/chat/completions"
            if self.provider == "huggingface":
                path = "/chat/completions"
            if self.provider == "cohere":
                path = "/chat"
            if self.provider == "cloudflare":
                path = "/run/{model}"
            if self.provider == "google_gemini":
                path = "/models/{model}:generateContent"
        url = (base.rstrip("/") + ("/" + path.lstrip("/") if path else "")).replace("{account_id}", self.account_id or "").replace("{model}", model or self.model_name or "")
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ProviderFailure("invalid_endpoint")
        if parsed.scheme != "https" and self.provider != "local_ai":
            raise ProviderFailure("https_required")
        return url

    def _request(self, method, path="", payload=None, params=None, model=None, generation=False, operation="lookup", response_format="json"):
        self.ensure_one()
        key = self._credential()
        if (self.source_scope == "generation" and self.provider != "local_ai" or self.provider in ("ready_api", "usda_fdc") or self.authentication_required) and not key:
            failure = ProviderFailure("authentication_missing", 401)
            self._record_failure(failure)
            self._call_log(operation, time.monotonic(), 401, failure.code, model)
            raise failure
        url = self._endpoint(path, model, generation)
        params = dict(params or {})
        headers = {"Accept": "application/xml" if response_format == "spl" else "application/json", "User-Agent": "AbdinSEO/19.0 (catalog enrichment; local cache)"}
        if key:
            if self.provider in ("openfda", "fda_ndc", "openfda_cosmetic_event", "usda_fdc"):
                params["api_key"] = key
            else:
                headers["x-goog-api-key" if self.provider == "google_gemini" else "Authorization"] = key if self.provider == "google_gemini" else "Bearer " + key
        reserved = len(json.dumps(payload or {}, ensure_ascii=False).encode()) + self.max_output_tokens if generation else 0
        for attempt in range(self.retry_count + 1):
            start = time.monotonic()
            status = 0
            try:
                units = 0
                if generation and self.daily_unit_limit:
                    if not self.units_per_input_token or not self.units_per_output_token:
                        raise ProviderFailure("unit_cost_configuration_required")
                    units = reserved * max(self.units_per_input_token, self.units_per_output_token)
                self._reserve(reserved, units)
                with requests.request(method, url, json=payload, params=params, headers=headers, timeout=(5, self.timeout_seconds), allow_redirects=False, stream=True) as response:
                    status = response.status_code
                    if status >= 300:
                        retry_after = response.headers.get("Retry-After", "")
                        delay = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else self.cooldown_seconds
                        code = "rate_limit" if status == 429 else "authentication_failed" if status in (401, 403) else "unsupported_model" if status == 404 and generation else "empty_response" if status == 404 else "temporary_failure" if status in (408, 500, 502, 503, 504) else "invalid_request"
                        raise ProviderFailure(code, status, delay)
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        if len(body) + len(chunk) > 16 * 1024 * 1024:
                            raise ProviderFailure("response_too_large", status)
                        body.extend(chunk)
                    try:
                        data = {"spl": list(spl_records(io.BytesIO(body)))} if response_format == "spl" else json.loads(body)
                    except (ValueError, etree.XMLSyntaxError) as error:
                        raise ProviderFailure("malformed_response", status) from error
                    if not isinstance(data, (dict, list)) or not data:
                        raise ProviderFailure("empty_response", status)
                    if isinstance(data, dict) and (data.get("error") or data.get("success") is False):
                        raise ProviderFailure("provider_error", status)
                if generation:
                    _text, usage = ai_response(self.provider, data)
                    self._account_tokens(usage, reserved)
                    if self.daily_unit_limit:
                        actual_units = (int(usage.get("prompt_tokens") or 0) * self.units_per_input_token + int(usage.get("completion_tokens") or 0) * self.units_per_output_token) or units
                        self._account_units(actual_units, units)
                self.write({"health": "ready", "last_success": fields.Datetime.now(), "disabled_until": False, "last_error": False})
                self._call_log(operation, start, status, model=model)
                return data
            except (requests.Timeout, requests.ConnectionError) as error:
                failure = ProviderFailure("timeout" if isinstance(error, requests.Timeout) else "network_error")
            except requests.RequestException:
                failure = ProviderFailure("invalid_endpoint")
            except ProviderFailure as error:
                failure = error
            self._call_log(operation, start, failure.status or status, failure.code, model=model)
            retryable = failure.code in ("timeout", "network_error", "temporary_failure", "rate_limit")
            delay = max(self.backoff_seconds * 2 ** attempt, failure.retry_after if failure.status == 429 else 0)
            if retryable and attempt < self.retry_count and delay <= 2:
                time.sleep(delay)
                continue
            self._record_failure(failure)
            raise failure

    def _record_failure(self, error):
        health = "quota" if error.code == "quota_exhausted" else "auth" if error.status in (401, 403) else "cooldown" if error.code in ("rate_limit", "timeout", "network_error", "temporary_failure") else "unavailable"
        now = fields.Datetime.now()
        delay = max(error.retry_after, 3600 if health == "auth" else self.cooldown_seconds)
        self.write({"health": health, "last_failure": now, "error_count": self.error_count + 1, "last_error": error.code,
                    "disabled_until": max(self.disabled_until or now, now + timedelta(seconds=delay))})

    def _call_log(self, operation, start, status=0, error=None, model=None):
        self.env["ab_seo_provider_call"].sudo().create({
            "provider_id": self.id, "job_id": self.env.context.get("enrichment_job_id"),
            "product_id": self.env.context.get("enrichment_product_id"), "operation": operation,
            "started_at": fields.Datetime.now() - timedelta(seconds=time.monotonic() - start),
            "duration": time.monotonic() - start, "success": not error, "status_code": status,
            "error_type": error, "fallback_triggered": bool(error), "model_name": model})

    def _lookup(self, identity):
        self.ensure_one()
        if not self.active:
            raise ProviderFailure("disabled")
        found = self.env["ab_seo_source_record"]._lookup(self, identity)
        if not found and self.provider == "ready_api" and identity.get("name"):
            cached = self.env["ab.product.drug.data"].search(fields.Domain("product_name", "=ilike", identity["name"]), limit=10)
            found = []
            for rec in cached:
                values = {k: rec[k] for k in ("product_name", "manufacturer", "active_ingredient", "dosage_form", "strength", "package_size", "route") if rec[k]}
                values["source_id"] = rec.external_id or str(rec.id)
                item = adapter(self.provider).normalize(values)
                item.update(source_url=rec.source_url, source_version=str(rec.last_synced_at), checksum=digest(rec.raw_payload))
                found.append(item)
        if found:
            if self.provider == "rxnorm":
                codes = {code for row in found for code in row.get("identifiers", {}).get("rxcui", [])}
                identifiers = self.env["ab_seo_source_identifier"].search(fields.Domain("provider_id", "=", self.id) & fields.Domain("kind", "=", "rxcui") & fields.Domain("value", "in", list(codes)) & fields.Domain("record_id.active", "=", True) & fields.Domain("record_id.dataset_id.state", "=", "done"), limit=100)
                found = list({row["source_id"]: row for row in found + identifiers.mapped("record_id.payload")}.values())
            self._call_log("local_lookup", time.monotonic())
            return found
        if not self.allow_remote:
            raise ProviderFailure("local_miss")
        cache_key = digest([identity, self.provider, self.base_url, self.endpoint_path, self.index_revision])
        cache = self.env["ab_seo_cache"]._get(self, "lookup", cache_key)
        if cache:
            if cache.error_type:
                raise ProviderFailure(cache.error_type)
            return cache.payload
        try:
            def request(method, path, **kwargs):
                result = self._request(method, path, **kwargs)
                if not isinstance(result, dict) and self.provider != "ready_api":
                    raise ProviderFailure("malformed_response")
                return result
            found = adapter(self.provider).lookup(identity, request)
            if not found:
                raise ProviderFailure("empty_response")
            for row in found:
                row["retrieved_at"] = fields.Datetime.to_string(fields.Datetime.now())
        except ProviderFailure as error:
            self.env["ab_seo_cache"]._put(self, "lookup", cache_key, {}, error.code)
            raise
        self.env["ab_seo_cache"]._put(self, "lookup", cache_key, found)
        return found

    def _generate_grounded(self, name, language, facts, provenance, prompt_version, contract=None, category_context=None):
        self.ensure_one()
        if not self.active:
            raise ProviderFailure("disabled")
        if self.provider_type not in ("AI_GENERATOR", "LOCAL_MODEL"):
            raise ProviderFailure("unsupported_operation")
        if not self.allow_remote and self.provider != "local_ai":
            raise ProviderFailure("remote_disabled")
        names = [v.strip() for v in (self.model_names or self.model_name or "").splitlines() if v.strip()]
        if not names:
            raise ProviderFailure("model_not_configured")
        if self.provider in ("groq", "openrouter", "google_gemini") and (not self.models_checked_at or self.models_checked_at < fields.Datetime.now() - timedelta(days=1)):
            self.action_refresh_models()
        available = self.model_metadata or {}
        if available.get("ids"):
            names = [v for v in names if v in available["ids"]]
        if not names:
            raise ProviderFailure("unsupported_model")
        evidence = self.env["ab_seo_enrichment_fact"].browse(provenance).exists()
        stable_sources = sorted([{"field": row.field_name, "source": row.provider_id.provider or "internal", "source_id": row.source_record_id,
                                  "version": row.source_version, "url": row.source_url, "value_hash": row.value_hash} for row in evidence], key=lambda row: digest(row))
        prompt = contract_prompt(contract, facts, stable_sources, language, category_context) if contract else build_prompt(name, language, facts, prompt_version, stable_sources)
        last_error = ProviderFailure("empty_response")
        for model in names:
            key = digest([name, language, facts, stable_sources, prompt_version, contract, category_context, model, self.base_url, self.endpoint_path, self.temperature, self.max_output_tokens])
            cache = self.env["ab_seo_cache"]._get(self, "generation", key)
            if cache:
                if cache.error_type:
                    last_error = ProviderFailure(cache.error_type)
                    continue
                return dict(cache.payload, cache_hit=True, input_sources=provenance)
            try:
                response = self._request("POST", payload=ai_payload(self.provider, model, prompt, self.temperature, self.max_output_tokens), model=model, generation=True, operation="generation")
                text, _usage = ai_response(self.provider, response)
                try:
                    payload = json.loads(text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
                except (ValueError, TypeError) as error:
                    raise ProviderFailure("malformed_response") from error
                if contract:
                    if not isinstance(payload, dict) or set(payload) - {'meta_title', 'meta_description', 'short_description', 'sections', 'keywords'}:
                        raise ProviderFailure("malformed_response")
                    result = dict(payload, content_kind="GENERATED_TEXT", content_source="assistant", review_required=True)
                    report = validate_template(result, contract, facts, language)
                    if report["errors"]:
                        raise ProviderFailure("template_validation_failed")
                    keywords = result.get("keywords", [])
                    result.update(keyword_text=", ".join(keywords), search_phrases=keywords, seo_name=name, validation=report)
                else:
                    result = validate_draft(payload, facts)
                result.update(provider_id=self.id, model=model, prompt_version=prompt_version, normalized_input_hash=key, input_sources=provenance)
                self.env["ab_seo_cache"]._put(self, "generation", key, result)
                return result
            except ProviderFailure as error:
                last_error = error
                self.env["ab_seo_cache"]._put(self, "generation", key, {}, error.code)
                if error.code not in ("unsupported_model", "malformed_response", "empty_response", "invalid_request", "provider_error", "template_validation_failed"):
                    break
                self.disabled_until = False
        raise last_error

    def action_test_connection(self):
        self._require_enrichment_manager()
        for rec in self:
            try:
                if CATALOG[rec.provider].get("mode") == "manual":
                    rec.write({"health": "manual", "last_test_message": _("Use the official verification page and record the source evidence.")})
                elif rec.source_scope == "generation":
                    rec.action_refresh_models()
                else:
                    rec.action_test_lookup()
            except ProviderFailure as error:
                rec._record_failure(error)
            rec.last_test_at = fields.Datetime.now()
        return True

    def action_refresh_models(self):
        self._require_enrichment_manager()
        for rec in self:
            path = "/models" if rec.provider == "google_gemini" else rec.models_endpoint
            if rec.provider == "cohere":
                path = "__cohere_models__"
            if rec.provider == "cloudflare":
                path = "/models/search"
            if not path:
                raise UserError(_("Configure a documented model-list endpoint for this provider."))
            data = rec._request("GET", path, operation="models", params={"page_size": 1000, "endpoint": "chat"} if rec.provider == "cohere" else None)
            if not isinstance(data, dict):
                raise ProviderFailure("malformed_response")
            rows = data.get("data", data.get("models", data.get("result", [])))
            if not isinstance(rows, list):
                raise ProviderFailure("malformed_response")
            ids = [(row.get("name") if rec.provider == "cloudflare" else row.get("id")) or row.get("name", "").removeprefix("models/") for row in rows if isinstance(row, dict) and not row.get("is_deprecated")]
            rec.write({"model_metadata": {"ids": ids}, "models_checked_at": fields.Datetime.now()})
            if rec.model_name and rec.model_name not in ids:
                rec.write({"health": "unavailable", "last_error": "unsupported_model"})
        return True

    def action_test_lookup(self):
        self._require_enrichment_manager()
        for rec in self:
            if not isinstance(rec.lookup_identity, dict) or not rec.lookup_identity:
                raise UserError(_("Enter an identity with a name or exact identifier before testing a lookup."))
            try:
                rec.last_lookup_result = rec._lookup(rec.lookup_identity)
            except ProviderFailure as error:
                rec.last_lookup_result = {"error": error.code}
        return True

    def action_reset_usage(self):
        self._require_enrichment_manager()
        self.write({"disabled_until": False, "health": "untested", "used_today": 0, "monthly_requests_used": 0, "monthly_tokens_used": 0, "minute_requests": 0, "minute_tokens": 0, "total_tokens_today": 0, "units_used_today": 0, "last_reset": fields.Datetime.now()})
        for rec in self:
            rec._call_log("usage_reset", time.monotonic())
        return True

    def action_disable_provider(self):
        self._require_enrichment_manager()
        self.active = False
        return True

    def action_move_up(self):
        self._require_enrichment_manager()
        for rec in self:
            rec.sequence -= 1
        return True

    def action_move_down(self):
        self._require_enrichment_manager()
        for rec in self:
            rec.sequence += 1
        return True

    def action_sync_dataset(self):
        self._require_enrichment_manager()
        for rec in self:
            if not rec.dataset_url and rec.provider in ("openfda", "fda_ndc", "openfda_cosmetic_event"):
                data = rec._request("GET", "__openfda_manifest__", operation="bulk_manifest")
                category, kind = ("cosmetic", "event") if rec.provider == "openfda_cosmetic_event" else ("drug", "ndc" if rec.provider == "fda_ndc" else "label")
                release = data.get("results", {}).get(category, {}).get(kind, {})
                partitions = release.get("partitions", [])
                if not partitions:
                    raise UserError(_("The official download manifest contains no dataset partitions."))
                for part in partitions:
                    url = part.get("file")
                    if not url:
                        continue
                    self.env["ab_seo_dataset"].create({"provider_id": rec.id, "url": url, "filename": urlsplit(url).path.rsplit("/", 1)[-1],
                        "source_version": str(release.get("export_date") or fields.Date.today()), "state": "queued"})
                continue
            if not rec.dataset_url:
                raise UserError(_("Configure an actual dataset file URL from the official download page."))
            self.env["ab_seo_dataset"].create({"provider_id": rec.id, "url": rec.dataset_url, "filename": rec.dataset_format_name,
                                                "source_version": rec.dataset_version or str(fields.Date.today()), "expected_checksum": rec.dataset_checksum,
                                                "json_prefix": rec.dataset_json_prefix, "state": "queued"})
        return True

    def action_rebuild_index(self):
        self._require_enrichment_manager()
        datasets = self.env["ab_seo_dataset"].search(fields.Domain("provider_id", "in", self.ids) & fields.Domain("state", "=", "done"))
        datasets.action_rebuild_index()
        return True

    def action_purge_stale_cache(self):
        self._require_enrichment_manager()
        stale = self.env["ab_seo_cache"].sudo().search(fields.Domain("provider_id", "in", self.ids) & fields.Domain("expires_at", "<", fields.Datetime.now()), limit=10000)
        stale.unlink()
        return True

    def generate_product_content(self, product_name, lang_code, product_context=None):
        self._require_enrichment_manager()
        if self.provider_type == "SAFETY_REGULATORY":
            raise UserError(_("Safety reports cannot generate product descriptions. Use internal enrichment context."))
        context = product_context or {}
        facts = {k: v for k, v in context.get("trusted_facts", {}).items() if k in ("name", "manufacturer", "brand", "active_ingredients", "strength", "dosage_form", "package")}
        facts.setdefault("name", product_name)
        if self.source_scope != "generation":
            try:
                return {"source_candidates": self._lookup(dict(facts, **context.get("identity", {}))), "review_required": True}
            except ProviderFailure as error:
                raise UserError(_("Provider lookup failed: %s") % error.code) from error
        try:
            return self._generate_grounded(product_name, lang_code, facts, [], "seo_v2")
        except ProviderFailure as error:
            raise UserError(_("Provider generation failed: %s") % error.code) from error

    def _normalize_cosmetic_event_items(self, product_name, events):
        return {"safety_context": events, "source_label": "openFDA Cosmetic Event Reports", "review_required": True}

    @api.model
    def _suggest_component(self, name, language, context):
        facts = {"name": name}
        for key in ("manufacturer", "product_code"):
            if context.get(key):
                facts[key] = context[key]
        providers = self.search(fields.Domain("provider_type", "in", ("AI_GENERATOR", "LOCAL_MODEL")), order="sequence, id")
        for provider in providers:
            if not provider._allowed_for_commercial():
                continue
            try:
                result = provider._generate_grounded(name, language, facts, [], "seo_component_v2")
                if result.get("unverified_proposal"):
                    continue
                return {"title": result["meta_title"][:70], "description": result["meta_description"][:160],
                        "keywords": provider._split_keywords(result.get("keyword_text")), "slug": name,
                        "assistant_id": provider.id, "assistant_name": provider.display_name}
            except ProviderFailure:
                continue
        raise UserError(_("No configured provider returned a usable SEO suggestion."))


class ProviderCall(models.Model):
    _name = "ab_seo_provider_call"
    _description = "Enrichment Provider Call"
    _order = "id desc"

    provider_id = fields.Many2one("ab.seo.assistant", required=True, index=True, ondelete="restrict")
    job_id = fields.Many2one("ab.product.seo.bulk.optimization", index=True, ondelete="restrict")
    product_id = fields.Many2one("product.template", index=True, ondelete="restrict")
    operation = fields.Char(required=True, index=True)
    started_at = fields.Datetime(required=True)
    duration = fields.Float()
    success = fields.Boolean(index=True)
    status_code = fields.Integer()
    error_type = fields.Char(index=True)
    fallback_triggered = fields.Boolean()
    model_name = fields.Char()

    def write(self, vals):
        raise UserError(_("Enrichment audit records are immutable."))

    def unlink(self):
        raise UserError(_("Enrichment audit records cannot be deleted."))


class EnrichmentCache(models.Model):
    _name = "ab_seo_cache"
    _description = "Enrichment Cache"

    provider_id = fields.Many2one("ab.seo.assistant", required=True, index=True, ondelete="cascade")
    operation = fields.Char(required=True)
    input_hash = fields.Char(required=True, index=True)
    payload = fields.Json()
    error_type = fields.Char()
    expires_at = fields.Datetime(required=True, index=True)

    _unique_input = models.Constraint("UNIQUE(provider_id, operation, input_hash)", "A provider cache entry must be unique.")

    @api.model
    def _get(self, provider, operation, key):
        return self.sudo().search(fields.Domain("provider_id", "=", provider.id) & fields.Domain("operation", "=", operation) & fields.Domain("input_hash", "=", key) & fields.Domain("expires_at", ">", fields.Datetime.now()), limit=1)

    @api.model
    def _put(self, provider, operation, key, payload, error=None):
        cache = self.sudo().search(fields.Domain("provider_id", "=", provider.id) & fields.Domain("operation", "=", operation) & fields.Domain("input_hash", "=", key), limit=1)
        vals = {"payload": payload, "error_type": error, "expires_at": fields.Datetime.now() + (timedelta(minutes=provider.failure_cache_minutes) if error else timedelta(days=provider.cache_days))}
        if cache:
            cache.write(vals)
        else:
            self.sudo().create(dict(vals, provider_id=provider.id, operation=operation, input_hash=key))
