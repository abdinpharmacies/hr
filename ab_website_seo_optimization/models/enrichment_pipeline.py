import json
import logging
import re
import time
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html_escape

from ..services.catalog import CATALOG
from ..services.seo_templates import FACT_KEYS
from ..services.providers import MEDICAL, SEO_FIELDS, ProviderFailure, digest, match, normalized, strings
from .enrichment_provider import MANAGER


_logger = logging.getLogger(__name__)
DOMAINS = [(key, label) for key, label in (("auto", "Automatic"), ("drug", "Drug"), ("cosmetic", "Cosmetic"), ("supplement", "Supplement"), ("food", "Food"), ("general", "General"))]


class EnrichmentPipeline(models.Model):
    _name = "ab_seo_pipeline"
    _description = "Product Enrichment Pipeline"
    _order = "sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    domain = fields.Selection(DOMAINS[1:], required=True, default="general", index=True)
    line_ids = fields.One2many("ab_seo_pipeline_step", "pipeline_id")
    prompt_version = fields.Char(default="seo_v2", required=True)
    ai_mode = fields.Selection([("off", "Sources Only"), ("missing", "Generate Missing Content"), ("always", "Generate Drafts")], default="missing", required=True)
    category_ids = fields.Many2many("product.public.category", string="Product Categories")

    def _providers(self, generation=False):
        self.ensure_one()
        return self.line_ids.sorted(lambda line: (line.sequence, line.id)).filtered(
            lambda line: line.active and line.provider_id.active and (line.provider_id.source_scope == "generation") == generation
        ).mapped("provider_id")


class EnrichmentPipelineStep(models.Model):
    _name = "ab_seo_pipeline_step"
    _description = "Enrichment Pipeline Step"
    _order = "sequence, id"

    pipeline_id = fields.Many2one("ab_seo_pipeline", required=True, index=True, ondelete="cascade")
    provider_id = fields.Many2one("ab.seo.assistant", required=True, ondelete="restrict")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    provider_type = fields.Selection(related="provider_id.provider_type")

    _unique_step = models.Constraint("UNIQUE(pipeline_id, provider_id)", "A provider can appear only once in a pipeline.")


class EnrichmentFact(models.Model):
    _name = "ab_seo_enrichment_fact"
    _description = "Enrichment Field Provenance"
    _order = "id desc"

    item_id = fields.Many2one("ab_seo_work_item", required=True, index=True, ondelete="restrict")
    product_id = fields.Many2one(related="item_id.product_id", store=True, index=True)
    job_id = fields.Many2one(related="item_id.job_id", store=True, index=True)
    provider_id = fields.Many2one("ab.seo.assistant", index=True, ondelete="restrict")
    field_name = fields.Char(required=True, index=True)
    value = fields.Json(required=True)
    content_kind = fields.Selection([(v, v.replace("_", " ").title()) for v in ("SOURCE_FACT", "GENERATED_TEXT", "INFERRED_TEXT", "UNVERIFIED_TEXT")], required=True)
    source_record_id = fields.Char()
    source_version = fields.Char()
    source_url = fields.Char()
    source_type = fields.Char()
    matched_by = fields.Char()
    matched_identifier = fields.Char()
    match_score = fields.Float()
    retrieved_at = fields.Datetime(default=fields.Datetime.now, required=True)
    verified_at = fields.Datetime()
    accepted = fields.Boolean(default=False)
    source_metadata = fields.Json()
    value_hash = fields.Char(required=True)
    lang_code = fields.Char()
    model_name = fields.Char()
    prompt_version = fields.Char()
    input_sources = fields.Json()

    _unique_evidence = models.Constraint("UNIQUE(item_id, value_hash)", "Evidence must not be duplicated on job resume.")

    def write(self, vals):
        raise UserError(_("Enrichment audit records are immutable."))

    def unlink(self):
        raise UserError(_("Enrichment audit records cannot be deleted."))


