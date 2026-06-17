from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AbProductDrugData(models.Model):
    _name = "ab.product.drug.data"
    _description = "Product Drug Data"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "product_template_id"

    active = fields.Boolean(default=True)
    is_published = fields.Boolean(default=True, tracking=True)
    product_template_id = fields.Many2one(
        "product.template",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    ab_product_id = fields.Many2one(
        "ab_product",
        related="product_template_id.ab_product_id",
        store=True,
        readonly=True,
        index=True,
    )
    name = fields.Char(compute="_compute_name", store=True)
    scientific_name = fields.Char(translate=True)
    commercial_names = fields.Text(translate=True)
    active_ingredient = fields.Char(translate=True)
    drug_class = fields.Char(translate=True)
    regulatory_status = fields.Char(translate=True)
    common_uses = fields.Text(translate=True)
    side_effects = fields.Text(translate=True)
    warnings = fields.Text(translate=True)
    pregnancy = fields.Text(translate=True)
    breastfeeding = fields.Text(translate=True)
    storage = fields.Text(translate=True)
    interactions = fields.Text(translate=True)
    source_type = fields.Selection(
        [
            ("internal", "Internal Product Data"),
            ("drugs_eg", "Drugs EG API"),
            ("assistant", "Assistant Optimized"),
            ("manual", "Manual"),
        ],
        default="internal",
        required=True,
    )
    source_label = fields.Char(
        default="Internal product catalog / drugs-eg enrichment",
        translate=True,
    )
    source_url = fields.Char(default="https://ready-api.vercel.app/api/drugs-eg")
    assistant_id = fields.Many2one("ab.seo.assistant", string="Optimized By Assistant")
    last_generated_at = fields.Datetime(readonly=True)

    _uniq_product_template = models.UniqueIndex(
        "(product_template_id) WHERE active",
        "Each website product can only have one active drug data record.",
    )

    @api.depends("product_template_id")
    def _compute_name(self):
        for rec in self:
            rec.name = _("Drug Data - %s") % (rec.product_template_id.display_name or "")

    def unlink(self):
        raise UserError(_("Drug data records must be archived instead of deleted."))

    def action_generate_from_product(self):
        for rec in self:
            rec._generate_from_product("en_US")
            rec.with_context(lang="ar_001")._generate_from_product("ar_001")
        return True

    def _generate_from_product(self, lang_code):
        self.ensure_one()
        product = self.ab_product_id.sudo()
        template = self.product_template_id.sudo()
        product_name = product.name or template.name or ""
        scientific = ", ".join(product.scientific_groups_ids.mapped("name")) or product.effective_material or ""
        manufacturer = product.company_id.name or ""
        usage = product.usage_manner_id.name or ""
        notes = product.description or template.description_sale or ""
        if lang_code == "ar_001":
            values = self._get_arabic_generated_values(product_name, scientific, manufacturer, usage, notes)
        else:
            values = self._get_english_generated_values(product_name, scientific, manufacturer, usage, notes)
        values.update({
            "scientific_name": scientific,
            "commercial_names": product_name,
            "active_ingredient": product.effective_material or scientific,
            "source_type": "internal",
            "last_generated_at": fields.Datetime.now(),
        })
        self.with_context(lang=lang_code).write(values)

    def _apply_generated_content(self, content, assistant=False, lang_code="en_US"):
        self.ensure_one()
        drug_data = content.get("drug_data") or content
        vals = {
            "scientific_name": drug_data.get("scientific_name") or content.get("active_ingredient"),
            "commercial_names": drug_data.get("commercial_names"),
            "active_ingredient": drug_data.get("active_ingredient") or content.get("active_ingredient"),
            "drug_class": drug_data.get("drug_class"),
            "regulatory_status": drug_data.get("regulatory_status"),
            "common_uses": drug_data.get("common_uses") or content.get("short_description"),
            "side_effects": drug_data.get("side_effects"),
            "warnings": drug_data.get("warnings") or content.get("warnings"),
            "pregnancy": drug_data.get("pregnancy"),
            "breastfeeding": drug_data.get("breastfeeding"),
            "storage": drug_data.get("storage") or content.get("storage"),
            "interactions": drug_data.get("interactions"),
            "source_type": drug_data.get("source_type") or ("assistant" if assistant and assistant.assistant_type == "ai" else "drugs_eg"),
            "source_label": drug_data.get("source_label") or (assistant.display_name if assistant else False),
            "source_url": content.get("source_url") or (assistant._get_endpoint_url() if assistant else False),
            "assistant_id": assistant.id if assistant else False,
            "last_generated_at": fields.Datetime.now(),
        }
        vals = {key: value for key, value in vals.items() if value not in (None, "")}
        self.with_context(lang=lang_code).write(vals)

    def _get_english_generated_values(self, product_name, scientific, manufacturer, usage, notes):
        common_uses = notes or usage or _("See product leaflet and pharmacist instructions.")
        return {
            "drug_class": scientific or False,
            "regulatory_status": _("OTC or prescription status depends on local registration."),
            "common_uses": common_uses,
            "side_effects": _("Side effects vary by active ingredient. Review the product leaflet before use."),
            "warnings": _("Use only as directed. Ask a pharmacist or physician if you have chronic conditions or use other medicines."),
            "pregnancy": _("Ask a physician or pharmacist before use during pregnancy."),
            "breastfeeding": _("Ask a physician or pharmacist before use while breastfeeding."),
            "storage": _("Store at room temperature, away from moisture, heat, and direct light unless the leaflet states otherwise."),
            "interactions": _("Interactions depend on the active ingredient. Tell your pharmacist about all medicines and supplements you use."),
            "source_label": _("Internal product catalog / drugs-eg enrichment"),
        }

    def _get_arabic_generated_values(self, product_name, scientific, manufacturer, usage, notes):
        common_uses = notes or usage or "راجع النشرة الداخلية واستشر الصيدلي قبل الاستخدام."
        return {
            "drug_class": scientific or False,
            "regulatory_status": "تحديد حالة الصرف يعتمد على التسجيل المحلي للمنتج.",
            "common_uses": common_uses,
            "side_effects": "تختلف الأعراض الجانبية حسب المادة الفعالة. راجع النشرة الداخلية قبل الاستخدام.",
            "warnings": "يستخدم حسب الإرشادات فقط. استشر الصيدلي أو الطبيب إذا كان لديك أمراض مزمنة أو تستخدم أدوية أخرى.",
            "pregnancy": "استشيري الطبيب أو الصيدلي قبل الاستخدام أثناء الحمل.",
            "breastfeeding": "استشيري الطبيب أو الصيدلي قبل الاستخدام أثناء الرضاعة.",
            "storage": "يحفظ في درجة حرارة الغرفة بعيداً عن الرطوبة والحرارة والضوء المباشر ما لم تذكر النشرة خلاف ذلك.",
            "interactions": "تعتمد التداخلات الدوائية على المادة الفعالة. أخبر الصيدلي بكل الأدوية والمكملات التي تستخدمها.",
            "source_label": "كتالوج المنتجات الداخلي / إثراء بيانات drugs-eg",
        }


class ProductTemplate(models.Model):
    _inherit = "product.template"

    ab_drug_data_ids = fields.One2many("ab.product.drug.data", "product_template_id", string="Drug Data")
    ab_drug_data_id = fields.Many2one(
        "ab.product.drug.data",
        compute="_compute_ab_drug_data_id",
        string="Published Drug Data",
    )

    def _compute_ab_drug_data_id(self):
        for template in self:
            template.ab_drug_data_id = template.ab_drug_data_ids.filtered(
                lambda rec: rec.active and rec.is_published
            )[:1]
