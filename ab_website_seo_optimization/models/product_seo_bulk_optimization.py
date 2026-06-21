import re
import time

from odoo import _, api, fields, models
from odoo.addons.website.tools import text_from_html
from odoo.exceptions import UserError
from odoo.tools import html_escape

from .product_seo import SEO_LANGUAGES


class AbProductSeoBulkOptimization(models.Model):
    _name = "ab.product.seo.bulk.optimization"
    _description = "Bulk Website SEO Optimization"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, default=lambda self: _("Bulk Website SEO Optimization"))
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("queued", "Queued"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    target = fields.Selection(
        [
            ("products", "Published Products"),
            ("pages", "Published Pages"),
            ("all", "Published Products + Pages"),
        ],
        default="products",
        required=True,
    )
    website_id = fields.Many2one("website", string="Website")
    assistant_id = fields.Many2one("ab.seo.assistant", string="SEO Assistant")
    lang_mode = fields.Selection(
        [("all", "Arabic + English")] + SEO_LANGUAGES,
        string="Languages",
        default="all",
        required=True,
    )
    batch_limit = fields.Integer(default=100, required=True)
    only_missing_seo = fields.Boolean(
        default=False,
        help="Skip products that already have title, description, keywords, and page content in the selected language.",
    )
    publish_description = fields.Boolean(default=True)
    generate_drug_data = fields.Boolean(
        default=False,
        help="Deprecated. Drug-EG API data is now stored as a catalog cache and is not generated into product pages.",
    )
    request_delay_seconds = fields.Float(
        string="Delay Between Products",
        default=0.0,
        help="Optional wait time after each processed product or page. Use this for assistants with strict rate limits.",
    )
    rate_limit_retry_count = fields.Integer(
        default=3,
        help="How many times to retry the same product when the assistant returns a rate-limit error.",
    )
    rate_limit_wait_seconds = fields.Integer(
        default=60,
        help="How long to wait before retrying after a rate-limit error.",
    )
    compact_assistant_context = fields.Boolean(
        default=True,
        help="Send only compact product context to AI assistants to reduce token usage.",
    )
    processed_count = fields.Integer(readonly=True)
    optimized_count = fields.Integer(readonly=True)
    skipped_count = fields.Integer(readonly=True)
    error_count = fields.Integer(readonly=True)
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    line_ids = fields.One2many(
        "ab.product.seo.bulk.optimization.line",
        "bulk_id",
        domain=[("active", "=", True)],
        readonly=True,
    )

    def unlink(self):
        raise UserError(_("Bulk SEO optimization runs must be archived instead of deleted."))

    def action_fill_with_ai_for_published_products(self):
        self._require_manager()
        for run in self:
            run._enqueue_bulk_optimization()
        if len(self) == 1:
            return self._get_form_reload_action()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk SEO Optimization Queued"),
                "message": _("The bulk optimization is running in the background. Refresh this record to follow progress."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_process_next_chunk(self):
        self._require_manager()
        for run in self:
            if run.state not in ("queued", "running"):
                raise UserError(_("Only queued or running bulk optimizations can process the next chunk."))
            run._run_bulk_optimization_chunk()
        if len(self) == 1:
            return self._get_form_reload_action()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Bulk SEO Chunk Processed"),
                "message": _("One chunk was processed. Refresh this record to see the latest counters and logs."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_stop(self):
        return self.action_cancel_batch()

    def action_cancel_batch(self):
        self._require_manager()
        for run in self.filtered(lambda rec: rec.state in ("draft", "queued", "running")):
            run.write({
                "state": "cancelled",
                "finished_at": fields.Datetime.now(),
            })
            run._create_line("cancelled", _("Bulk optimization batch was cancelled manually."))
        if len(self) == 1:
            return self._get_form_reload_action()
        return True

    def _get_form_reload_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bulk Website SEO Optimization"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _enqueue_bulk_optimization(self):
        self.ensure_one()
        if self.state in ("queued", "running"):
            raise UserError(_("This bulk optimization is already running."))
        self.write({
            "state": "queued",
            "processed_count": 0,
            "optimized_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "started_at": False,
            "finished_at": False,
        })
        self.line_ids.write({"active": False})
        self.message_post(body=_("Bulk SEO optimization was queued for background processing."))
        return True

    @api.model
    def _cron_run_queued_bulk_optimizations(self, limit=1):
        runs = self.sudo().search([("state", "in", ("queued", "running")), ("active", "=", True)], limit=limit, order="id")
        for run in runs:
            try:
                with self.env.cr.savepoint():
                    run._run_bulk_optimization_chunk()
            except Exception as error:
                run.write({
                    "state": "failed",
                    "error_count": run.error_count + 1,
                    "finished_at": fields.Datetime.now(),
                })
                run._create_line("error", str(error))
        return True

    def _require_manager(self):
        if not self.env.user.has_group("ab_website_seo_optimization.group_ab_website_seo_optimization_manager"):
            raise UserError(_("Only SEO managers can run bulk SEO optimization."))

    def _run_bulk_optimization(self):
        self.ensure_one()
        previous_processed = -1
        while self.state not in ("done", "failed", "cancelled"):
            self._run_bulk_optimization_chunk()
            if self.state == "queued" and self.processed_count == previous_processed:
                break
            previous_processed = self.processed_count
        return True

    def _run_bulk_optimization_chunk(self):
        self.ensure_one()
        if self.batch_limit <= 0:
            raise UserError(_("Batch limit must be greater than zero."))
        if not self.started_at:
            self.started_at = fields.Datetime.now()
        self.state = "running"
        remaining = max(self.batch_limit - self.processed_count, 0)
        if not remaining:
            self._finish_bulk_optimization()
            return True
        chunk_limit = min(self._get_cron_chunk_size(), remaining)
        templates = self._get_published_products(limit=chunk_limit) if self.target in ("products", "all") else self.env["product.template"]
        remaining_after_products = chunk_limit - len(templates)
        pages = self.env["website.page"]
        if remaining_after_products and self.target in ("pages", "all"):
            pages = self._get_published_pages(limit=remaining_after_products)
        if not templates and not pages:
            self._finish_bulk_optimization()
            return True
        counters = {"processed": 0, "optimized": 0, "skipped": 0, "errors": 0, "deferred": 0}
        for template in templates:
            result = self._run_record_with_retries(lambda: self._optimize_template(template), template=template)
            counters[result] += 1
            if result != "deferred":
                counters["processed"] += 1
            self._sleep_between_records()
        for page in pages:
            result = self._run_record_with_retries(lambda: self._optimize_page(page), page=page)
            counters[result] += 1
            if result != "deferred":
                counters["processed"] += 1
            self._sleep_between_records()
        values = {
            "processed_count": self.processed_count + counters["processed"],
            "optimized_count": self.optimized_count + counters["optimized"],
            "skipped_count": self.skipped_count + counters["skipped"],
            "error_count": self.error_count + counters["errors"],
        }
        self.write(values)
        if self.processed_count >= self.batch_limit:
            self._finish_bulk_optimization()
        else:
            has_more_products = bool(self._get_published_products(limit=1)) if self.target in ("products", "all") else False
            has_more_pages = bool(self._get_published_pages(limit=1)) if self.target in ("pages", "all") else False
            if has_more_products or has_more_pages:
                self.state = "queued"
            else:
                self._finish_bulk_optimization()
        return True

    def _run_single_template_optimization(self, template):
        self.ensure_one()
        if self.batch_limit <= 0:
            self.batch_limit = 1
        if not self.started_at:
            self.started_at = fields.Datetime.now()
        self.state = "running"
        result = self._run_record_with_retries(lambda: self._optimize_template(template), template=template)
        counters = {
            "optimized": 1 if result == "optimized" else 0,
            "skipped": 1 if result == "skipped" else 0,
            "errors": 1 if result == "errors" else 0,
            "processed": 0 if result == "deferred" else 1,
        }
        self.write({
            "processed_count": self.processed_count + counters["processed"],
            "optimized_count": self.optimized_count + counters["optimized"],
            "skipped_count": self.skipped_count + counters["skipped"],
            "error_count": self.error_count + counters["errors"],
        })
        self._finish_bulk_optimization()
        return result

    def _get_cron_chunk_size(self):
        self.ensure_one()
        if self.assistant_id:
            return 1
        return 5

    def _finish_bulk_optimization(self):
        self.ensure_one()
        self.write({
            "state": "failed" if self.error_count and not self.optimized_count else "done",
            "finished_at": fields.Datetime.now(),
        })
        return True

    def _run_record_with_retries(self, operation, template=False, page=False):
        self.ensure_one()
        max_attempts = max(self.rate_limit_retry_count or 0, 0) + 1
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                with self.env.cr.savepoint():
                    return operation()
            except Exception as error:
                message = str(error)
                if self._is_rate_limit_error(message):
                    self._create_or_update_deferred_line(
                        _("Rate limit while optimizing %(record)s. The record was deferred and will be retried by the next cron tick.") % {
                            "record": self._get_record_reference(template=template, page=page),
                        },
                        template=template,
                        page=page,
                    )
                    return "deferred"
                self._create_line("error", message, template=template, page=page)
                return "errors"
        self._create_line(
            "error",
            _("Rate limit retry attempts were exhausted."),
            template=template,
            page=page,
        )
        return "errors"

    def _is_rate_limit_error(self, message):
        normalized = (message or "").lower()
        return "rate limit" in normalized or "429" in normalized

    def _sleep_between_records(self):
        self.ensure_one()
        if not self.assistant_id:
            return
        if self.request_delay_seconds and self.request_delay_seconds > 0:
            time.sleep(self.request_delay_seconds)

    def _sleep_for_rate_limit(self):
        self.ensure_one()
        if self.rate_limit_wait_seconds and self.rate_limit_wait_seconds > 0:
            time.sleep(self.rate_limit_wait_seconds)

    def _get_published_products(self, limit=None):
        self.ensure_one()
        processed_ids = self._get_processed_product_template_ids()
        requested_limit = limit or self.batch_limit
        domain = [
            ("is_published", "=", True),
            ("sale_ok", "=", True),
            ("active", "=", True),
            ("ab_product_id", "!=", False),
        ]
        if processed_ids:
            domain.append(("id", "not in", processed_ids))
        ProductTemplate = self.env["product.template"].sudo()
        if not self.only_missing_seo:
            return ProductTemplate.search(domain, limit=requested_limit, order="id desc")
        return self._search_missing_seo_records(
            ProductTemplate,
            domain,
            requested_limit,
            self._product_needs_seo,
        )

    def _get_published_pages(self, limit=None):
        self.ensure_one()
        processed_ids = self._get_processed_website_page_ids()
        requested_limit = limit or self.batch_limit
        domain = [
            ("is_published", "=", True),
            ("website_indexed", "=", True),
        ]
        if self.website_id:
            domain.append(("website_id", "=", self.website_id.id))
        if processed_ids:
            domain.append(("id", "not in", processed_ids))
        WebsitePage = self.env["website.page"].sudo()
        if not self.only_missing_seo:
            return WebsitePage.search(domain, limit=requested_limit, order="id desc")
        return self._search_missing_seo_records(
            WebsitePage,
            domain,
            requested_limit,
            self._page_needs_seo,
        )

    def _search_missing_seo_records(self, model, domain, limit, needs_seo):
        self.ensure_one()
        records = model.browse()
        offset = 0
        search_limit = max((limit or 1) * 5, 50)
        while len(records) < limit:
            candidates = model.search(domain, limit=search_limit, offset=offset, order="id desc")
            if not candidates:
                break
            records |= candidates.filtered(needs_seo)
            offset += len(candidates)
        return records[:limit]

    def _product_needs_seo(self, template):
        self.ensure_one()
        return any(not self._has_complete_native_seo(template, lang_code) for lang_code in self._get_selected_lang_codes())

    def _page_needs_seo(self, page):
        self.ensure_one()
        return any(not self._has_complete_page_seo(page, lang_code) for lang_code in self._get_selected_lang_codes())

    def _get_processed_product_template_ids(self):
        self.ensure_one()
        return self.env["ab.product.seo.bulk.optimization.line"].sudo().search([
            ("bulk_id", "=", self.id),
            ("active", "=", True),
            ("product_template_id", "!=", False),
            ("status", "!=", "deferred"),
        ]).mapped("product_template_id").ids

    def _get_processed_website_page_ids(self):
        self.ensure_one()
        return self.env["ab.product.seo.bulk.optimization.line"].sudo().search([
            ("bulk_id", "=", self.id),
            ("active", "=", True),
            ("website_page_id", "!=", False),
            ("status", "!=", "deferred"),
        ]).mapped("website_page_id").ids

    def _optimize_template(self, template):
        self.ensure_one()
        if not template.ab_product_id:
            self._create_line("skipped", _("Published product is not linked to an Abdin product."), template=template)
            return "skipped"
        lang_codes = self._get_selected_lang_codes()
        if not lang_codes:
            self._create_line("skipped", _("No matching SEO language was found."), template=template)
            return "skipped"
        generated_content_by_lang = {}
        optimized = False
        data_source_content = False
        for lang_code in lang_codes:
            if self.only_missing_seo and self._has_complete_native_seo(template, lang_code):
                continue
            if self.assistant_id:
                if self.assistant_id.assistant_type == "data_source":
                    if not data_source_content:
                        data_source_content = self._generate_assistant_product_content(template, lang_code)
                    content = data_source_content
                else:
                    content = self._generate_assistant_product_content(template, lang_code)
            else:
                content = self._generate_internal_product_content(template, lang_code)
            generated_content_by_lang[lang_code] = content
            self._write_native_product_seo(template, content, lang_code)
            optimized = True
        if not optimized:
            self._create_line("skipped", _("Native SEO fields are already complete."), template=template)
            return "skipped"
        self._create_line("optimized", _("SEO fields were generated and published."), template=template)
        return "optimized"

    def _optimize_page(self, page):
        self.ensure_one()
        lang_codes = self._get_selected_lang_codes()
        optimized = False
        for lang_code in lang_codes:
            if self.only_missing_seo and self._has_complete_page_seo(page, lang_code):
                continue
            vals = self._generate_page_seo_values(page, lang_code)
            page.with_context(lang=lang_code).sudo().write(vals)
            optimized = True
        if not optimized:
            self._create_line("skipped", _("Native page SEO fields are already complete."), page=page)
            return "skipped"
        self._create_line("optimized", _("Page SEO fields were generated and published."), page=page)
        return "optimized"

    def _get_or_create_product_seo(self, template):
        self.ensure_one()
        Seo = self.env["ab.product.seo"].sudo()
        domain = [("ab_product_id", "=", template.ab_product_id.id), ("active", "=", True)]
        if self.website_id:
            domain.append(("website_id", "=", self.website_id.id))
        else:
            domain.append(("website_id", "=", False))
        seo = Seo.search(domain, limit=1)
        if seo:
            if seo.product_template_id != template:
                seo.product_template_id = template.id
            return seo
        return Seo.create({
            "ab_product_id": template.ab_product_id.id,
            "product_template_id": template.id,
            "website_id": self.website_id.id,
        })

    def _get_selected_translations(self, seo):
        self.ensure_one()
        if self.lang_mode == "all":
            return seo.translation_ids
        return seo.translation_ids.filtered(lambda translation: translation.lang_code == self.lang_mode)

    def _get_selected_lang_codes(self):
        self.ensure_one()
        if self.lang_mode == "all":
            return [lang_code for lang_code, _label in SEO_LANGUAGES]
        return [self.lang_mode]

    def _has_complete_native_seo(self, template, lang_code):
        self.ensure_one()
        context = {"lang": lang_code}
        if self.website_id:
            context["website_id"] = self.website_id.id
        localized = template.with_context(**context)
        return bool(
            localized.website_meta_title
            and localized.website_meta_description
            and localized.website_meta_keywords
            and (not self.publish_description or localized.description_ecommerce)
        )

    def _has_complete_page_seo(self, page, lang_code):
        self.ensure_one()
        localized = page.with_context(lang=lang_code)
        return bool(
            localized.website_meta_title
            and localized.website_meta_description
            and localized.website_meta_keywords
        )

    def _generate_page_seo_values(self, page, lang_code):
        self.ensure_one()
        localized = page.with_context(lang=lang_code).sudo()
        page_name = localized.name or localized.url or _("Website Page")
        page_text = self._extract_page_text(localized)
        title = localized.website_meta_title or page_name
        description = self._extract_page_description(page_text, localized.website_meta_description or page_name)
        keywords = localized.website_meta_keywords or self._extract_page_keywords("%s %s" % (page_name, page_text))
        return {
            "website_meta_title": str(title)[:70],
            "website_meta_description": str(description)[:160],
            "website_meta_keywords": keywords[:255],
        }

    def _extract_page_text(self, page):
        arch = page.arch or page.view_id.arch_db or ""
        text = text_from_html(arch) or ""
        return re.sub(r"\s+", " ", text).strip()

    def _extract_page_description(self, page_text, fallback):
        if page_text:
            return page_text[:160]
        return fallback or ""

    def _extract_page_keywords(self, text):
        words = re.findall(r"[\w\u0600-\u06FF]{3,}", text or "")
        seen = []
        for word in words:
            clean_word = word.strip().lower()
            if clean_word and clean_word not in seen:
                seen.append(clean_word)
            if len(seen) >= 7:
                break
        return ", ".join(seen)

    def _publish_generated_versions(self, seo, versions):
        self.ensure_one()
        Log = self.env["ab.product.seo.publish.log"].sudo()
        for version in versions:
            seo._publish_version(version, Log, publish_description=self.publish_description)
        seo.write({
            "state": "published",
            "current_version_id": versions[-1].id,
            "published_version_id": versions[-1].id,
            "last_published_at": fields.Datetime.now(),
            "last_published_by": self.env.user.id,
            "has_conflict": False,
            "conflict_note": False,
        })

    def _generate_assistant_product_content(self, template, lang_code):
        self.ensure_one()
        product_name = self._get_product_name_for_generation(template)
        context = self._get_product_generation_context(template)
        if self.compact_assistant_context:
            context = self._compact_generation_context(context)
        return self.assistant_id.generate_product_content(product_name, lang_code, product_context=context)

    def _generate_internal_product_content(self, template, lang_code):
        self.ensure_one()
        product = template.ab_product_id.sudo()
        context = self._get_product_generation_context(template)
        product_name = self._get_product_name_for_generation(template)
        scientific = context.get("scientific_name") or context.get("effective_material") or ""
        manufacturer = context.get("manufacturer") or ""
        usage = context.get("usage_manner") or ""
        origin = context.get("origin") or ""
        notes = context.get("notes") or ""
        brand_name = _("Abdin Pharmacies")
        title_parts = [part for part in [product_name, scientific, brand_name] if part]
        description_parts = [
            _("Buy %(product)s from Abdin Pharmacies.") % {"product": product_name} if product_name else "",
            _("Manufacturer: %s.") % manufacturer if manufacturer else "",
            _("Scientific name: %s.") % scientific if scientific else "",
            _("Usage: %s.") % usage if usage else "",
        ]
        description = " ".join(part for part in description_parts if part).strip()
        public_description = notes or description
        return {
            "meta_title": " | ".join(title_parts[:3])[:255],
            "meta_description": description[:255],
            "keyword_text": ", ".join(part for part in [product_name, scientific, manufacturer, usage, origin] if part)[:255],
            "seo_name": product_name,
            "short_description": notes or description,
            "public_description": self._html_paragraph(public_description),
            "active_ingredient": product.effective_material or scientific,
            "content_source": "internal",
            "source_summary": _("Generated from internal product catalog."),
        }

    def _write_native_product_seo(self, template, content, lang_code):
        self.ensure_one()
        vals = {
            "website_meta_title": (content.get("meta_title") or "")[:255],
            "website_meta_description": (content.get("meta_description") or content.get("short_description") or "")[:255],
            "website_meta_keywords": (content.get("keyword_text") or content.get("keywords") or "")[:255],
            "seo_name": content.get("seo_name") or False,
        }
        if self.publish_description:
            public_description = content.get("public_description") or content.get("short_description") or content.get("meta_description")
            vals["description_ecommerce"] = public_description or False
            if "website_description" in template._fields:
                vals["website_description"] = public_description or False
        vals = {key: value for key, value in vals.items() if key in template._fields and value not in (None, "")}
        if vals:
            context = {"lang": lang_code}
            if self.website_id:
                context["website_id"] = self.website_id.id
            template.with_context(**context).sudo().write(vals)

    def _get_product_name_for_generation(self, template):
        product = template.ab_product_id.sudo()
        return product.name or product.product_card_name or template.name or product.code or ""

    def _get_product_generation_context(self, template):
        product = template.ab_product_id.sudo()
        return {
            "product_code": product.code or False,
            "eplus_serial": product.eplus_serial or False,
            "barcodes": ", ".join(product.barcode_ids.mapped("name")),
            "scientific_name": ", ".join(product.scientific_groups_ids.mapped("name")) or False,
            "manufacturer": product.company_id.name or False,
            "origin": product.origin_id.name or product.origin or False,
            "usage_manner": product.usage_manner_id.name or False,
            "effective_material": product.effective_material or False,
            "notes": product.description or template.description_sale or False,
            "group_path": " / ".join(product.groups_ids.mapped("name")),
        }

    def _compact_generation_context(self, context):
        compact = {}
        for key, value in (context or {}).items():
            if value in (None, False, "", 0):
                continue
            text = str(value).strip()
            if key in ("notes", "group_path") and len(text) > 300:
                text = text[:300]
            elif len(text) > 160:
                text = text[:160]
            compact[key] = text
        return compact

    @api.model
    def _html_paragraph(self, text):
        if not text:
            return False
        lines = str(html_escape(text)).splitlines() or [""]
        return "<p>%s</p>" % "<br/>".join(lines)

    def _create_line(self, status, message, template=False, page=False):
        self.ensure_one()
        self.env["ab.product.seo.bulk.optimization.line"].sudo().create({
            "bulk_id": self.id,
            "product_template_id": template.id if template else False,
            "ab_product_id": template.ab_product_id.id if template and template.ab_product_id else False,
            "website_page_id": page.id if page else False,
            "website_url": self._get_record_website_url(template=template, page=page),
            "status": status,
            "message": message,
        })

    def _create_or_update_deferred_line(self, message, template=False, page=False):
        self.ensure_one()
        Line = self.env["ab.product.seo.bulk.optimization.line"].sudo()
        domain = [
            ("bulk_id", "=", self.id),
            ("active", "=", True),
            ("status", "=", "deferred"),
        ]
        if template:
            domain.append(("product_template_id", "=", template.id))
        elif page:
            domain.append(("website_page_id", "=", page.id))
        line = Line.search(domain, limit=1)
        if line:
            line.message = message
        else:
            self._create_line("deferred", message, template=template, page=page)

    def _get_record_reference(self, template=False, page=False):
        if template:
            return template.display_name or _("Product")
        if page:
            return page.display_name or page.url or _("Website Page")
        return _("Record")

    def _get_record_website_url(self, template=False, page=False):
        if template:
            return getattr(template, "website_url", False) or False
        if page:
            return page.url or False
        return False

    def action_archive(self):
        self.write({"active": False})
        return True


class AbProductSeoBulkOptimizationLine(models.Model):
    _name = "ab.product.seo.bulk.optimization.line"
    _description = "Bulk Website SEO Optimization Line"
    _order = "id"

    active = fields.Boolean(default=True)
    bulk_id = fields.Many2one("ab.product.seo.bulk.optimization", required=True, index=True, ondelete="cascade")
    product_template_id = fields.Many2one("product.template", index=True, ondelete="restrict")
    ab_product_id = fields.Many2one("ab_product", index=True, ondelete="restrict")
    website_page_id = fields.Many2one("website.page", index=True, ondelete="restrict")
    website_url = fields.Char(readonly=True)
    status = fields.Selection(
        [
            ("optimized", "Optimized"),
            ("skipped", "Skipped"),
            ("error", "Error"),
            ("deferred", "Deferred"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        index=True,
    )
    message = fields.Text(readonly=True)

    def unlink(self):
        raise UserError(_("Bulk SEO optimization lines must not be deleted. Archive the parent run instead."))