class EnrichmentWorkItem(models.Model):
    _name = "ab_seo_work_item"
    _description = "Resumable Product Enrichment Item"
    _order = "id"

    job_id = fields.Many2one("ab.product.seo.bulk.optimization", required=True, index=True, ondelete="restrict")
    product_id = fields.Many2one("product.template", required=True, index=True, ondelete="restrict")
    company_id = fields.Many2one(related="job_id.company_id", store=True, index=True)
    state = fields.Selection([(v, label) for v, label in (("queued", "Queued"), ("processing", "Processing"), ("done", "Successful"), ("failed", "Failed"), ("skipped", "Skipped"), ("review_required", "Review Required"), ("waiting", "Waiting for Providers"))], default="queued", required=True, index=True)
    attempts = fields.Integer(readonly=True)
    next_attempt_at = fields.Datetime(index=True)
    last_error = fields.Char(readonly=True)
    seo_id = fields.Many2one("ab.product.seo", ondelete="restrict", readonly=True)
    pipeline_id = fields.Many2one("ab_seo_pipeline", ondelete="restrict", readonly=True)
    fact_ids = fields.One2many("ab_seo_enrichment_fact", "item_id", readonly=True)
    result = fields.Json(readonly=True)
    normalized_input_hash = fields.Char(readonly=True)

    _unique_product_job = models.Constraint("UNIQUE(job_id, product_id)", "Each product can be queued once per enrichment job.")
    _queue_index = models.Index("(job_id, state, next_attempt_at, id)")

    def _identity(self):
        template = self.product_id
        product = template.ab_product_id
        explicit = template.ab_enrichment_identity or {}
        identity = {
            "name": product.name or product.product_card_name or template.name,
            "manufacturer": product.company_id.name or "",
            "gtin": product.barcode_ids.mapped("name"),
            "active_ingredients": product.effective_material or "",
            "strength": str(product.effective_material_conc or ""),
            "internal_id": product.id,
        }
        identity.update({k: v for k, v in explicit.items() if k in ("source_ids", "ndc", "rxcui", "registration", "dosage_form", "strength", "cas", "inchi", "gtin") and v})
        return identity

    def _select_pipeline(self):
        job = self.job_id
        if job.pipeline_id:
            return job.pipeline_id
        domain = self.product_id.ab_enrichment_domain
        if domain == "auto":
            categories = self.product_id.public_categ_ids
            category_pipeline = self.env["ab_seo_pipeline"].search(fields.Domain("category_ids", "parent_of", categories.ids), limit=1) if categories else self.env["ab_seo_pipeline"]
            if category_pipeline:
                return category_pipeline
            domain = "drug" if getattr(self.product_id.ab_product_id, "is_medicine", False) else "general"
        return self.env["ab_seo_pipeline"].search(fields.Domain("domain", "=", domain), limit=1)

    def _evidence(self, field, value, provider=None, record=None, matching=None, accepted=False, kind="SOURCE_FACT", lang=None, generation=None):
        self.ensure_one()
        record, matching, generation = record or {}, matching or {}, generation or {}
        key = digest([field, value, provider.id if provider else None, record.get("source_id"), record.get("source_version"), lang, generation.get("normalized_input_hash")])
        model = self.env["ab_seo_enrichment_fact"].sudo()
        old = model.search(fields.Domain("item_id", "=", self.id) & fields.Domain("value_hash", "=", key), limit=1)
        if old:
            return old
        return model.create({"item_id": self.id, "provider_id": provider.id if provider else False, "field_name": field, "value": value,
                             "content_kind": kind, "source_record_id": record.get("source_id") or str(self.product_id.ab_product_id.id),
                             "source_version": record.get("source_version") or str(self.product_id.ab_product_id.write_date),
                             "source_url": record.get("source_url") or (provider.official_url if provider else ""),
                             "source_type": provider.provider_type if provider else "INTERNAL_CATALOG",
                             "matched_by": matching.get("matched_by", "internal_id"), "matched_identifier": matching.get("matched_identifier"),
                             "match_score": matching.get("match_score", 1.0), "accepted": accepted,
                             "retrieved_at": record.get("retrieved_at") or fields.Datetime.now(),
                             "verified_at": fields.Datetime.now() if accepted else False,
                             "source_metadata": dict(provider.metadata, checksum=record.get("checksum")) if provider else {"authority": "internal_catalog"},
                             "value_hash": key, "lang_code": lang, "model_name": generation.get("model"), "prompt_version": generation.get("prompt_version"),
                             "input_sources": generation.get("input_sources")})

    def _collect_facts(self, identity, pipeline):
        facts = {k: v for k, v in identity.items() if k in ("name", "name_ar", "manufacturer", "brand", "active_ingredients", "strength", "dosage_form", "package", "product_code") and v}
        provenance = []
        for key, value in facts.items():
            provenance.append(self._evidence(key, value, accepted=True).id)
        for provider in pipeline._providers():
            provider = provider.with_context(enrichment_job_id=self.job_id.id, enrichment_product_id=self.product_id.id)
            spec = CATALOG[provider.provider]
            if pipeline.domain not in spec["domain"].split(","):
                continue
            if not provider._allowed_for_commercial():
                provider._call_log("skip", time.monotonic(), error="license_review_required")
                continue
            lookups = [dict(identity, source_id=(identity.get("source_ids") or {}).get(provider.provider))]
            if provider.source_scope == "ingredient":
                ingredient = facts.get("active_ingredients") or facts.get("ingredients")
                if isinstance(ingredient, str):
                    ingredients = [v.strip() for v in re.split(r"[+,;]", ingredient) if v.strip()]
                elif isinstance(ingredient, list):
                    ingredients = [v.get("name") for v in ingredient if isinstance(v, dict) and v.get("name")]
                else:
                    ingredients = []
                lookups = [{"name": v, "ingredient_name": v} for v in ingredients[:20]]
            for lookup in lookups:
                try:
                    candidates = provider._lookup(lookup)
                except ProviderFailure as error:
                    provider._call_log("fallback", time.monotonic(), error=error.code)
                    continue
                ranked = sorted(((match(lookup, row), row) for row in candidates), key=lambda x: x[0]["match_score"], reverse=True)
                if not ranked:
                    continue
                if provider.source_scope == "normalization":
                    for matching, row in ranked:
                        self._evidence("normalization_context", row["facts"], provider, row, matching, False)
                    continue
                matching, row = ranked[0]
                ambiguous = len(ranked) > 1 and ranked[1][0]["match_score"] == matching["match_score"] and ranked[1][1]["source_id"] != row["source_id"]
                trusted = matching["match_score"] >= .95 and not ambiguous and provider.source_scope == "product"
                if spec.get("mode") == "manual":
                    dataset = self.env["ab_seo_dataset"].browse(row.get("dataset_id")).exists()
                    trusted = trusted and bool(dataset.manual_verified_at)
                for key, value in row.get("facts", {}).items():
                    accept = trusted and key not in facts and key in FACT_KEYS
                    if key in MEDICAL | {"directions", "suitable_for", "storage"} and (spec["market_relevance"] != "egypt" or spec["authority"] not in ("regulatory", "official")):
                        accept = False
                    evidence = self._evidence(key, value, provider, row, matching, accept,
                                              kind="UNVERIFIED_TEXT" if key == "unverified_context" or matching["match_score"] < .95 else "SOURCE_FACT")
                    if accept:
                        facts[key] = value
                        provenance.append(evidence.id)
        return facts, provenance

    def _conservative_content(self, identity, lang):
        name = identity["name"]
        description = self.with_context(lang=lang).env._("Product information for %s.", name)
        return {"meta_title": name, "meta_description": description, "short_description": description,
                "public_description": "<p>%s</p>" % html_escape(description), "keyword_text": name,
                "seo_name": name, "search_phrases": [name], "bullets": [], "content_source": "internal",
                "content_kind": "SOURCE_FACT", "review_required": True, "prompt_version": "conservative_v1"}

    def _process(self):
        self.ensure_one()
        template = self.product_id
        if not template.active or not template.sale_ok or not template.is_published or not template.ab_product_id:
            self.state = "skipped"
            return
        if self.job_id._template_should_skip(template) or (self.job_id.only_missing_seo and not self.job_id._product_needs_seo(template)):
            self.state = "skipped"
            return
        pipeline = self._select_pipeline()
        if not pipeline:
            raise ValidationError(_("Configure an active enrichment pipeline for this product type."))
        self.pipeline_id = pipeline
        self.state = "processing"
        identity = self._identity()
        facts, provenance = self._collect_facts(identity, pipeline)
        template_hash = self._prepare_template(facts, provenance, pipeline)
        input_hash = digest([identity, facts, provenance, pipeline.prompt_version, template_hash])
        outputs = dict(self.result or {}) if not self.normalized_input_hash or self.normalized_input_hash == input_hash else {}
        for lang in self.job_id._get_selected_lang_codes():
            if lang in outputs:
                continue
            if (self.job_id.regeneration_mode == "missing" and not self.job_id._template_language_missing(template, lang)) or (self.job_id.only_missing_seo and self.job_id._has_complete_native_seo(template, lang)):
                continue
            content = self._template_content(facts, lang)
            content["input_sources"] = provenance
            generate = pipeline.ai_mode == "always" or (pipeline.ai_mode == "missing" and not self.job_id._has_complete_native_seo(template, lang))
            if generate and self.job_id.generation_mode == "ai" and len(facts) > 2:
                success = False
                failures = []
                for provider in pipeline._providers(generation=True):
                    provider = provider.with_context(enrichment_job_id=self.job_id.id, enrichment_product_id=template.id)
                    if not provider._allowed_for_commercial():
                        provider._call_log("skip", time.monotonic(), error="license_review_required")
                        continue
                    try:
                        content = provider._generate_grounded(identity["name"], lang, facts, provenance, self.template_snapshot[lang]["prompt_version"], contract=self.template_snapshot[lang], category_context=self.category_context)
                        report = self._validate_template_output(content, lang)
                        if report["errors"]:
                            raise ProviderFailure("template_validation_failed")
                        success = True
                        break
                    except ProviderFailure as error:
                        failures.append((error.code, provider.disabled_until))
                        provider._call_log("fallback", time.monotonic(), error=error.code)
                if not success and pipeline._providers(generation=True):
                    recoverable = {"quota_exhausted", "rate_limit", "cooldown", "provider_busy", "timeout", "network_error", "temporary_failure"}
                    retry_times = [until for code, until in failures if code in recoverable and until]
                    waiting = self.attempts < 8 and (bool(retry_times) or any(code in recoverable for code, until in failures))
                    next_attempt = max(fields.Datetime.now() + timedelta(seconds=60), min(retry_times)) if retry_times else fields.Datetime.now() + timedelta(seconds=min(3600, 60 * 2 ** min(self.attempts, 6)))
                    self.sudo().write({"state": "waiting" if waiting else "failed", "attempts": self.attempts + 1,
                                "last_error": "all_generators_unavailable", "next_attempt_at": next_attempt,
                                "result": outputs, "normalized_input_hash": input_hash})
                    return
            self._validate_template_output(content, lang)
            content["source_summary"] = _("Enrichment draft; verify source evidence before approval.")
            outputs[lang] = content
            provider = self.env["ab.seo.assistant"].browse(content.get("provider_id")).exists()
            for field in SEO_FIELDS:
                if content.get(field):
                    self._evidence(field, content[field], provider=provider, accepted=False,
                                   kind=content.get("content_kind", "GENERATED_TEXT"), lang=lang, generation=content)
        seo = self.job_id._get_or_create_product_seo(template)
        self._save_template_metadata(self.env["ab.product.seo"], outputs)
        if self.validation_status == "rejected":
            self.sudo().write({"state": "failed", "result": outputs, "seo_id": seo.id, "last_error": "template_validation_failed"})
            return
        if seo.state in ("under_review", "approved", "published"):
            self.sudo().write({"state": "review_required", "result": outputs, "seo_id": seo.id, "last_error": "existing_review_preserved"})
            return
        self._save_outputs(seo, outputs)
        self.sudo().write({"state": "review_required", "result": outputs, "seo_id": seo.id, "normalized_input_hash": input_hash, "last_error": False})

    def _save_outputs(self, seo, outputs):
        for translation in seo.translation_ids:
            content = outputs.get(translation.lang_code)
            if not content:
                continue
            translation.sudo()._apply_generated_content(content)
            translation.sudo().write({"enrichment_item_id": self.id, "review_required": True, "search_phrases": content.get("search_phrases", []),
                               "structured_bullets": content.get("bullets", []), "prompt_version": content.get("prompt_version"),
                               "reviewed_by": False, "reviewed_at": False})
        seo.write({"state": "generated", "last_bulk_id": self.job_id.id, "result_message": _("Enrichment drafts are ready for review."), "result_status": "optimized"})
        self._save_template_metadata(seo, outputs)


