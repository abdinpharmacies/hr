import re

import werkzeug

from odoo import http, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request


class AbWebsiteSeoComponentController(http.Controller):

    @http.route(
        "/ab_website_seo_optimization/seo_component_suggest",
        type="jsonrpc",
        auth="user",
        website=True,
    )
    def seo_component_suggest(self, res_model, res_id, lang=None, url=None, title=None, description=None, keywords=None, page_text=None):
        record = self._get_editable_record(res_model, res_id)
        assistant = self._get_available_ai_assistant()
        lang_code = lang or request.env.context.get("lang") or request.website.default_lang_id.code or "en_US"
        component_name = self._get_component_name(record, title=title, url=url)
        context = self._build_component_context(
            record,
            url=url,
            title=title,
            description=description,
            keywords=keywords,
            page_text=page_text,
        )
        suggestion = assistant.generate_seo_component_content(
            component_name,
            lang_code,
            component_context=context,
        )
        suggestion["slug"] = request.env["ir.http"]._slugify(suggestion.get("slug") or component_name)
        return suggestion

    def _get_editable_record(self, res_model, res_id):
        if not request.env.user.has_group("website.group_website_restricted_editor"):
            try:
                record = request.env[res_model].browse(int(res_id))
                record.check_access("write")
            except AccessError:
                raise werkzeug.exceptions.Forbidden()
        record = request.env[res_model].browse(int(res_id)).exists()
        if not record:
            raise UserError(_("The SEO target record was not found."))
        try:
            request.website._check_user_can_modify(record)
        except AccessError:
            raise werkzeug.exceptions.Forbidden()
        if request.env.user.has_group("website.group_website_restricted_editor"):
            record = record.sudo()
        return record

    def _get_available_ai_assistant(self):
        assistant = request.env["ab.seo.assistant"].sudo().search([
            ("active", "=", True),
            ("assistant_type", "=", "ai"),
            ("api_key", "!=", False),
        ], order="sequence, id", limit=1)
        if not assistant:
            raise UserError(_("No active AI assistant with an API key is configured in SEO Optimization settings."))
        return assistant

    def _get_component_name(self, record, title=None, url=None):
        return (
            self._clean_component_label(title)
            or self._clean_text(getattr(record, "display_name", False))
            or self._clean_text(url)
            or _("Website page")
        )

    def _build_component_context(self, record, url=None, title=None, description=None, keywords=None, page_text=None):
        values = {
            "res_model": record._name,
            "res_id": record.id,
            "display_name": self._clean_text(getattr(record, "display_name", "")),
            "url": self._clean_text(url),
            "current_title": self._clean_component_label(title),
            "current_description": self._clean_component_label(description),
            "current_keywords": self._clean_text(keywords),
            "page_text": self._sanitize_page_text(page_text),
        }
        if record._name == "product.template":
            values.update(self._get_product_context(record))
        elif record._name == "website.page":
            values.update({
                "page_name": self._clean_text(record.name),
                "page_url": self._clean_text(record.url),
            })
        return {key: value for key, value in values.items() if value}

    def _get_product_context(self, template):
        product = template.ab_product_id.sudo() if "ab_product_id" in template._fields and template.ab_product_id else False
        if not product:
            return {
                "product_name": self._clean_text(template.name),
                "description_sale": self._clean_text(template.description_sale),
            }
        return {
            "product_name": self._clean_text(product.name or product.product_card_name or template.name),
            "product_code": self._clean_text(product.code),
            "eplus_serial": product.eplus_serial or False,
            "scientific_name": self._clean_text(", ".join(product.scientific_groups_ids.mapped("name"))),
            "manufacturer": self._clean_text(product.company_id.name),
            "origin": self._clean_text(product.origin_id.name or product.origin),
            "usage_manner": self._clean_text(product.usage_manner_id.name),
            "effective_material": self._clean_text(product.effective_material),
            "notes": self._truncate_text(product.description or template.description_sale, 700),
            "group_path": self._clean_text(" / ".join(product.groups_ids.mapped("name"))),
        }

    def _clean_text(self, value):
        if not value:
            return False
        return re.sub(r"\s+", " ", str(value)).strip()

    def _clean_component_label(self, value):
        text = self._clean_text(value)
        if not text:
            return False
        lowered = text.lower()
        if text.startswith(("{", "[")) or any(marker in lowered for marker in (
            '"meta_title"',
            '"public_description"',
            '"drug_data"',
            '"short_description"',
        )):
            return False
        return text

    def _truncate_text(self, value, limit):
        text = self._clean_text(value)
        return text[:limit] if text else False

    def _sanitize_page_text(self, value):
        text = self._clean_text(value)
        if not text:
            return False
        text = re.sub(r"\{[^{}]*(?:meta_title|public_description|drug_data|short_description)[^{}]*\}", " ", text)
        ignored_patterns = (
            r"\bUnits in Stock\b",
            r"\bPrice\b",
            r"\bTerms and Conditions\b",
            r"\bShipping\b",
            r"\bBusiness Days\b",
            r"\bLE\b",
            r"\bEGP\b",
        )
        lines = []
        for line in re.split(r"(?<=[.!؟])\s+|\n+", text):
            clean_line = self._clean_text(line)
            if not clean_line:
                continue
            if any(re.search(pattern, clean_line, flags=re.IGNORECASE) for pattern in ignored_patterns):
                continue
            if clean_line.startswith(("{", "[")):
                continue
            lines.append(clean_line)
            if len(" ".join(lines)) >= 1600:
                break
        return self._truncate_text(" ".join(lines), 1800)
