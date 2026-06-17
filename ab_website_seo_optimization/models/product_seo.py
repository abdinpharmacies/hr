from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape


SEO_STATES = [
    ("draft", "Draft"),
    ("generated", "Generated"),
    ("under_review", "Under Review"),
    ("approved", "Approved"),
    ("published", "Published"),
    ("rejected", "Rejected"),
    ("archived", "Archived"),
]

SEO_LANGUAGES = [
    ("ar_001", "Arabic"),
    ("en_US", "English"),
]


class AbProductSeo(models.Model):
    _name = "ab.product.seo"
    _description = "Website SEO Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "write_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True, tracking=True)
    state = fields.Selection(SEO_STATES, default="draft", required=True, tracking=True, index=True)
    ab_product_id = fields.Many2one(
        "ab_product",
        string="Abdin Product",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    product_template_id = fields.Many2one(
        "product.template",
        string="Website Product",
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, index=True)
    website_id = fields.Many2one("website", string="Website", index=True)
    assistant_id = fields.Many2one("ab.seo.assistant", string="SEO Assistant")
    translation_ids = fields.One2many("ab.product.seo.translation", "seo_id", string="Translations")
    version_ids = fields.One2many("ab.product.seo.version", "seo_id", string="Versions")
    publish_log_ids = fields.One2many("ab.product.seo.publish.log", "seo_id", string="Publish Logs")
    match_ids = fields.One2many("ab.product.seo.match", "seo_id", string="Matches")
    source_snapshot_ids = fields.One2many("ab.product.seo.source.snapshot", "seo_id", string="Source Snapshots")
    current_version_id = fields.Many2one("ab.product.seo.version", string="Current Version", readonly=True)
    published_version_id = fields.Many2one("ab.product.seo.version", string="Published Version", readonly=True)
    last_snapshot_id = fields.Many2one("ab.product.seo.source.snapshot", string="Last Snapshot", readonly=True)
    last_published_at = fields.Datetime(readonly=True)
    last_published_by = fields.Many2one("res.users", readonly=True)
    seo_score = fields.Float(compute="_compute_seo_score", store=True)
    source_quality = fields.Selection(
        [
            ("empty", "Empty"),
            ("weak", "Weak"),
            ("fair", "Fair"),
            ("strong", "Strong"),
        ],
        compute="_compute_source_quality",
        store=True,
    )
    ready_for_publish = fields.Boolean(compute="_compute_ready_for_publish", store=True)
    has_conflict = fields.Boolean(default=False, tracking=True)
    conflict_note = fields.Text(readonly=True)

    _uniq_ab_product_website = models.UniqueIndex(
        "(ab_product_id, COALESCE(website_id, 0)) WHERE active",
        "Each product can only have one active SEO record per website scope.",
    )

    @api.depends("ab_product_id", "product_template_id")
    def _compute_name(self):
        for rec in self:
            product_name = rec.ab_product_id.display_name or rec.product_template_id.display_name
            rec.name = product_name and _("SEO - %s") % product_name or _("Website SEO Record")

    @api.depends("translation_ids.meta_title", "translation_ids.meta_description", "translation_ids.public_description")
    def _compute_seo_score(self):
        for rec in self:
            translations = rec.translation_ids
            if not translations:
                rec.seo_score = 0.0
                continue
            scores = []
            for translation in translations:
                filled = 0
                filled += bool(translation.meta_title)
                filled += bool(translation.meta_description)
                filled += bool(translation.seo_name)
                filled += bool(translation.public_description)
                filled += bool(translation.keyword_text)
                scores.append(filled / 5.0 * 100.0)
            rec.seo_score = sum(scores) / len(scores)

    @api.depends("last_snapshot_id", "last_snapshot_id.scientific_name", "last_snapshot_id.manufacturer", "last_snapshot_id.notes")
    def _compute_source_quality(self):
        for rec in self:
            snapshot = rec.last_snapshot_id
            if not snapshot:
                rec.source_quality = "empty"
                continue
            score = 0
            score += bool(snapshot.product_code)
            score += bool(snapshot.scientific_name)
            score += bool(snapshot.manufacturer)
            score += bool(snapshot.usage_manner)
            score += bool(snapshot.notes)
            if score >= 4:
                rec.source_quality = "strong"
            elif score >= 2:
                rec.source_quality = "fair"
            else:
                rec.source_quality = "weak"

    @api.depends("state", "translation_ids.current_version_id")
    def _compute_ready_for_publish(self):
        for rec in self:
            rec.ready_for_publish = rec.state == "approved" and bool(rec.translation_ids.filtered("current_version_id"))

    @api.model_create_multi
    def create(self, vals_list):
        templates = self.env["product.template"].sudo().with_context(active_test=False)
        for vals in vals_list:
            if vals.get("ab_product_id") and not vals.get("product_template_id"):
                template = templates.search([("ab_product_id", "=", vals["ab_product_id"])], limit=1)
                vals["product_template_id"] = template.id
        records = super().create(vals_list)
        records._ensure_default_translations()
        return records

    def unlink(self):
        raise UserError(_("SEO records must be archived instead of deleted."))

    def _ensure_default_translations(self):
        Translation = self.env["ab.product.seo.translation"]
        for rec in self:
            existing_langs = set(rec.translation_ids.mapped("lang_code"))
            for lang_code, _label in SEO_LANGUAGES:
                if lang_code not in existing_langs:
                    Translation.create({
                        "seo_id": rec.id,
                        "lang_code": lang_code,
                    })

    def _require_group(self, group_xmlid):
        if not self.env.user.has_group(group_xmlid):
            raise UserError(_("You do not have permission to perform this SEO action."))

    def action_create_source_snapshot(self):
        Snapshot = self.env["ab.product.seo.source.snapshot"].sudo()
        for rec in self:
            snapshot = Snapshot.create(rec._prepare_source_snapshot_vals())
            rec.last_snapshot_id = snapshot.id
        return True

    def _prepare_source_snapshot_vals(self):
        self.ensure_one()
        product = self.ab_product_id.sudo()
        return {
            "seo_id": self.id,
            "ab_product_id": product.id,
            "product_template_id": self.product_template_id.id,
            "eplus_serial": product.eplus_serial or 0,
            "product_code": product.code or False,
            "barcode_values": ", ".join(product.barcode_ids.mapped("name")),
            "scientific_name": ", ".join(product.scientific_groups_ids.mapped("name")) or False,
            "manufacturer": product.company_id.name or False,
            "origin": product.origin_id.name or product.origin or False,
            "usage_manner": product.usage_manner_id.name or False,
            "effective_material": product.effective_material or False,
            "effective_material_conc": str(product.effective_material_conc or "") or False,
            "notes": product.description or False,
            "group_path": " / ".join(product.groups_ids.mapped("name")),
        }

    def action_generate_draft(self):
        for rec in self:
            if not rec.last_snapshot_id:
                rec.action_create_source_snapshot()
            rec._ensure_default_translations()
            for translation in rec.translation_ids:
                if rec.assistant_id:
                    content = rec.assistant_id.generate_product_content(
                        rec._get_product_name_for_generation(),
                        translation.lang_code,
                        product_context=rec._get_generation_context(),
                    )
                    translation._apply_generated_content(content)
                    rec._apply_drug_data_content(content, translation.lang_code)
                else:
                    translation._generate_from_snapshot(rec.last_snapshot_id)
            rec.state = "generated"
        return True

    def action_fill_with_ai(self):
        return self.action_generate_draft()

    def _get_product_name_for_generation(self):
        self.ensure_one()
        product = self.ab_product_id
        template = self.product_template_id
        return product.name or product.product_card_name or template.name or product.code or ""

    def _get_generation_context(self):
        self.ensure_one()
        snapshot = self.last_snapshot_id
        return {
            "product_code": snapshot.product_code,
            "eplus_serial": snapshot.eplus_serial,
            "barcodes": snapshot.barcode_values,
            "scientific_name": snapshot.scientific_name,
            "manufacturer": snapshot.manufacturer,
            "origin": snapshot.origin,
            "usage_manner": snapshot.usage_manner,
            "effective_material": snapshot.effective_material,
            "notes": snapshot.notes,
            "group_path": snapshot.group_path,
        }

    def _apply_drug_data_content(self, content, lang_code):
        self.ensure_one()
        if not self.product_template_id or not content.get("drug_data"):
            return False
        DrugData = self.env["ab.product.drug.data"].sudo()
        drug_data = DrugData.search([
            ("product_template_id", "=", self.product_template_id.id),
            ("active", "=", True),
        ], limit=1)
        if not drug_data:
            drug_data = DrugData.create({"product_template_id": self.product_template_id.id})
        drug_data._apply_generated_content(content, assistant=self.assistant_id, lang_code=lang_code)
        return drug_data

    def action_submit_review(self):
        for rec in self:
            if rec.state not in ("draft", "generated", "rejected"):
                raise ValidationError(_("Only draft, generated, or rejected SEO records can be submitted."))
            if not rec.translation_ids.filtered(lambda tr: tr.meta_title and tr.meta_description):
                raise ValidationError(_("At least one translation must have meta title and meta description."))
            rec.state = "under_review"
        return True

    def action_approve(self):
        self._require_group("ab_website_seo_optimization.group_ab_website_seo_optimization_reviewer")
        for rec in self:
            if rec.state != "under_review":
                raise ValidationError(_("Only records under review can be approved."))
            versions = self.env["ab.product.seo.version"]
            for translation in rec.translation_ids.filtered(lambda tr: tr.meta_title and tr.meta_description):
                versions |= translation._create_version()
            if versions:
                rec.current_version_id = versions[-1].id
            rec.state = "approved"
        return True

    def action_reject(self):
        self._require_group("ab_website_seo_optimization.group_ab_website_seo_optimization_reviewer")
        for rec in self:
            if rec.state != "under_review":
                raise ValidationError(_("Only records under review can be rejected."))
            rec.state = "rejected"
        return True

    def action_publish(self):
        return self._publish_versions(force=False)

    def action_force_publish(self):
        self._require_group("ab_website_seo_optimization.group_ab_website_seo_optimization_manager")
        return self._publish_versions(force=True)

    def _publish_versions(self, force=False, publish_description=True):
        self._require_group("ab_website_seo_optimization.group_ab_website_seo_optimization_manager")
        Log = self.env["ab.product.seo.publish.log"].sudo()
        for rec in self:
            if rec.state not in ("approved", "published"):
                raise ValidationError(_("Only approved SEO records can be published."))
            if not rec.product_template_id:
                raise ValidationError(_("SEO record %s is not linked to a website product.") % rec.display_name)
            versions = rec.translation_ids.mapped("current_version_id").filtered(lambda version: version.active)
            if not versions:
                raise ValidationError(_("No approved SEO version is available for %s.") % rec.display_name)
            conflicts = []
            for version in versions:
                conflicts += rec._detect_publish_conflicts(version, publish_description=publish_description)
            if conflicts and not force:
                rec.write({
                    "has_conflict": True,
                    "conflict_note": "\n".join(conflicts),
                })
                raise ValidationError(_("Manual SEO field changes were detected:\n%s") % "\n".join(conflicts))
            for version in versions:
                rec._publish_version(version, Log, publish_description=publish_description)
            rec.write({
                "state": "published",
                "published_version_id": versions[-1].id,
                "last_published_at": fields.Datetime.now(),
                "last_published_by": self.env.user.id,
                "has_conflict": False,
                "conflict_note": False,
            })
        return True

    def _detect_publish_conflicts(self, version, publish_description=True):
        self.ensure_one()
        context = {"lang": version.lang_code}
        if self.website_id:
            context["website_id"] = self.website_id.id
        template = self.product_template_id.with_context(**context)
        conflicts = []
        field_values = version._get_publish_field_values(include_description=publish_description)
        for field_name in field_values:
            last_log = self.env["ab.product.seo.publish.log"].sudo().search([
                ("seo_id", "=", self.id),
                ("product_template_id", "=", self.product_template_id.id),
                ("lang_code", "=", version.lang_code),
                ("field_name", "=", field_name),
            ], order="published_at desc, id desc", limit=1)
            if not last_log:
                continue
            current_value = template[field_name] or False
            if (current_value or False) != (last_log.new_value or False):
                conflicts.append("%s/%s" % (version.lang_code, field_name))
        return conflicts

    def _publish_version(self, version, Log, publish_description=True):
        self.ensure_one()
        context = {"lang": version.lang_code}
        if self.website_id:
            context["website_id"] = self.website_id.id
        template = self.product_template_id.with_context(**context).sudo()
        vals = version._get_publish_field_values(include_description=publish_description)
        old_values = {field_name: template[field_name] or False for field_name in vals}
        template.write(vals)
        now = fields.Datetime.now()
        for field_name, new_value in vals.items():
            Log.create({
                "seo_id": self.id,
                "product_template_id": self.product_template_id.id,
                "version_id": version.id,
                "lang_code": version.lang_code,
                "field_name": field_name,
                "old_value": old_values.get(field_name) or False,
                "new_value": new_value or False,
                "operation": "publish",
                "published_by": self.env.user.id,
                "published_at": now,
            })
        version.sudo().write({
            "is_published": True,
            "published_by": self.env.user.id,
            "published_at": now,
        })

    def action_archive(self):
        self.write({"active": False, "state": "archived"})
        return True

    def action_reset_to_draft(self):
        self.write({"state": "draft"})
        return True

    @api.model
    def _html_paragraph(self, text):
        if not text:
            return False
        lines = str(html_escape(text)).splitlines() or [""]
        return "<p>%s</p>" % "<br/>".join(lines)