class EnrichmentBulk(models.Model):
    _inherit = "ab.product.seo.bulk.optimization"

    enrichment_enabled = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, index=True)
    pipeline_id = fields.Many2one("ab_seo_pipeline", ondelete="restrict")
    work_item_ids = fields.One2many("ab_seo_work_item", "job_id", readonly=True)
    discovery_cursor = fields.Integer(readonly=True)
    discovery_max_id = fields.Integer(readonly=True)
    discovery_done = fields.Boolean(readonly=True)
    total_count = fields.Integer(readonly=True)
    queued_count = fields.Integer(compute="_compute_enrichment_progress")
    processing_count = fields.Integer(compute="_compute_enrichment_progress")
    review_required_count = fields.Integer(compute="_compute_enrichment_progress")
    provider_exhausted_count = fields.Integer(compute="_compute_enrichment_progress")
    provider_progress = fields.Json(compute="_compute_enrichment_progress")
    items_per_tick = fields.Integer(default=50)

    @api.constrains("items_per_tick")
    def _check_items_per_tick(self):
        if any(not 1 <= rec.items_per_tick <= 1000 for rec in self):
            raise ValidationError(_("Items per tick must be between 1 and 1,000."))

    def _compute_enrichment_progress(self):
        for job in self:
            groups = self.env["ab_seo_work_item"]._read_group(fields.Domain("job_id", "=", job.id), ["state"], ["__count"])
            counts = dict(groups)
            job.queued_count = counts.get("queued", 0) + counts.get("waiting", 0)
            job.processing_count = counts.get("processing", 0)
            job.review_required_count = counts.get("review_required", 0)
            calls = self.env["ab_seo_provider_call"]._read_group(fields.Domain("job_id", "=", job.id), ["provider_id", "success", "error_type"], ["__count"])
            progress = {}
            exhausted = 0
            for provider, success, error, count in calls:
                bucket = progress.setdefault(str(provider.id), {"provider": provider.name, "success": 0, "fail": 0, "quota": 0, "processed": 0})
                bucket["processed"] += count
                bucket["success" if success else "fail"] += count
                if error in ("quota_exhausted", "rate_limit"):
                    bucket["quota"] += count
                    exhausted += count
            job.provider_exhausted_count = exhausted
            job.provider_progress = progress

    def _enrichment_domain(self):
        domain = fields.Domain("is_published", "=", True) & fields.Domain("sale_ok", "=", True) & fields.Domain("active", "=", True) & fields.Domain("ab_product_id", "!=", False)
        domain &= fields.Domain("company_id", "in", [False, self.company_id.id])
        if self.website_id:
            domain &= fields.Domain("website_id", "in", [False, self.website_id.id])
        return domain

    def _enqueue_bulk_optimization(self):
        if not self.enrichment_enabled:
            if self.assistant_id:
                raise UserError(_("External providers require the enrichment draft pipeline."))
            return super()._enqueue_bulk_optimization()
        self.ensure_one()
        if self.target != "products":
            raise UserError(_("Select Published Products for the enrichment pipeline. Existing page optimization remains available with enrichment disabled."))
        if self.batch_limit <= 0:
            raise ValidationError(_("Batch limit must be greater than zero."))
        if self.env["ab_seo_work_item"].search_count(fields.Domain("job_id", "=", self.id), limit=1) or self.state in ("queued", "running"):
            raise UserError(_("Use Resume Job to continue this run, or create a new run."))
        template = self.env["product.template"].search(self._enrichment_domain(), order="id desc", limit=1)
        self.write({"state": "queued", "discovery_cursor": 0, "discovery_max_id": template.id or 0,
                    "total_count": min(self.batch_limit, self.env["product.template"].search_count(self._enrichment_domain())),
                    "started_at": fields.Datetime.now(), "finished_at": False})
        return True

    def action_resume_job(self):
        self._require_manager()
        for job in self:
            if not job.try_lock_for_update():
                continue
            self.env["ab_seo_work_item"].search(fields.Domain("job_id", "=", job.id) & fields.Domain("state", "=", "processing")).write({"state": "queued"})
            job.write({"state": "queued", "finished_at": False})
        return True

    def action_retry_failures(self):
        self._require_manager()
        for job in self:
            if not job.try_lock_for_update():
                continue
            self.env["ab_seo_work_item"].search(fields.Domain("job_id", "=", job.id) & fields.Domain("state", "in", ("failed", "waiting"))).write({"state": "queued", "attempts": 0, "next_attempt_at": False})
            job.write({"state": "queued", "finished_at": False})
        return True

    def _discover_chunk(self, limit=500):
        self.ensure_one()
        if self.discovery_done:
            return
        work = self.env["ab_seo_work_item"]
        remaining = self.batch_limit - work.search_count(fields.Domain("job_id", "=", self.id))
        templates = self.env["product.template"].search(self._enrichment_domain() & fields.Domain("id", ">", self.discovery_cursor) & fields.Domain("id", "<=", self.discovery_max_id), order="id", limit=min(limit, max(remaining, 0))) if remaining > 0 else self.env["product.template"]
        if templates:
            work.create([{"job_id": self.id, "product_id": t.id} for t in templates])
            self.discovery_cursor = templates[-1].id
        if not templates or len(templates) < limit or remaining <= limit:
            self.discovery_done = True
            self.total_count = work.search_count(fields.Domain("job_id", "=", self.id))

    def _run_bulk_optimization_chunk(self):
        if not self.enrichment_enabled:
            return super()._run_bulk_optimization_chunk()
        self.ensure_one()
        if not self.try_lock_for_update():
            return True
        self.invalidate_recordset()
        if self.state not in ("queued", "running"):
            return True
        self.state = "running"
        self._discover_chunk()
        work = self.env["ab_seo_work_item"]
        domain = fields.Domain("job_id", "=", self.id)
        now = fields.Datetime.now()
        item = work.search(domain & fields.Domain("state", "in", ("queued", "waiting")) & (fields.Domain("next_attempt_at", "=", False) | fields.Domain("next_attempt_at", "<=", now)), order="id", limit=1)
        if item and item.try_lock_for_update():
            item.with_company(self.company_id)._process()
        counts = dict(work._read_group(domain, ["state"], ["__count"]))
        finished = not any(counts.get(k) for k in ("queued", "waiting", "processing")) and self.discovery_done
        self.write({"processed_count": sum(counts.get(k, 0) for k in ("done", "failed", "skipped", "review_required")),
                    "optimized_count": counts.get("done", 0) + counts.get("review_required", 0), "skipped_count": counts.get("skipped", 0),
                    "error_count": counts.get("failed", 0), "state": "done" if finished else "queued", "finished_at": now if finished else False})
        return True

    @api.model
    def _cron_run_queued_bulk_optimizations(self, limit=1):
        jobs = self.search(fields.Domain("state", "in", ("queued", "running")), order="id", limit=limit)
        for job in jobs:
            deadline = time.monotonic() + 45
            for _index in range(job.items_per_tick if job.enrichment_enabled else 1):
                before = job.processed_count
                try:
                    with self.env.cr.savepoint():
                        job._run_bulk_optimization_chunk()
                except Exception as error:
                    _logger.exception("SEO job architecture failure job_id=%s type=%s", job.id, type(error).__name__)
                    job.write({"state": "failed", "finished_at": fields.Datetime.now()})
                    job._create_line("error", _("Job stopped because of a server error: %s") % type(error).__name__)
                if self.env.context.get("cron_id") and not self.env["ir.cron"]._commit_progress(1):
                    break
                if job.state not in ("queued", "running") or job.processed_count == before or time.monotonic() >= deadline:
                    break
        return True


