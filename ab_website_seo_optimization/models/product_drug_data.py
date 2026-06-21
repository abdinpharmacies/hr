import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AbProductDrugData(models.Model):
    _name = "ab.product.drug.data"
    _description = "Drug-EG API Data"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "write_date desc, id desc"

    active = fields.Boolean(default=True)
    external_id = fields.Char(index=True)
    product_name = fields.Char(index=True)
    commercial_name_en = fields.Char(index=True)
    commercial_name_ar = fields.Char(index=True)
    scientific_name = fields.Char(index=True, translate=True)
    active_ingredient = fields.Char(index=True, translate=True)
    manufacturer = fields.Char(index=True)
    drug_class = fields.Char(index=True, translate=True)
    route = fields.Char(index=True)
    category = fields.Char(index=True)
    dosage_form = fields.Char(index=True)
    strength = fields.Char()
    package_size = fields.Char()
    price = fields.Float()
    currency = fields.Char(default="EGP")
    regulatory_status = fields.Char(translate=True)
    source_url = fields.Char(default="https://ready-api.vercel.app/api/drugs-eg")
    raw_payload = fields.Text(readonly=True)
    last_synced_at = fields.Datetime(readonly=True, index=True)
    name = fields.Char(compute="_compute_name", store=True)

    _uniq_external_id = models.UniqueIndex(
        "(external_id) WHERE external_id IS NOT NULL AND active",
        "Each active Drug-EG API row must have a unique external ID.",
    )

    @api.depends("product_name", "scientific_name")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.product_name or rec.scientific_name or _("Drug-EG API Data")

    def unlink(self):
        raise UserError(_("Drug-EG API data must be archived instead of deleted."))

    @api.model
    def upsert_from_drug_eg_item(self, item, source_url=False):
        if not isinstance(item, dict):
            return self.browse()
        external_id = self._extract_external_id(item)
        values = self._prepare_drug_eg_values(item, source_url=source_url)
        domain = [("external_id", "=", external_id)] if external_id else self._fallback_match_domain(values)
        record = self.sudo().search(domain, limit=1) if domain else self.browse()
        if record:
            record.write(values)
            return record
        return self.sudo().create(values)

    @api.model
    def _extract_external_id(self, item):
        for key in ("id", "_id", "drug_id", "product_id", "registration_number", "code", "barcode"):
            value = item.get(key)
            if value not in (None, False, "", []):
                return str(value)
        name = self._first_value(
            item,
            "commercial_name_en",
            "name_en",
            "product_name_en",
            "english_name",
            "name",
            "product_name",
            "trade_name",
            "brand_name",
            "commercial_name",
        )
        manufacturer = self._first_value(item, "manufacturer", "company", "company_name")
        if name and manufacturer:
            return "%s|%s" % (name.strip().lower(), manufacturer.strip().lower())
        return False

    @api.model
    def _fallback_match_domain(self, values):
        product_name = values.get("product_name")
        manufacturer = values.get("manufacturer")
        if product_name and manufacturer:
            return [("product_name", "=", product_name), ("manufacturer", "=", manufacturer)]
        if product_name:
            return [("product_name", "=", product_name)]
        return []

    @api.model
    def _prepare_drug_eg_values(self, item, source_url=False):
        scientific = self._first_value(
            item,
            "scientific_name",
            "scientificName",
            "generic_name",
            "active_ingredient",
            "ingredient",
            "ingredient_name",
        )
        commercial_name_en = self._first_value(
            item,
            "commercial_name_en",
            "commercialNameEn",
            "name_en",
            "nameEn",
            "product_name_en",
            "productNameEn",
            "english_name",
            "englishName",
            "name",
            "product_name",
            "trade_name",
            "brand_name",
            "commercial_name",
        )
        commercial_name_ar = self._first_value(
            item,
            "commercial_name_ar",
            "commercialNameAr",
            "name_ar",
            "nameAr",
            "product_name_ar",
            "productNameAr",
            "arabic_name",
            "arabicName",
            "nameArabic",
        )
        return {
            "active": True,
            "external_id": self._extract_external_id(item),
            "product_name": commercial_name_en or commercial_name_ar,
            "commercial_name_en": commercial_name_en,
            "commercial_name_ar": commercial_name_ar,
            "scientific_name": scientific,
            "active_ingredient": self._first_value(item, "active_ingredient", "ingredient", "ingredient_name") or scientific,
            "manufacturer": self._first_value(item, "manufacturer", "manufacturer_name", "company", "company_name"),
            "drug_class": self._first_value(
                item,
                "drug_class",
                "drugClass",
                "class",
                "class_name",
                "therapeutic_class",
                "therapeutic_category",
                "therapeuticCategory",
                "category",
                "category_name",
                "main_category",
            ),
            "route": self._first_value(item, "route", "usage_route", "route_of_administration"),
            "category": self._first_value(item, "category", "category_name", "therapeutic_category", "group", "main_category"),
            "dosage_form": self._first_value(item, "dosage_form", "form", "pharmaceutical_form"),
            "strength": self._first_value(item, "strength", "concentration", "dose"),
            "package_size": self._first_value(item, "package_size", "pack_size", "package"),
            "price": self._first_float(item, "price", "price_egp", "public_price"),
            "currency": self._first_value(item, "currency") or "EGP",
            "regulatory_status": self._first_value(item, "regulatory_status", "legal_status", "otc_status"),
            "source_url": source_url or "https://ready-api.vercel.app/api/drugs-eg",
            "raw_payload": json.dumps(item, ensure_ascii=False, sort_keys=True),
            "last_synced_at": fields.Datetime.now(),
        }

    @api.model
    def _first_value(self, data, *keys):
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else False
            if value not in (None, False, "", []):
                if isinstance(value, (list, tuple)):
                    return ", ".join(str(item) for item in value if item)
                if isinstance(value, dict):
                    return json.dumps(value, ensure_ascii=False, sort_keys=True)
                return str(value)
        return False

    @api.model
    def _first_float(self, data, *keys):
        for key in keys:
            value = data.get(key) if isinstance(data, dict) else False
            if value in (None, False, "", []):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0
