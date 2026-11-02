import base64
import binascii
import json
from collections import Counter

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.integration_queue_job.exception import RetryableJobError


SOURCE_FIELDS = {
    "website_meta_title": "meta_title",
    "website_meta_description": "meta_description",
    "website_meta_keywords": "keyword_text",
    "seo_name": "seo_name",
}
LANGUAGES = ("en_US", "ar_001")
MAX_SOURCE_BYTES = 60 * 1024 * 1024
BATCH_SIZE = 100


class AbStorefrontLegacySeoImport(models.Model):
    _name = "ab_storefront_legacy_seo_import"
    _description = "Legacy Product SEO Import"
    _order = "id desc"

    name = fields.Char(required=True, default=lambda self: _("Legacy product SEO import"))
    file = fields.Binary(required=True, attachment=True, string="Export File")
    filename = fields.Char(string="Filename")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    website_id = fields.Many2one("website", required=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("ready", "Ready"),
        ("running", "Running"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ], required=True, default="draft")
    source_count = fields.Integer(string="Rows with SEO Data", readonly=True)
    ready_count = fields.Integer(string="Matched Rows", readonly=True)
    processed_count = fields.Integer(string="Imported Drafts", readonly=True)
    skipped_count = fields.Integer(string="Skipped Rows", readonly=True)
    error_count = fields.Integer(string="Errors", readonly=True)
    line_ids = fields.One2many("ab_storefront_legacy_seo_import_line", "import_id", readonly=True)

    def write(self, values):
        if {"file", "filename", "company_id", "website_id"} & set(values):
            if any(record.state != "draft" for record in self):
                raise UserError(_("Import settings cannot change after preview."))
        return super().write(values)

    def _check_manager(self):
        if not self.env.user.has_group("ab_website_seo_optimization.group_ab_website_seo_optimization_manager"):
            raise AccessError(_("Only SEO Managers can import legacy SEO."))
        for record in self:
            if record.company_id not in self.env.companies or record.website_id.company_id != record.company_id:
                raise AccessError(_("The website must belong to an allowed company."))

    def _load_source(self):
        self.ensure_one()
        try:
            raw = base64.b64decode(self.file, validate=True)
        except (binascii.Error, ValueError):
            raise UserError(_("The export file could not be decoded.")) from None
        if len(raw) > MAX_SOURCE_BYTES:
            raise UserError(_("The export file is too large."))
        try:
            source = json.loads(raw)
        except (UnicodeError, ValueError):
            raise UserError(_("The export file is not valid JSON.")) from None
        if not isinstance(source, dict) or source.get("source") != "https://abdinpharmacies.com":
            raise UserError(_("This file was not exported from the expected website."))
        groups = source.get("products_by_language")
        if not isinstance(groups, dict) or not all(isinstance(groups.get(lang), list) for lang in LANGUAGES):
            raise UserError(_("The export must contain English and Arabic products."))
        catalog = source.get("template_field_catalog")
        if not isinstance(catalog, dict) or not all(name in catalog for name in SOURCE_FIELDS):
            raise UserError(_("The export is missing required SEO fields."))
        if any(not isinstance(catalog[name], dict) or catalog[name].get("type") not in ("char", "text") for name in SOURCE_FIELDS):
            raise UserError(_("The export has unexpected SEO field types."))
        return groups

    def action_prepare(self):
        self.ensure_one()
        self._check_manager()
        self.check_access("write")
        if self.state != "draft":
            raise UserError(_("Only a new import can be prepared."))
        if not (self.filename or "").lower().endswith(".json"):
            raise UserError(_("Upload the JSON file exported from the old website."))
        groups = self._load_source()
        entries = []
        for lang in LANGUAGES:
            for row in groups[lang]:
                if not isinstance(row, dict) or not isinstance(row.get("id"), int):
                    raise UserError(_("The export contains an invalid product row."))
                values = {
                    target: value.strip()
                    for source, target in SOURCE_FIELDS.items()
                    if isinstance(value := row.get(source), str) and value.strip()
                }
                if not values:
                    continue
                entries.append((lang, row, values))
        if not entries:
            raise UserError(_("The export has no product SEO values."))
        duplicate_keys = Counter((lang, row["id"]) for lang, row, _values in entries)
        if any(count > 1 for count in duplicate_keys.values()):
            raise UserError(_("The export contains duplicate product rows."))
        source_codes = {}
        for lang, row, _values in entries:
            product_id = row["id"]
            code = str(row.get("default_code") or "").strip()
            if product_id in source_codes and source_codes[product_id] != code:
                raise UserError(_("Product codes differ between the exported languages."))
            source_codes[product_id] = code
        duplicate_codes = Counter(
            (lang, str(row.get("default_code") or "").strip())
            for lang, row, _values in entries if str(row.get("default_code") or "").strip()
        )
        if any(count > 1 for count in duplicate_codes.values()):
            raise UserError(_("The export contains duplicate product codes."))
        codes = {str(row.get("default_code") or "").strip() for _lang, row, _values in entries}
        codes.discard("")
        products = self.env["ab_product"].search(fields.Domain("code", "in", list(codes)))
        products_by_code = {}
        for product in products:
            products_by_code.setdefault(product.code, []).append(product)
        template_domain = (
            fields.Domain("ab_product_id", "in", products.ids)
            & fields.Domain("active", "=", True)
            & fields.Domain("sale_ok", "=", True)
            & fields.Domain("is_published", "=", True)
            & fields.Domain("company_id", "in", [False, self.company_id.id])
            & fields.Domain("website_id", "in", [False, self.website_id.id])
        )
        templates = self.env["product.template"].search(template_domain)
        templates_by_product = {}
        for template in templates:
            templates_by_product.setdefault(template.ab_product_id.id, []).append(template)
        seo_domain = (
            fields.Domain("ab_product_id", "in", products.ids)
            & fields.Domain("website_id", "=", self.website_id.id)
            & fields.Domain("active", "=", True)
        )
        seo_records = self.env["ab.product.seo"].search(seo_domain)
        seo_by_product = {}
        for record in seo_records:
            seo_by_product.setdefault(record.ab_product_id.id, []).append(record)
        translations = self.env["ab.product.seo.translation"].search(
            fields.Domain("seo_id", "in", seo_records.ids)
        )
        translations_by_key = {(item.seo_id.id, item.lang_code): item for item in translations}
        lines = []
        ready = skipped = 0
        for lang, row, values in entries:
            code = str(row.get("default_code") or "").strip()
            matches = products_by_code.get(code, [])
            candidates = templates_by_product.get(matches[0].id, []) if len(matches) == 1 else []
            reason = False
            if not code:
                reason = _("Missing product code")
            elif len(matches) != 1:
                reason = _("Product code must match exactly one Abdin product")
            elif len(candidates) != 1:
                reason = _("Product must match exactly one published website product")
            else:
                existing = seo_by_product.get(matches[0].id, [])
                if len(existing) > 1 or (existing and (
                    existing[0].product_template_id != candidates[0]
                    or existing[0].company_id != self.company_id
                    or existing[0].state != "draft"
                )):
                    reason = _("Existing SEO record needs manual review")
                elif existing:
                    translation = translations_by_key.get((existing[0].id, lang))
                    if translation and (translation.content_source != "manual" or translation.current_version_id):
                        reason = _("Existing SEO translation needs manual review")
                    elif translation and all(not value or getattr(translation, field) for field, value in values.items()):
                        reason = _("SEO draft already contains these values")
            if reason:
                skipped += 1
            else:
                ready += 1
            lines.append({
                "import_id": self.id,
                "source_id": row["id"],
                "product_code": code,
                "lang_code": lang,
                "product_template_id": candidates[0].id if not reason else False,
                "meta_title": values.get("meta_title"),
                "meta_description": values.get("meta_description"),
                "keyword_text": values.get("keyword_text"),
                "seo_name": values.get("seo_name"),
                "source_og_image": row.get("website_meta_og_img") if isinstance(row.get("website_meta_og_img"), str) else False,
                "state": "skipped" if reason else "pending",
                "reason": reason,
            })
        line_model = self.env["ab_storefront_legacy_seo_import_line"]
        for offset in range(0, len(lines), 500):
            line_model.create(lines[offset:offset + 500])
        self.write({
            "source_count": len(entries),
            "ready_count": ready,
            "skipped_count": skipped,
            "state": "ready",
        })
        return self._open_form()

    def action_start(self):
        self.ensure_one()
        self._check_manager()
        self.check_access("write")
        if self.state != "ready" or not self.ready_count:
            raise UserError(_("Prepare an import with matched products first."))
        self.state = "running"
        self.with_company(self.company_id).with_context(allowed_company_ids=self.company_id.ids).with_delay(
            channel="root.seo",
            description=_("Import legacy product SEO"),
        )._process_batch()
        return self._open_form()

    def action_cancel(self):
        self.ensure_one()
        self._check_manager()
        if self.state not in ("ready", "running"):
            raise UserError(_("Only a ready or running import can be cancelled."))
        self.state = "cancelled"
        return self._open_form()

    def _process_batch(self):
        self.ensure_one()
        self._check_manager()
        if not self.try_lock_for_update():
            raise RetryableJobError(_("SEO import is busy. Try again shortly."), seconds=10)
        self.invalidate_recordset()
        if self.state != "running":
            return
        line_model = self.env["ab_storefront_legacy_seo_import_line"]
        pending_domain = fields.Domain("import_id", "=", self.id) & fields.Domain("state", "=", "pending")
        lines = line_model.search(pending_domain, order="id", limit=BATCH_SIZE)
        product_ids = lines.mapped("product_template_id.ab_product_id").ids
        seo_domain = (
            fields.Domain("ab_product_id", "in", product_ids)
            & fields.Domain("website_id", "=", self.website_id.id)
            & fields.Domain("active", "=", True)
        )
        seo_by_product = {}
        for record in self.env["ab.product.seo"].search(seo_domain):
            seo_by_product.setdefault(record.ab_product_id.id, []).append(record)
        for line in lines:
            try:
                with self.env.cr.savepoint():
                    result, reason = line._import_draft(seo_by_product)
            except (UserError, ValidationError) as error:
                result, reason = "error", str(error)
            line.write({"state": result, "reason": reason})
        self.write({
            "processed_count": self.processed_count + len(lines.filtered(lambda line: line.state == "imported")),
            "skipped_count": self.skipped_count + len(lines.filtered(lambda line: line.state == "skipped")),
            "error_count": self.error_count + len(lines.filtered(lambda line: line.state == "error")),
        })
        if line_model.search_count(pending_domain, limit=1):
            self.with_company(self.company_id).with_context(allowed_company_ids=self.company_id.ids).with_delay(
                channel="root.seo",
                description=_("Import legacy product SEO"),
            )._process_batch()
        else:
            self.state = "done"

    def _open_form(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Legacy SEO Imports"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_lines(self):
        self.ensure_one()
        self._check_manager()
        return {
            "type": "ir.actions.act_window",
            "name": _("SEO Import Results"),
            "res_model": "ab_storefront_legacy_seo_import_line",
            "view_mode": "list",
            "domain": list(fields.Domain("import_id", "=", self.id)),
            "target": "current",
        }


class AbStorefrontLegacySeoImportLine(models.Model):
    _name = "ab_storefront_legacy_seo_import_line"
    _description = "Legacy Product SEO Import Line"
    _order = "id"

    import_id = fields.Many2one("ab_storefront_legacy_seo_import", required=True, ondelete="cascade", index=True)
    source_id = fields.Integer(string="Old Product ID", readonly=True)
    product_code = fields.Char(string="Product Code", readonly=True)
    lang_code = fields.Selection([("en_US", "English"), ("ar_001", "Arabic")], string="Language", readonly=True)
    product_template_id = fields.Many2one("product.template", string="Website Product", readonly=True)
    meta_title = fields.Char(string="Meta Title", readonly=True)
    meta_description = fields.Text(string="Meta Description", readonly=True)
    keyword_text = fields.Char(string="Keywords", readonly=True)
    seo_name = fields.Char(string="SEO Slug", readonly=True)
    source_og_image = fields.Char(string="Old Open Graph Image", readonly=True)
    state = fields.Selection([
        ("pending", "Pending"), ("imported", "Imported"),
        ("skipped", "Skipped"), ("error", "Error"),
    ], readonly=True)
    reason = fields.Text(string="Details", readonly=True)

    def _import_draft(self, seo_by_product):
        self.ensure_one()
        self.import_id._check_manager()
        template = self.product_template_id
        if not template or (template.company_id and template.company_id != self.import_id.company_id):
            return "skipped", _("Product company changed after preview")
        if template.website_id and template.website_id != self.import_id.website_id:
            return "skipped", _("Product website changed after preview")
        if not template.active or not template.sale_ok or not template.is_published:
            return "skipped", _("Product is no longer published")
        if template.ab_product_id.code != self.product_code:
            return "skipped", _("Product code changed after preview")
        seo_model = self.env["ab.product.seo"]
        records = seo_by_product.get(template.ab_product_id.id, [])
        if len(records) > 1:
            return "error", _("Multiple active SEO records need review")
        record = records[0] if records else False
        if record and (record.product_template_id != template or record.state != "draft"):
            return "skipped", _("Existing SEO record needs manual review")
        if record and record.company_id != self.import_id.company_id:
            return "skipped", _("Existing SEO record belongs to another company")
        if not record:
            record = seo_model.create({
                "ab_product_id": template.ab_product_id.id,
                "product_template_id": template.id,
                "company_id": self.import_id.company_id.id,
                "website_id": self.import_id.website_id.id,
                "lang_mode": "all",
            })
        translation = record.translation_ids.filtered(lambda item: item.lang_code == self.lang_code)
        if not translation:
            record._ensure_default_translations()
            translation = record.translation_ids.filtered(lambda item: item.lang_code == self.lang_code)
        translation.check_access("write")
        if translation.content_source != "manual" or translation.current_version_id:
            return "skipped", _("Existing SEO translation needs manual review")
        values = {
            name: getattr(self, name)
            for name in ("meta_title", "meta_description", "keyword_text", "seo_name")
            if getattr(self, name) and not getattr(translation, name)
        }
        if not values:
            return "skipped", _("SEO draft already contains these values")
        values.update({
            "content_source": "manual",
            "source_summary": _("Imported from the old website, product code %s") % self.product_code,
        })
        translation.write(values)
        seo_by_product[template.ab_product_id.id] = [record]
        return "imported", _("SEO draft saved for review")