class EnrichmentProduct(models.Model):
    _inherit = "product.template"

    ab_enrichment_domain = fields.Selection(DOMAINS, default="auto", groups=MANAGER)
    ab_enrichment_identity = fields.Json(groups=MANAGER)


class EnrichmentSeo(models.Model):
    _inherit = "ab.product.seo"

    def write(self, vals):
        if vals.get("state") in ("approved", "published") and self.translation_ids.filtered("enrichment_item_id"):
            self._require_group("ab_website_seo_optimization.group_ab_website_seo_optimization_reviewer")
            if self.translation_ids.filtered(lambda row: row.enrichment_item_id and row.review_required):
                raise ValidationError(_("Review the enrichment evidence for each generated translation before approval."))
        return super().write(vals)

    def _optimize_single_published_product(self):
        self._require_group(MANAGER)
        self.ensure_one()
        if not self.env.context.get("legacy_internal_seo"):
            job = self.env["ab.product.seo.bulk.optimization"].create({"name": self.name, "website_id": self.website_id.id,
                  "company_id": self.company_id.id or self.env.company.id, "lang_mode": self.lang_mode, "batch_limit": 1,
                  "enrichment_enabled": True, "generation_mode": self.template_generation_mode,
                  "regeneration_mode": "selected" if self.env.context.get("force_seo_optimization") or not self.only_missing_seo else "missing",
                  "only_missing_seo": self.only_missing_seo and not self.env.context.get("force_seo_optimization"),
                  "discovery_done": True, "total_count": 1, "state": "queued", "started_at": fields.Datetime.now()})
            self.env["ab_seo_work_item"].create({"job_id": job.id, "product_id": self.product_template_id.id})
            self.last_bulk_id = job
            return job
        if self.assistant_id:
            raise UserError(_("External providers require the enrichment draft pipeline."))
        return super()._optimize_single_published_product()

    def action_approve(self):
        for seo in self:
            if seo.translation_ids.filtered(lambda t: t.enrichment_item_id and t.review_required):
                raise ValidationError(_("Review the enrichment evidence for each generated translation before approval."))
        return super().action_approve()

    def _publish_versions(self, force=False, publish_description=True):
        for seo in self:
            if seo.translation_ids.filtered(lambda t: t.enrichment_item_id and t.review_required):
                raise ValidationError(_("Review the enrichment evidence for each generated translation before publishing."))
        return super()._publish_versions(force, publish_description)


