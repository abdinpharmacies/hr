import json
import logging
import re
import time

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import html_escape


_logger = logging.getLogger(__name__)


class AbSeoAssistant(models.Model):
    _inherit = "ab.seo.assistant"

    _CLASSIFICATION_LABELS = (
        "medicine",
        "supplement",
        "medical_device",
        "cosmetic",
        "personal_care",
        "general_product",
    )

    @api.model
    def _build_product_source_bundle(self, product_name=False, product_context=None):
        context = product_context or {}
        trusted_facts = {
            "product_name": product_name or context.get("product_name") or "",
            "product_code": context.get("product_code") or "",
            "eplus_serial": context.get("eplus_serial") or "",
            "barcodes": context.get("barcodes") or context.get("barcode") or "",
            "manufacturer": context.get("manufacturer") or "",
            "category_path": context.get("category_path") or context.get("group_path") or "",
            "scientific_name": context.get("scientific_name") or "",
            "scientific_group": context.get("scientific_group") or context.get("scientific_name") or "",
            "effective_material": context.get("effective_material") or "",
            "effective_material_conc": context.get("effective_material_conc") or "",
            "usage_manner": context.get("usage_manner") or "",
            "origin": context.get("origin") or "",
            "is_medicine": bool(context.get("is_medicine")),
            "existing_descriptions": context.get("existing_descriptions") or {
                "notes": context.get("notes") or "",
                "description": context.get("description") or "",
            },
            "existing_website_descriptions": context.get("existing_website_descriptions") or {},
            "cached_drug_information": context.get("cached_drug_information") or self._get_cached_drug_information(
                product_name or context.get("product_name"),
                context,
            ),
        }
        existing_seo = context.get("existing_seo") or {
            "website_meta_title": context.get("website_meta_title") or "",
            "website_meta_description": context.get("website_meta_description") or "",
            "website_meta_keywords": context.get("website_meta_keywords") or "",
            "seo_name": context.get("seo_name") or "",
        }
        bundle = {
            "trusted_facts": trusted_facts,
            "existing_seo": existing_seo,
            "classification": {},
            "missing_information": [],
        }
        bundle["classification"] = self._classify_product_from_source_bundle(bundle)
        bundle["missing_information"] = self._get_source_bundle_missing_information(
            bundle,
            bundle["classification"],
        )
        return bundle

    @api.model
    def _get_cached_drug_information(self, product_name=False, product_context=None):
        if "ab.product.drug.data" not in self.env.registry:
            return {}
        context = product_context or {}
        search_values = [
            product_name,
            context.get("scientific_name"),
            context.get("effective_material"),
        ]
        domain = []
        for value in search_values:
            if not value:
                continue
            clean_value = str(value).strip()
            if not clean_value:
                continue
            condition = [
                "|", "|", "|",
                ("product_name", "ilike", clean_value),
                ("commercial_name_en", "ilike", clean_value),
                ("commercial_name_ar", "ilike", clean_value),
                ("scientific_name", "ilike", clean_value),
            ]
            domain = condition if not domain else ["|"] + domain + condition
        if not domain:
            return {}
        record = self.env["ab.product.drug.data"].sudo().search(domain, limit=1)
        if not record:
            return {}
        return {
            "product_name": record.product_name or "",
            "commercial_name_en": record.commercial_name_en or "",
            "commercial_name_ar": record.commercial_name_ar or "",
            "scientific_name": record.scientific_name or "",
            "active_ingredient": record.active_ingredient or "",
            "manufacturer": record.manufacturer or "",
            "drug_class": record.drug_class or "",
            "route": record.route or "",
            "category": record.category or "",
            "dosage_form": record.dosage_form or "",
            "strength": record.strength or "",
            "package_size": record.package_size or "",
            "regulatory_status": record.regulatory_status or "",
            "source_url": record.source_url or "",
        }

    @api.model
    def _classify_product_from_source_bundle(self, source_bundle):
        facts = (source_bundle or {}).get("trusted_facts") or {}
        haystack = self._classification_haystack(facts)
        scores = {label: 0.0 for label in self._CLASSIFICATION_LABELS}
        evidence_counts = {label: 0 for label in self._CLASSIFICATION_LABELS}

        if facts.get("is_medicine"):
            scores["medicine"] += 0.35
            evidence_counts["medicine"] += 1
        if facts.get("scientific_name") or facts.get("scientific_group"):
            scores["medicine"] += 0.25
            evidence_counts["medicine"] += 1
        if facts.get("effective_material") or facts.get("effective_material_conc"):
            scores["medicine"] += 0.25
            evidence_counts["medicine"] += 1
        if self._has_any(haystack, self._medicine_terms()):
            scores["medicine"] += 0.25
            evidence_counts["medicine"] += 1

        term_groups = {
            "supplement": self._supplement_terms(),
            "medical_device": self._medical_device_terms(),
            "cosmetic": self._cosmetic_terms(),
            "personal_care": self._personal_care_terms(),
        }
        for label, terms in term_groups.items():
            matches = self._term_matches(haystack, terms)
            if matches:
                scores[label] += min(0.80, 0.35 + (0.15 * min(len(matches), 3)))
                evidence_counts[label] += len(matches)

        scores["general_product"] = 0.20
        selected = max(scores, key=lambda key: scores[key])
        if selected == "medicine" and scores[selected] <= 0.35:
            non_medical = max(
                ("supplement", "medical_device", "cosmetic", "personal_care"),
                key=lambda key: scores[key],
            )
            if scores[non_medical] >= 0.50:
                selected = non_medical
        confidence = scores[selected]
        if selected != "general_product":
            confidence = min(0.95, confidence + min(0.10, evidence_counts[selected] * 0.02))
        return {
            "classification": selected if confidence >= 0.30 else "general_product",
            "classification_confidence": round(confidence if confidence >= 0.30 else 0.20, 2),
        }

    @api.model
    def _get_source_bundle_missing_information(self, source_bundle, classification=None):
        facts = (source_bundle or {}).get("trusted_facts") or {}
        classification = classification or (source_bundle or {}).get("classification") or {}
        product_type = classification.get("classification") or "general_product"
        missing = []
        required = [
            ("product_name", _("product name missing")),
            ("manufacturer", _("manufacturer missing")),
            ("category_path", _("category missing")),
            ("barcodes", _("barcode missing")),
        ]
        if product_type in ("medicine", "supplement"):
            required += [
                ("effective_material", _("active ingredient unavailable")),
                ("scientific_name", _("scientific name unavailable")),
            ]
        for key, message in required:
            if not facts.get(key):
                missing.append(message)
        return missing

    def _request_ai_product(self, product_name, lang_code, product_context=None):
        self.ensure_one()
        source_bundle = self._build_product_source_bundle(product_name, product_context=product_context)
        classification = source_bundle.get("classification") or {}
        prompt_type = classification.get("classification") or "general_product"
        start = time.monotonic()
        try:
            prompt = self._build_ai_product_prompt_from_bundle(product_name, lang_code, source_bundle)
            payload = self._build_ai_payload(prompt)
            response = self._http_json("POST", self._get_endpoint_url(), payload=payload)
            content = self._extract_ai_text(response)
            if not content:
                raise UserError(_("%s returned an empty AI response.") % self.display_name)
            parsed = self._parse_ai_content(content, product_name=product_name, lang_code=lang_code)
            sanitized = self._sanitize_generated_product_content(parsed, source_bundle)
            return sanitized, self._extract_token_usage(response)
        finally:
            duration = time.monotonic() - start
            _logger.info(
                "SEO AI generation diagnostics: assistant=%s classification=%s confidence=%s "
                "prompt_type=%s source_bundle_size=%s missing_fields=%s duration=%.3fs",
                self.display_name,
                classification.get("classification"),
                classification.get("classification_confidence"),
                prompt_type,
                len(json.dumps(source_bundle, ensure_ascii=False, default=str)),
                ", ".join(source_bundle.get("missing_information") or []),
                duration,
            )

    def _parse_ai_content(self, content, product_name=False, lang_code=False):
        parsed = super()._parse_ai_content(
            content,
            product_name=product_name,
            lang_code=lang_code,
        )
        raw_data = self._extract_first_ai_dict(content)
        raw_data = self._unwrap_json_field_payload(raw_data)
        if not isinstance(raw_data, dict):
            return parsed
        for key in (
            "review_required",
            "missing_information",
            "confidence_score",
            "classification",
            "classification_confidence",
        ):
            if key in raw_data:
                parsed[key] = raw_data[key]
        return parsed

    def _build_ai_product_prompt(self, product_name, lang_code, product_context=None):
        self.ensure_one()
        source_bundle = self._build_product_source_bundle(product_name, product_context=product_context)
        return self._build_ai_product_prompt_from_bundle(product_name, lang_code, source_bundle)

    def _build_ai_product_prompt_from_bundle(self, product_name, lang_code, source_bundle):
        language = "Arabic" if lang_code == "ar_001" else "English"
        classification = (source_bundle or {}).get("classification") or {}
        product_type = classification.get("classification") or "general_product"
        context_text = json.dumps(
            source_bundle,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return (
            "%(system)s "
            "Language=%(language)s. Product=%(product_name)s. Product classification=%(product_type)s. "
            "Structured source bundle=%(context)s. "
            "%(variant)s "
            "Return this existing backward-compatible schema exactly, with the metadata keys included: "
            "{"
            "\"meta_title\":\"\","
            "\"meta_description\":\"\","
            "\"keywords\":\"\","
            "\"slug\":\"\","
            "\"short_description\":\"\","
            "\"public_description\":\"\","
            "\"active_ingredient\":\"\","
            "\"warnings\":\"\","
            "\"contraindications\":\"\","
            "\"storage\":\"\","
            "\"drug_data\":{},"
            "\"review_required\":true,"
            "\"missing_information\":[],"
            "\"confidence_score\":0.0,"
            "\"classification\":\"%(product_type)s\","
            "\"classification_confidence\":%(classification_confidence)s"
            "}. "
            "Keep active_ingredient, warnings, contraindications, and storage empty unless those exact facts are present in trusted_facts. "
            "Never include dosage, side effects, clinical claims, regulatory claims, pregnancy advice, breastfeeding advice, or interactions unless present in trusted_facts."
        ) % {
            "system": self._seo_enhancement_system_prompt(),
            "variant": self._seo_enhancement_variant_prompt(product_type),
            "language": language,
            "product_name": product_name or "",
            "product_type": product_type,
            "classification_confidence": classification.get("classification_confidence") or 0.0,
            "context": context_text,
        }

    def _seo_enhancement_system_prompt(self):
        return (
            "Return compact valid JSON only, no markdown. "
            "You generate ecommerce SEO content for a pharmacy website. "
            "Trusted source facts are read-only and must not be changed. "
            "AI generated content is limited to meta_title, meta_description, keywords, slug, short_description, and public_description. "
            "If a trusted fact is unavailable, leave related factual output empty and list it in missing_information. "
            "Do not invent medical, pharmaceutical, regulatory, dosage, contraindication, side-effect, interaction, storage, pregnancy, breastfeeding, or clinical information."
        )

    def _seo_enhancement_variant_prompt(self, product_type):
        prompts = {
            "medicine": (
                "Medicine rules: be conservative, use source facts only, avoid treatment promises, and require review. "
                "Use pharmacist/leaflet wording when source facts are incomplete."
            ),
            "supplement": (
                "Supplement rules: be conservative, avoid disease treatment or cure claims, and only mention ingredients when present in trusted facts."
            ),
            "medical_device": (
                "Medical device rules: focus on supported usage context and product type. Do not make unsupported diagnostic, clinical, or regulatory claims."
            ),
            "cosmetic": (
                "Cosmetic rules: write rich but safe marketing-style SEO. You may use common product-category knowledge for usage, consumer benefits, and application guidance. "
                "Do not invent ingredients, clinical claims, medical claims, or regulatory claims."
            ),
            "personal_care": (
                "Personal care rules: write rich practical SEO similar to cosmetic products. You may describe common usage and consumer benefits. "
                "Do not invent ingredients, clinical claims, medical claims, or regulatory claims."
            ),
            "general_product": (
                "General product rules: write standard ecommerce SEO from product name, category, manufacturer, and existing descriptions. Avoid medical claims."
            ),
        }
        return prompts.get(product_type) or prompts["general_product"]

    def _sanitize_generated_product_content(self, content, source_bundle):
        content = dict(content or {})
        source_bundle = source_bundle or {}
        facts = (source_bundle or {}).get("trusted_facts") or {}
        classification = (source_bundle or {}).get("classification") or {}
        missing = list(source_bundle.get("missing_information") or [])
        product_type = classification.get("classification") or "general_product"

        content = self._clean_generated_content_text_fields(content)
        self._ensure_category_description_template(content, facts, product_type)

        trusted_active = facts.get("effective_material") or facts.get("scientific_name") or ""
        content["active_ingredient"] = trusted_active or False
        content["warnings"] = False
        content["contraindications"] = False
        content["storage"] = False

        drug_data = content.get("drug_data") if isinstance(content.get("drug_data"), dict) else {}
        safe_drug_data = {
            "scientific_name": facts.get("scientific_name") or "",
            "commercial_names": facts.get("product_name") or "",
            "active_ingredient": trusted_active or "",
            "drug_class": product_type,
            "source_label": _("Trusted Odoo product facts with AI-generated SEO copy"),
            "source_type": "odoo",
        }
        if product_type in ("cosmetic", "personal_care", "general_product", "medical_device"):
            for key in ("common_uses",):
                if drug_data.get(key):
                    safe_drug_data[key] = drug_data[key]
        content["drug_data"] = safe_drug_data

        content["classification"] = product_type
        content["classification_confidence"] = classification.get("classification_confidence") or 0.0
        content["missing_information"] = self._deduplicate_missing_information(
            list(content.get("missing_information") or []) + missing
        )
        content["review_required"] = self._review_required_for_generated_content(content, product_type)
        content["confidence_score"] = self._safe_float(
            content.get("confidence_score"),
            fallback=content["classification_confidence"],
        )
        content["source_summary"] = content.get("source_summary") or _(
            "Generated from enriched trusted product context. Factual medical fields are source-only."
        )
        return content

    def _clean_generated_content_text_fields(self, content):
        clean = dict(content or {})
        field_fallbacks = {
            "meta_title": ("title",),
            "meta_description": ("description", "short_description"),
            "keyword_text": ("keywords",),
            "keywords": ("keyword_text",),
            "seo_name": ("slug",),
            "slug": ("seo_name",),
            "short_description": ("meta_description", "description"),
            "public_description": ("short_description", "meta_description", "description"),
        }
        for field_name, fallback_fields in field_fallbacks.items():
            clean[field_name] = self._clean_generated_text_value(
                clean.get(field_name),
                field_name,
                clean,
                fallback_fields,
            )
        return clean

    def _clean_generated_text_value(self, value, field_name, data, fallback_fields=()):
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(item) for item in value if item)
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            return ""
        if self._looks_like_raw_json_payload(text):
            return ""
        nested = self._extract_first_ai_dict(text)
        if nested:
            for candidate in (field_name, *fallback_fields):
                nested_value = nested.get(candidate)
                if nested_value not in (None, False, "", []):
                    if candidate == field_name and str(nested_value).strip() == text:
                        continue
                    return self._clean_generated_text_value(nested_value, field_name, nested, fallback_fields)
            return ""
        text = re.sub(r"^```(?:json)?|```$", "", text).strip()
        if text.startswith("{") or text.startswith("["):
            return ""
        return text

    def _looks_like_raw_json_payload(self, value):
        text = re.sub(r"<[^>]+>", " ", str(value or ""))
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return False
        if text.startswith("{{") or text.startswith("{") or text.startswith("["):
            return True
        return bool(
            ("\"meta_title\"" in text or "\"public_description\"" in text or "\"drug_data\"" in text)
            and ("{" in text or "[" in text)
        )

    def _ensure_category_description_template(self, content, facts, product_type):
        product_name = facts.get("product_name") or content.get("meta_title") or _("this product")
        manufacturer = facts.get("manufacturer") or ""
        category_path = facts.get("category_path") or ""
        if not content.get("meta_description"):
            content["meta_description"] = self._default_meta_description(
                product_name, manufacturer, category_path, product_type
            )
        if not content.get("short_description"):
            content["short_description"] = content["meta_description"]
        if not content.get("public_description"):
            content["public_description"] = self._default_public_description(
                product_name, manufacturer, category_path, product_type
            )
        elif not self._looks_like_html(content["public_description"]):
            content["public_description"] = self._html_paragraph(content["public_description"])
        if not content.get("meta_title"):
            content["meta_title"] = product_name
        if not (content.get("keyword_text") or content.get("keywords")):
            content["keyword_text"] = ", ".join(
                part for part in [product_name, manufacturer, category_path.replace(" / ", ", ")] if part
            )[:255]
        if not (content.get("seo_name") or content.get("slug")):
            content["seo_name"] = product_name

    def _default_meta_description(self, product_name, manufacturer, category_path, product_type):
        if self._is_fragrance_product(product_name, category_path):
            return _("Shop %(product)s, a fragrance product, from Abdin Pharmacies with clear product details.") % {
                "product": product_name,
            }
        if product_type in ("cosmetic", "personal_care"):
            return _("Shop %(product)s for daily personal care from Abdin Pharmacies with clear product details.") % {
                "product": product_name,
            }
        if product_type == "medical_device":
            return _("Find %(product)s device information at Abdin Pharmacies with clear product details.") % {
                "product": product_name,
            }
        if product_type in ("medicine", "supplement"):
            return _("Find product information for %(product)s at Abdin Pharmacies. Always follow leaflet or pharmacist guidance.") % {
                "product": product_name,
            }
        return _("Shop %(product)s from Abdin Pharmacies with clear and updated product information.") % {
            "product": product_name,
        }

    def _default_public_description(self, product_name, manufacturer, category_path, product_type):
        if self._is_fragrance_product(product_name, category_path):
            parts = [
                _("%s is a fragrance product available from Abdin Pharmacies.") % product_name,
                manufacturer and _("Brand or manufacturer: %s.") % manufacturer,
                _("Suitable for customers looking for a refined personal fragrance choice."),
                _("Review the product packaging for full details before use."),
            ]
            return self._html_paragraph(" ".join(part for part in parts if part))
        if product_type in ("cosmetic", "personal_care"):
            parts = [
                _("%s is a personal care product available from Abdin Pharmacies.") % product_name,
                manufacturer and _("Brand or manufacturer: %s.") % manufacturer,
                category_path and _("Category: %s.") % category_path,
                _("Use according to the product packaging instructions."),
            ]
            return self._html_paragraph(" ".join(part for part in parts if part))
        if product_type == "medical_device":
            return self._html_paragraph(
                _("%s is a medical device product available from Abdin Pharmacies. Review the product manual and packaging before use.") % product_name
            )
        if product_type in ("medicine", "supplement"):
            return self._html_paragraph(
                _("%s product information is available from Abdin Pharmacies. Always follow the leaflet or ask a pharmacist before use.") % product_name
            )
        return self._html_paragraph(
            _("%s is available from Abdin Pharmacies with clear and updated product information.") % product_name
        )

    def _looks_like_html(self, value):
        return bool(re.search(r"<\s*(p|div|ul|ol|li|br|section|h[1-6])\b", str(value or ""), flags=re.IGNORECASE))

    def _html_paragraph(self, text):
        if not text:
            return False
        lines = str(html_escape(text)).splitlines() or [""]
        return "<p>%s</p>" % "<br/>".join(lines)

    def _review_required_for_generated_content(self, content, product_type):
        if product_type in ("medicine", "supplement", "medical_device"):
            return True
        if content.get("missing_information"):
            return True
        text = " ".join(str(content.get(key) or "") for key in (
            "meta_title",
            "meta_description",
            "short_description",
            "public_description",
        )).lower()
        return self._has_any(text, self._clinical_claim_terms())

    def _classification_haystack(self, facts):
        values = []
        for key in (
            "product_name",
            "manufacturer",
            "category_path",
            "scientific_name",
            "scientific_group",
            "effective_material",
            "usage_manner",
            "origin",
        ):
            values.append(str(facts.get(key) or ""))
        descriptions = facts.get("existing_descriptions")
        if isinstance(descriptions, dict):
            values += [str(value or "") for value in descriptions.values()]
        return " ".join(values).lower()

    def _term_matches(self, text, terms):
        return [term for term in terms if term in (text or "")]

    def _has_any(self, text, terms):
        return bool(self._term_matches(text, terms))

    def _deduplicate_missing_information(self, values):
        result = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    def _safe_float(self, value, fallback=0.0):
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return round(float(fallback or 0.0), 2)

    def _medicine_terms(self):
        return (
            "tablet", "tab", "capsule", "cap", "syrup", "suspension", "injection",
            "antibiotic", "analgesic", "pain relief", "fever", "oral", "drops",
            "paracetamol", "amoxicillin", "clavulanate", "augmentin", "panadol",
        )

    def _supplement_terms(self):
        return (
            "vitamin", "mineral", "supplement", "omega", "zinc", "magnesium",
            "calcium", "iron", "multivitamin", "probiotic",
        )

    def _medical_device_terms(self):
        return (
            "meter", "test", "strip", "nebulizer", "device", "accu-chek",
            "glucometer", "thermometer", "monitor", "blood pressure", "lancet",
        )

    def _cosmetic_terms(self):
        return (
            "cream", "lotion", "deodorant", "makeup", "skin care", "skincare",
            "beauty", "cosmetic", "cleanser", "moisturizer", "collagen",
            "vitamin e cream", "dove", "cetaphil", "perfume", "parfum",
            "fragrance", "eau de parfum", "eau de toilette", "edt", "edp",
        )

    def _personal_care_terms(self):
        return (
            "shampoo", "soap", "oral care", "body care", "toothpaste",
            "toothbrush", "mouthwash", "hair care", "hand wash", "sanitizer",
        )

    def _clinical_claim_terms(self):
        return (
            "cure", "treats", "treatment for", "diagnose", "prevents disease",
            "contraindicated", "dose", "dosage", "side effects", "pregnancy",
            "breastfeeding", "interaction",
        )

    def _is_fragrance_product(self, product_name, category_path=False):
        text = "%s %s" % (product_name or "", category_path or "")
        return self._has_any(
            text.lower(),
            ("perfume", "parfum", "fragrance", "eau de parfum", "eau de toilette", "edt", "edp"),
        )
