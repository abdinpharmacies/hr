from odoo import models


class AbProductSeoBulkOptimization(models.Model):
    _inherit = "ab.product.seo.bulk.optimization"

    def _get_product_generation_context(self, template):
        context = super()._get_product_generation_context(template)
        product = template.ab_product_id.sudo()
        localized = template
        existing_descriptions = {
            "product_description": product.description or False,
            "description_sale": template.description_sale or False,
            "description_ecommerce": template.description_ecommerce or False,
            "website_description": getattr(template, "website_description", False) or False,
        }
        existing_seo = {
            "website_meta_title": localized.website_meta_title or False,
            "website_meta_description": localized.website_meta_description or False,
            "website_meta_keywords": localized.website_meta_keywords or False,
            "seo_name": localized.seo_name or False,
        }
        scientific_group = ", ".join(product.scientific_groups_ids.mapped("name"))
        category_path = " / ".join(product.groups_ids.mapped("name"))
        context.update({
            "product_name": self._get_product_name_for_generation(template),
            "product_code": product.code or False,
            "eplus_serial": product.eplus_serial or False,
            "barcodes": ", ".join(product.barcode_ids.mapped("name")),
            "manufacturer": product.company_id.name or False,
            "category_path": category_path or context.get("group_path") or False,
            "scientific_name": scientific_group or False,
            "scientific_group": scientific_group or False,
            "effective_material": product.effective_material or False,
            "effective_material_conc": str(product.effective_material_conc or "") or False,
            "usage_manner": product.usage_manner_id.name or False,
            "origin": product.origin_id.name or product.origin or False,
            "is_medicine": bool(getattr(product, "is_medicine", False)),
            "existing_descriptions": existing_descriptions,
            "existing_seo": existing_seo,
            "source_bundle_version": "1.0",
        })
        source_bundle = self.env["ab.seo.assistant"]._build_product_source_bundle(
            context.get("product_name"),
            product_context=context,
        )
        classification = source_bundle.get("classification") or {}
        context.update({
            "classification": classification.get("classification") or "general_product",
            "classification_confidence": classification.get("classification_confidence") or 0.0,
            "missing_information": source_bundle.get("missing_information") or [],
            "source_bundle": source_bundle,
        })
        return context

    def _write_native_product_seo(self, template, content, lang_code):
        context = self._get_product_generation_context(template)
        assistant = self.assistant_id or self.env["ab.seo.assistant"]
        source_bundle = context.get("source_bundle") or assistant._build_product_source_bundle(
            context.get("product_name"),
            product_context=context,
        )
        content = assistant._sanitize_generated_product_content(content or {}, source_bundle)
        vals = {
            "website_meta_title": (content.get("meta_title") or "")[:255],
            "website_meta_description": (content.get("meta_description") or content.get("short_description") or "")[:255],
            "website_meta_keywords": (content.get("keyword_text") or content.get("keywords") or "")[:255],
            "seo_name": content.get("seo_name") or False,
        }
        public_description = content.get("public_description") or content.get("short_description") or content.get("meta_description")
        if self.publish_description:
            vals["description_ecommerce"] = public_description or False
            if (
                "website_description" in template._fields
                and (template.website_description or False) == (public_description or False)
            ):
                vals["website_description"] = False
        vals = {key: value for key, value in vals.items() if key in template._fields and value not in (None, "")}
        if vals:
            write_context = {"lang": lang_code}
            if self.website_id:
                write_context["website_id"] = self.website_id.id
            template.with_context(**write_context).sudo().write(vals)
        return True