class EnrichmentTranslation(models.Model):
    _inherit = "ab.product.seo.translation"

    enrichment_item_id = fields.Many2one("ab_seo_work_item", readonly=True, ondelete="restrict")
    review_required = fields.Boolean(default=False, readonly=True)
    reviewed_by = fields.Many2one("res.users", readonly=True)
    reviewed_at = fields.Datetime(readonly=True)
    prompt_version = fields.Char(readonly=True)
    search_phrases = fields.Json()
    structured_bullets = fields.Json()

    def action_review_evidence(self):
        if not self.env.user.has_group("ab_website_seo_optimization.group_ab_website_seo_optimization_reviewer"):
            raise AccessError(_("Only SEO reviewers can confirm enrichment evidence."))
        for rec in self:
            if not rec.review_notes:
                raise ValidationError(_("Record the evidence checked and corrections made in review notes."))
            super(EnrichmentTranslation, rec).write({"review_required": False, "reviewed_by": self.env.user.id, "reviewed_at": fields.Datetime.now()})
        return True

    def write(self, vals):
        if not self.env.su and {"review_required", "reviewed_by", "reviewed_at"} & set(vals):
            raise AccessError(_("Use the evidence review action to confirm a translation."))
        if set(vals) & set(SEO_FIELDS) and self.filtered("enrichment_item_id"):
            vals = dict(vals, review_required=True, reviewed_by=False, reviewed_at=False)
        return super().write(vals)

    def _create_version(self):
        version = super()._create_version()
        if self.enrichment_item_id:
            version.sudo().write({"enrichment_provenance": {"item_id": self.enrichment_item_id.id, "facts": self.enrichment_item_id.fact_ids.ids,
                                  "prompt_version": self.prompt_version, "reviewed_by": self.reviewed_by.id, "reviewed_at": str(self.reviewed_at)}})
        return version


class EnrichmentVersion(models.Model):
    _inherit = "ab.product.seo.version"

    enrichment_provenance = fields.Json(readonly=True)

    def write(self, vals):
        if "enrichment_provenance" in vals and (not self.env.su or self.filtered("enrichment_provenance")):
            raise UserError(_("Enrichment audit records are immutable."))
        return super().write(vals)
