from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .product_seo import SEO_LANGUAGES


class AbProductSeoTranslation(models.Model):
    _name = "ab.product.seo.translation"
    _description = "Website SEO Translation"
    _order = "seo_id, lang_code"

    seo_id = fields.Many2one("ab.product.seo", required=True, index=True, ondelete="cascade")
    lang_code = fields.Selection(SEO_LANGUAGES, required=True, index=True)
    meta_title = fields.Char()
    meta_description = fields.Text()
    keyword_text = fields.Char(string="Keywords")
    seo_name = fields.Char(string="Slug")
    short_description = fields.Text()
    public_description = fields.Html()
    active_ingredient = fields.Char()
    warnings = fields.Text()
    contraindications = fields.Text()
    storage = fields.Text()
    source_summary = fields.Text(readonly=True)
    content_source = fields.Selection(
        [
            ("manual", "Manual"),
            ("internal", "Internal Data"),
            ("ready_api", "Ready API"),
            ("assistant", "AI Assistant"),
        ],
        default="manual",
        required=True,
    )
    review_notes = fields.Text()
    current_version_id = fields.Many2one("ab.product.seo.version", readonly=True)

    _uniq_seo_lang = models.Constraint(
        "UNIQUE(seo_id, lang_code)",
        "Each SEO record can only have one translation per language.",
    )

    def unlink(self):
        if self.filtered("current_version_id"):
            raise UserError(_("Approved SEO translations must be archived through the parent SEO record, not deleted."))
        return super().unlink()

    def _generate_from_snapshot(self, snapshot):
        self.ensure_one()
        seo = self.seo_id
        product = seo.ab_product_id
        product_name = product.name or product.product_card_name or product.code or ""
        manufacturer = snapshot.manufacturer or ""
        scientific = snapshot.scientific_name or snapshot.effective_material or ""
        usage = snapshot.usage_manner or ""
        origin = snapshot.origin or ""
        brand_name = "صيدليات عابدين" if self.lang_code == "ar_001" else "Abdin Pharmacies"
        title_parts = [part for part in [product_name, scientific, brand_name] if part]
        meta_title = " | ".join(title_parts[:3])
        if self.lang_code == "ar_001":
            description_parts = [
                "اشتري %(product)s من صيدليات عابدين." % {"product": product_name} if product_name else "",
                "الشركة المنتجة: %s." % manufacturer if manufacturer else "",
                "الاسم العلمي: %s." % scientific if scientific else "",
                "طريقة الاستخدام: %s." % usage if usage else "",
            ]
        else:
            description_parts = [
                _("Buy %(product)s from Abdin Pharmacies.") % {"product": product_name} if product_name else "",
                _("Manufacturer: %s.") % manufacturer if manufacturer else "",
                _("Scientific name: %s.") % scientific if scientific else "",
                _("Usage: %s.") % usage if usage else "",
            ]
        meta_description = " ".join(part for part in description_parts if part).strip()
        keywords = ", ".join(part for part in [product_name, scientific, manufacturer, usage, origin] if part)
        public_description = snapshot.notes and seo._html_paragraph(snapshot.notes) or False
        vals = {
            "meta_title": meta_title[:255],
            "meta_description": meta_description,
            "keyword_text": keywords[:255],
            "seo_name": product_name,
            "short_description": snapshot.notes or meta_description,
            "public_description": public_description,
            "active_ingredient": snapshot.effective_material or scientific,
            "source_summary": snapshot._get_source_summary(),
            "content_source": "internal",
        }
        self.write(vals)

    def _apply_generated_content(self, content):
        self.ensure_one()
        vals = {
            "meta_title": (content.get("meta_title") or "")[:255],
            "meta_description": content.get("meta_description") or False,
            "keyword_text": (content.get("keyword_text") or content.get("keywords") or "")[:255],
            "seo_name": content.get("seo_name") or content.get("slug") or False,
            "short_description": content.get("short_description") or False,
            "public_description": content.get("public_description") or False,
            "active_ingredient": content.get("active_ingredient") or False,
            "warnings": content.get("warnings") or False,
            "contraindications": content.get("contraindications") or False,
            "storage": content.get("storage") or False,
            "source_summary": content.get("source_summary") or False,
            "content_source": content.get("content_source") or "assistant",
        }
        vals = {key: value for key, value in vals.items() if value not in (None, "")}
        if vals:
            self.write(vals)

    def _create_version(self):
        self.ensure_one()
        version_number = self.env["ab.product.seo.version"].search_count([
            ("seo_id", "=", self.seo_id.id),
            ("lang_code", "=", self.lang_code),
        ]) + 1
        version = self.env["ab.product.seo.version"].sudo().create({
            "seo_id": self.seo_id.id,
            "translation_id": self.id,
            "source_snapshot_id": self.seo_id.last_snapshot_id.id,
            "version_number": version_number,
            "lang_code": self.lang_code,
            "meta_title": self.meta_title,
            "meta_description": self.meta_description,
            "keyword_text": self.keyword_text,
            "seo_name": self.seo_name,
            "short_description": self.short_description,
            "public_description": self.public_description,
            "active_ingredient": self.active_ingredient,
            "warnings": self.warnings,
            "contraindications": self.contraindications,
            "storage": self.storage,
            "approved_by": self.env.user.id,
            "approved_at": fields.Datetime.now(),
        })
        self.current_version_id = version.id
        return version
