from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .product_seo import SEO_LANGUAGES
from ..services.seo_templates import language_errors


class AbProductSeoVersion(models.Model):
    _name = "ab.product.seo.version"
    _description = "Website SEO Version"
    _order = "seo_id, lang_code, version_number desc"

    active = fields.Boolean(default=True)
    seo_id = fields.Many2one("ab.product.seo", required=True, index=True, ondelete="cascade")
    translation_id = fields.Many2one("ab.product.seo.translation", index=True, ondelete="set null")
    source_snapshot_id = fields.Many2one("ab.product.seo.source.snapshot", ondelete="set null")
    version_number = fields.Integer(required=True, index=True)
    lang_code = fields.Selection(SEO_LANGUAGES, required=True, index=True)
    meta_title = fields.Char(readonly=True)
    meta_description = fields.Text(readonly=True)
    keyword_text = fields.Char(string="Keywords", readonly=True)
    seo_name = fields.Char(string="Slug", readonly=True)
    short_description = fields.Text(readonly=True)
    public_description = fields.Html(readonly=True)
    active_ingredient = fields.Char(readonly=True)
    warnings = fields.Text(readonly=True)
    contraindications = fields.Text(readonly=True)
    storage = fields.Text(readonly=True)
    approved_by = fields.Many2one("res.users", readonly=True)
    approved_at = fields.Datetime(readonly=True)
    published_by = fields.Many2one("res.users", readonly=True)
    published_at = fields.Datetime(readonly=True)
    is_published = fields.Boolean(readonly=True)
    rollback_of_version_id = fields.Many2one("ab.product.seo.version", readonly=True)

    _uniq_version_lang = models.Constraint(
        "UNIQUE(seo_id, lang_code, version_number)",
        "SEO version numbers must be unique per product and language.",
    )

    def write(self, vals):
        protected = {
            "website_meta_title",
            "website_meta_description",
            "website_meta_keywords",
            "seo_name",
            "description_ecommerce",
            "meta_title",
            "meta_description",
            "keyword_text",
            "short_description",
            "public_description",
            "active_ingredient",
            "warnings",
            "contraindications",
            "storage",
            "version_number",
            "lang_code",
            "approved_by",
            "approved_at",
        }
        if protected & set(vals):
            raise UserError(_("SEO versions are immutable. Create a new version instead."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("SEO versions must not be deleted. Archive the parent SEO record instead."))

    def _get_publish_field_values(self, include_description=True):
        self.ensure_one()
        content = {field: self[field] for field in ('meta_title', 'meta_description', 'keyword_text', 'seo_name')}
        if include_description:
            content['public_description'] = self.public_description
        if language_errors(content, self.lang_code):
            raise UserError(_("Translate the SEO content into the selected language before approval or publication: %s") % self.lang_code)
        values = {
            "website_meta_title": self.meta_title or False,
            "website_meta_description": self.meta_description or False,
            "website_meta_keywords": self.keyword_text or False,
            "seo_name": self.seo_name or False,
        }
        if include_description:
            values["description_ecommerce"] = self.public_description or False
        return values
