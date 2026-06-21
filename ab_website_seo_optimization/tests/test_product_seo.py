import json
import tempfile
from urllib.error import HTTPError

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged("post_install", "-at_install")
class TestProductSeo(TransactionCase):

    def setUp(self):
        super().setUp()
        self.product_card = self.env["ab_product_card"].create({
            "name": "Panadol Extra",
            "description": "Pain relief product.",
        })
        self.ab_product = self.env["ab_product"].create({
            "product_card_id": self.product_card.id,
            "code": "SEO-PANADOL",
            "default_price": 50.0,
            "allow_sale": True,
        })
        self.template = self.env["product.template"].create({
            "name": "Panadol Extra",
            "ab_product_id": self.ab_product.id,
            "sale_ok": True,
            "is_published": True,
        })

    def test_seo_record_uses_one_product_bulk_optimization(self):
        seo = self.env["ab.product.seo"].create({
            "product_template_id": self.template.id,
        })

        seo.action_generate_draft()
        self.assertEqual(seo.state, "published")
        self.assertEqual(seo.target, "products")
        self.assertEqual(seo.batch_limit, 1)
        self.assertEqual(seo.lang_mode, "all")
        self.assertTrue(seo.only_missing_seo)
        self.assertTrue(seo.publish_description)
        self.assertEqual(seo.rate_limit_retry_count, 3)
        self.assertEqual(seo.rate_limit_wait_seconds, 0)
        self.assertTrue(seo.last_bulk_id)
        self.assertEqual(seo.last_bulk_id.batch_limit, 1)
        self.assertEqual(seo.result_status, "optimized")
        self.assertTrue(seo.translation_ids.filtered(lambda rec: rec.meta_title))
        self.assertTrue(self.template.website_meta_title)
        self.assertTrue(self.template.website_meta_description)
        self.assertTrue(self.template.website_meta_keywords)
        self.assertTrue(seo.published_version_id)
        self.assertTrue(seo.en_meta_title)
        self.assertTrue(seo.ar_meta_title)

    def test_seo_record_complete_product_requires_confirmation(self):
        self.template.write({
            "website_meta_title": "Complete SEO Product",
            "website_meta_description": "Complete description",
            "website_meta_keywords": "complete, seo",
            "description_ecommerce": "<p>Complete ecommerce description</p>",
        })
        self.template.with_context(lang="ar_001").write({
            "website_meta_title": "منتج مكتمل",
            "website_meta_description": "وصف مكتمل",
            "website_meta_keywords": "مكتمل, سيو",
            "description_ecommerce": "<p>وصف مكتمل</p>",
        })
        seo = self.env["ab.product.seo"].create({
            "product_template_id": self.template.id,
            "only_missing_seo": True,
        })

        action = seo.action_generate_draft()

        self.assertEqual(action["res_model"], "ab.product.seo.optimize.confirm.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(seo.result_status, "not_run")
        self.assertFalse(seo.en_meta_title)
        self.assertFalse(seo.ar_meta_title)

    def test_seo_record_confirmation_updates_complete_product(self):
        self.template.write({
            "website_meta_title": "Complete SEO Product",
            "website_meta_description": "Complete description",
            "website_meta_keywords": "complete, seo",
            "description_ecommerce": "<p>Complete ecommerce description</p>",
        })
        self.template.with_context(lang="ar_001").write({
            "website_meta_title": "منتج مكتمل",
            "website_meta_description": "وصف مكتمل",
            "website_meta_keywords": "مكتمل, سيو",
            "description_ecommerce": "<p>وصف مكتمل</p>",
        })
        seo = self.env["ab.product.seo"].create({
            "product_template_id": self.template.id,
            "only_missing_seo": True,
        })
        action = seo.action_generate_draft()
        wizard = self.env[action["res_model"]].browse(action["res_id"])

        wizard.action_optimize_and_update()

        self.assertEqual(seo.result_status, "optimized")
        self.assertEqual(seo.optimized_count, 1)
        self.assertEqual(seo.state, "published")
        self.assertNotEqual(seo.en_meta_title, "Complete SEO Product")
        self.assertNotEqual(seo.ar_meta_title, "منتج مكتمل")

    def test_seo_record_product_selector_contains_published_products(self):
        complete_product = self.env["ab_product"].create({
            "product_card_id": self.product_card.id,
            "code": "SEO-SELECTOR-COMPLETE",
            "default_price": 60.0,
            "allow_sale": True,
        })
        complete_template = self.env["product.template"].create({
            "name": "Selector Complete SEO Product",
            "ab_product_id": complete_product.id,
            "sale_ok": True,
            "is_published": True,
            "website_meta_title": "Complete SEO Product",
            "website_meta_description": "Complete description",
            "website_meta_keywords": "complete, seo",
            "description_ecommerce": "<p>Complete ecommerce description</p>",
        })
        complete_template.with_context(lang="ar_001").write({
            "website_meta_title": "منتج مكتمل",
            "website_meta_description": "وصف مكتمل",
            "website_meta_keywords": "مكتمل, سيو",
            "description_ecommerce": "<p>وصف مكتمل</p>",
        })
        seo = self.env["ab.product.seo"].create({
            "product_template_id": self.template.id,
            "only_missing_seo": True,
        })

        self.assertIn(self.template, seo.available_product_template_ids)
        self.assertIn(complete_template, seo.available_product_template_ids)

    def test_seo_records_are_archived_not_deleted(self):
        seo = self.env["ab.product.seo"].create({
            "product_template_id": self.template.id,
        })
        with self.assertRaises(UserError):
            seo.unlink()

    def test_bulk_optimization_publishes_only_published_products(self):
        unpublished_template = self.env["product.template"].create({
            "name": "Unpublished SEO Product",
            "sale_ok": True,
        })
        bulk = self.env["ab.product.seo.bulk.optimization"].create({
            "name": "Bulk SEO Test",
            "batch_limit": 1,
            "lang_mode": "en_US",
        })

        bulk.action_fill_with_ai_for_published_products()
        self.assertEqual(bulk.state, "queued")
        bulk._run_bulk_optimization()
        self.assertEqual(bulk.state, "done")
        self.assertGreaterEqual(bulk.optimized_count, 1)
        self.assertTrue(self.template.website_meta_title)
        self.assertTrue(self.template.website_meta_description)
        self.assertTrue(self.template.website_meta_keywords)
        self.assertFalse(unpublished_template.website_meta_title)

    def test_bulk_optimization_batches_only_abdin_linked_products(self):
        unlinked_templates = self.env["product.template"]
        for index in range(3):
            unlinked_templates |= self.env["product.template"].create({
                "name": "Unlinked Published Product %s" % index,
                "sale_ok": True,
                "is_published": True,
            })
        bulk = self.env["ab.product.seo.bulk.optimization"].create({
            "name": "Bulk Linked Product Test",
            "batch_limit": 1,
            "lang_mode": "en_US",
        })

        selected_templates = bulk._get_published_products()
        self.assertTrue(selected_templates)
        self.assertFalse(selected_templates & unlinked_templates)
        self.assertTrue(all(selected_templates.mapped("ab_product_id")))

    def test_only_missing_seo_filters_complete_products_before_limit(self):
        complete_product = self.env["ab_product"].create({
            "product_card_id": self.product_card.id,
            "code": "SEO-COMPLETE",
            "default_price": 60.0,
            "allow_sale": True,
        })
        complete_template = self.env["product.template"].create({
            "name": "Complete SEO Product",
            "ab_product_id": complete_product.id,
            "sale_ok": True,
            "is_published": True,
            "website_meta_title": "Complete SEO Product",
            "website_meta_description": "Complete description",
            "website_meta_keywords": "complete, seo",
            "description_ecommerce": "<p>Complete ecommerce description</p>",
        })
        bulk = self.env["ab.product.seo.bulk.optimization"].create({
            "name": "Only Missing SEO Selection Test",
            "batch_limit": 1,
            "lang_mode": "en_US",
            "only_missing_seo": True,
            "publish_description": True,
        })
        current_candidates = bulk._get_published_products(limit=100)
        for template in current_candidates.filtered(lambda rec: rec not in (self.template | complete_template)):
            bulk._create_line("optimized", "Existing fixture excluded from selection test.", template=template)

        selected_templates = bulk._get_published_products(limit=1)

        self.assertEqual(selected_templates, self.template)
        self.assertNotIn(complete_template, selected_templates)

    def test_bulk_optimization_can_be_cancelled(self):
        bulk = self.env["ab.product.seo.bulk.optimization"].create({
            "name": "Cancelled Bulk SEO Test",
            "batch_limit": 10,
            "lang_mode": "en_US",
        })

        bulk.action_fill_with_ai_for_published_products()
        bulk.action_cancel_batch()

        self.assertEqual(bulk.state, "cancelled")
        self.assertTrue(bulk.finished_at)
        self.assertTrue(bulk.line_ids.filtered(lambda line: line.status == "cancelled"))

    def test_bulk_optimization_updates_arabic_page_content(self):
        self.template.with_context(lang="ar_001").write({
            "website_meta_title": "عنوان قديم",
            "website_meta_description": "وصف قديم",
            "website_meta_keywords": "قديم",
            "description_ecommerce": False,
        })
        bulk = self.env["ab.product.seo.bulk.optimization"].create({
            "name": "Arabic Bulk SEO Test",
            "batch_limit": 1,
            "lang_mode": "ar_001",
            "only_missing_seo": True,
            "publish_description": True,
        })

        bulk.action_fill_with_ai_for_published_products()
        self.assertEqual(bulk.state, "queued")
        bulk._run_bulk_optimization()
        arabic_template = self.template.with_context(lang="ar_001")
        self.assertTrue(arabic_template.description_ecommerce)
        self.assertIn("صيدليات عابدين", arabic_template.website_meta_title)
        self.assertIn("صيدليات عابدين", arabic_template.website_meta_description)

    def test_bulk_optimization_updates_published_website_pages(self):
        view = self.env["ir.ui.view"].create({
            "name": "SEO Bulk Page",
            "type": "qweb",
            "key": "ab_website_seo_optimization.bulk_page",
            "arch": "<t name='SEO Bulk Page'><section><h1>Offers</h1><p>Monthly pharmacy offers and services.</p></section></t>",
        })
        page = self.env["website.page"].create({
            "name": "SEO Bulk Page",
            "url": "/seo-bulk-page",
            "view_id": view.id,
            "is_published": True,
            "website_indexed": True,
        })

        bulk = self.env["ab.product.seo.bulk.optimization"].create({
            "name": "Page Bulk SEO Test",
            "target": "pages",
            "batch_limit": 1,
            "lang_mode": "en_US",
        })

        bulk.action_fill_with_ai_for_published_products()
        self.assertEqual(bulk.state, "queued")
        bulk._run_bulk_optimization()
        self.assertEqual(bulk.state, "done")
        self.assertTrue(page.website_meta_title)
        self.assertTrue(page.website_meta_description)
        self.assertTrue(page.website_meta_keywords)
        self.assertTrue(bulk.line_ids.filtered(lambda line: line.website_page_id == page and line.status == "optimized"))

    def test_assistant_configuration_tests(self):
        ready_assistant = self.env["ab.seo.assistant"].create({
            "name": "Ready API Missing Key Test",
            "provider": "ready_api",
            "assistant_type": "data_source",
            "model_name": "ready-api",
            "base_url": "https://ready-api.vercel.app",
            "endpoint_path": "/api/drugs-eg",
        })
        ready_assistant.action_test_configuration()
        self.assertEqual(ready_assistant.assistant_type, "data_source")
        self.assertEqual(ready_assistant.test_status, "missing_key")
        self.assertIn("no API key", ready_assistant.last_test_message)

        gemini = self.env["ab.seo.assistant"].create({
            "name": "Gemini Missing Key Test",
            "provider": "google_gemini",
            "assistant_type": "ai",
            "model_name": "gemini-3.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "endpoint_path": "/models/{model}:generateContent",
        })
        gemini.action_test_configuration()
        self.assertEqual(gemini.test_status, "missing_key")

    def test_drug_eg_api_data_upsert_uses_structured_response(self):
        item = {
            "commercial_name_en": "1 2 3 (ONE TWO THREE) 20 F.C.TABS.",
            "commercial_name_ar": "1 2 3",
            "scientific_name": "CHLORPHENIRAMINE+PARACETAMOL(ACETAMINOPHEN)+PSEUDOEPHEDRINE",
            "manufacturer": "HIKMA PHARMA",
            "drug_class": "COLD PRODUCTS",
            "route": "oral",
            "price_egp": 10,
        }

        drug_data = self.env["ab.product.drug.data"].upsert_from_drug_eg_item(
            item,
            source_url="https://ready-api.vercel.app/api/drugs-eg?page=1&limit=100",
        )
        updated = self.env["ab.product.drug.data"].upsert_from_drug_eg_item({
            **item,
            "price_egp": 64,
        })

        self.assertEqual(drug_data, updated)
        self.assertEqual(drug_data.product_name, "1 2 3 (ONE TWO THREE) 20 F.C.TABS.")
        self.assertEqual(drug_data.commercial_name_en, "1 2 3 (ONE TWO THREE) 20 F.C.TABS.")
        self.assertEqual(drug_data.commercial_name_ar, "1 2 3")
        self.assertEqual(drug_data.scientific_name, "CHLORPHENIRAMINE+PARACETAMOL(ACETAMINOPHEN)+PSEUDOEPHEDRINE")
        self.assertEqual(drug_data.manufacturer, "HIKMA PHARMA")
        self.assertEqual(drug_data.drug_class, "COLD PRODUCTS")
        self.assertEqual(drug_data.price, 64.0)
        self.assertIn("commercial_name_ar", drug_data.raw_payload)

    def test_assistant_token_usage_is_tracked(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "Token Usage Test",
            "provider": "openrouter",
            "assistant_type": "ai",
            "model_name": "nex-agi/nex-n2-pro:free",
            "base_url": "https://openrouter.ai/api/v1",
            "endpoint_path": "/chat/completions",
        })
        usage = assistant._extract_token_usage({
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25,
            }
        })
        assistant._increment_usage(token_usage=usage)

        self.assertEqual(assistant.used_today, 1)
        self.assertEqual(assistant.prompt_tokens_today, 10)
        self.assertEqual(assistant.completion_tokens_today, 15)
        self.assertEqual(assistant.total_tokens_today, 25)
        self.assertEqual(assistant.lifetime_total_tokens, 25)
        self.assertEqual(assistant.last_total_tokens, 25)

    def test_gemini_token_usage_is_tracked(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "Gemini Token Usage Test",
            "provider": "google_gemini",
            "assistant_type": "ai",
            "model_name": "gemini-3.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "endpoint_path": "/models/{model}:generateContent",
        })
        usage = assistant._extract_token_usage({
            "usageMetadata": {
                "promptTokenCount": 7,
                "candidatesTokenCount": 11,
                "totalTokenCount": 18,
            }
        })

        self.assertEqual(usage["prompt_tokens"], 7)
        self.assertEqual(usage["completion_tokens"], 11)
        self.assertEqual(usage["total_tokens"], 18)

    def test_ai_parser_accepts_wrapped_json(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "Wrapped JSON Parser Test",
            "provider": "google_gemini",
            "assistant_type": "ai",
            "model_name": "gemini-3.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "endpoint_path": "/models/{model}:generateContent",
        })
        content = """Here is the JSON:
```json
{"meta_title":"Panadol","meta_description":"Pain relief product","drug_data":{"common_uses":"Pain relief","source_label":"Gemini"}}
```
"""

        result = assistant._parse_ai_content(content)

        self.assertEqual(result["meta_title"], "Panadol")
        self.assertEqual(result["drug_data"]["common_uses"], "Pain relief")

    def test_ai_parser_falls_back_for_plain_text(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "Gemini Plain Text Parser Test",
            "provider": "google_gemini",
            "assistant_type": "ai",
            "model_name": "gemini-3.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "endpoint_path": "/models/{model}:generateContent",
        })

        result = assistant._parse_ai_content(
            "Panadol Extra is a pain relief product available from Abdin Pharmacies.",
            product_name="Panadol Extra",
            lang_code="en_US",
        )

        self.assertEqual(result["meta_title"], "Panadol Extra")
        self.assertIn("pain relief", result["meta_description"])
        self.assertIn("non-JSON", result["source_summary"])

    def test_ai_parser_accepts_json_array(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "Gemini Array Parser Test",
            "provider": "google_gemini",
            "assistant_type": "ai",
            "model_name": "gemini-3.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "endpoint_path": "/models/{model}:generateContent",
        })

        result = assistant._parse_ai_content('[{"meta_title":"Panadol","meta_description":"Pain relief"}]')

        self.assertEqual(result["meta_title"], "Panadol")
        self.assertEqual(result["meta_description"], "Pain relief")

    def test_ai_parser_normalizes_seo_component_response(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "SEO Component Parser Test",
            "provider": "google_gemini",
            "assistant_type": "ai",
            "model_name": "gemini-3.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "endpoint_path": "/models/{model}:generateContent",
        })

        result = assistant._parse_ai_seo_component_content(
            '{"title":"Dove Powder Stick 74g","description":"Shop Dove Powder Stick 74g with clear product information from Abdin Pharmacies.","keywords":["Dove Powder","deodorant","personal care"],"slug":"dove-powder-stick-74g"}',
            component_name="Dove Powder Stick 74g",
            lang_code="en_US",
        )

        self.assertEqual(result["title"], "Dove Powder Stick 74g")
        self.assertIn("Abdin Pharmacies", result["description"])
        self.assertEqual(result["keywords"][0], "Dove Powder")
        self.assertEqual(result["slug"], "dove-powder-stick-74g")

    def test_ai_parser_removes_nested_json_from_seo_component_fields(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "SEO Component Nested JSON Parser Test",
            "provider": "google_gemini",
            "assistant_type": "ai",
            "model_name": "gemini-3.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "endpoint_path": "/models/{model}:generateContent",
        })

        result = assistant._parse_ai_seo_component_content(
            '{"title":"{\\"title\\":\\"Luna Emollient Collagen & Vitamin E Cream 20gm | Abdeen\\",\\"description\\":\\"Shop Luna Emollient Collagen and Vitamin E Cream 20gm for daily skin hydration from Abdin Pharmacies.\\",\\"keywords\\":[\\"Luna cream\\",\\"collagen cream\\"],\\"slug\\":\\"luna-emollient-collagen-vitamin-e-cream-20gm\\"}"}',
            component_name="Luna Emollient Collagen & Vitamin E Cream 20gm",
            lang_code="en_US",
        )

        self.assertNotIn("{", result["title"])
        self.assertNotIn('"title"', result["description"])
        self.assertEqual(result["title"], "Luna Emollient Collagen & Vitamin E Cream 20gm | Abdeen")
        self.assertIn("daily skin hydration", result["description"])

    def test_ai_parser_maps_malformed_product_schema_to_seo_component_fields(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "SEO Component Malformed Product Schema Test",
            "provider": "google_gemini",
            "assistant_type": "ai",
            "model_name": "gemini-3.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "endpoint_path": "/models/{model}:generateContent",
        })
        content = (
            '{"meta_title":"LUNA EMOLLIENT COLLAGEN &VITAMIN E CREAM 20GM 1 UNIT",'
            '"meta_description":"LUNA EMOLLIENT COLLAGEN &VITAMIN E CREAM 20GM 1 UNIT product details and benefits",'
            '"keywords":"LUNA EMOLLIENT COLLAGEN &VITAMIN E CREAM 20GM 1 UNIT",'
            '"slug":"luna-emollient-collagen-vitamin-e-cream-20gm-1-unit",'
            '"short_description":"Moisturizing cream with collagen and vitamin E for skin care",'
            '"public_description":"LUNA EMOLLIENT COLLAGEN &VITAMIN E CREAM 20GM 1 UNIT is a rich and nourishing moisturizing cream.",'
            '"drug_data":{"drug_class":"cosmetic","warnings":"Avoid using on broken or irritated skin",}'
        )

        result = assistant._parse_ai_seo_component_content(
            content,
            component_name="Luna Emollient Collagen & Vitamin E Cream 20gm",
            lang_code="en_US",
        )

        self.assertNotIn("{", result["description"])
        self.assertEqual(result["title"], "LUNA EMOLLIENT COLLAGEN &VITAMIN E CREAM 20GM 1 UNIT"[:70])
        self.assertIn("product details and benefits", result["description"])
        self.assertEqual(result["slug"], "luna-emollient-collagen-vitamin-e-cream-20gm-1-unit")

    def test_gemini_payload_requests_json_response(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "Gemini JSON Payload Test",
            "provider": "google_gemini",
            "assistant_type": "ai",
            "model_name": "gemini-3.5-flash",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "endpoint_path": "/models/{model}:generateContent",
        })

        payload = assistant._build_ai_payload("Return JSON")

        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")

    def test_assistant_endpoint_adds_missing_https_scheme(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "URL Normalization Test",
            "provider": "other",
            "assistant_type": "ai",
            "model_name": "demo-model",
            "base_url": "api.example.com/v1",
            "endpoint_path": "/chat/completions",
        })

        self.assertEqual(
            assistant._get_endpoint_url(),
            "https://api.example.com/v1/chat/completions",
        )

    def test_alibaba_qwen_endpoint_uses_workspace_compatible_mode(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "Qwen URL Normalization Test",
            "provider": "alibaba_qwen",
            "assistant_type": "ai",
            "model_name": "Qwen",
            "base_url": "ws-eish2a8n2iixd1b3.ap-southeast-1.maas.aliyuncs.com",
            "endpoint_path": "/models/{model}:generateContent",
        })

        self.assertEqual(
            assistant._get_endpoint_url(),
            "https://ws-eish2a8n2iixd1b3.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/chat/completions",
        )

    def test_alibaba_qwen_defaults_use_singapore_workspace(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "Qwen Defaults Test",
            "provider": "alibaba_qwen",
        })

        assistant.action_apply_provider_defaults()

        self.assertEqual(assistant.assistant_type, "ai")
        self.assertEqual(assistant.model_name, "Qwen")
        self.assertEqual(
            assistant.base_url,
            "https://ws-eish2a8n2iixd1b3.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
        )
        self.assertEqual(assistant.endpoint_path, "/chat/completions")

    def test_openfda_defaults_use_drug_label_endpoint(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "openFDA Defaults Test",
            "provider": "openfda",
        })

        assistant.action_apply_provider_defaults()

        self.assertEqual(assistant.assistant_type, "data_source")
        self.assertEqual(assistant.base_url, "https://api.fda.gov")
        self.assertEqual(assistant.endpoint_path, "/drug/label.json")
        self.assertEqual(assistant.api_key_name, "OPENFDA_API_KEY")
        self.assertEqual(assistant.daily_limit, 120000)

    def test_cosmetic_event_defaults_use_openfda_endpoint(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "Cosmetic Event Defaults Test",
            "provider": "openfda_cosmetic_event",
        })

        assistant.action_apply_provider_defaults()

        self.assertEqual(assistant.assistant_type, "data_source")
        self.assertEqual(assistant.base_url, "https://api.fda.gov")
        self.assertEqual(assistant.endpoint_path, "/cosmetic/event.json")
        self.assertEqual(assistant.api_key_name, "OPENFDA_API_KEY")
        self.assertEqual(assistant.daily_limit, 120000)

    def test_cosmetic_event_file_fallback_summarizes_reactions(self):
        payload = {
            "results": [
                {
                    "reactions": ["Inflammation", "Purpura", "Inflammation"],
                    "outcomes": ["Other Serious or Important Medical Event"],
                    "products": [{"product_name": "Dove Powder Stick 74g"}],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = "%s/cosmetic-event.json" % directory
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
            assistant = self.env["ab.seo.assistant"].create({
                "name": "Cosmetic Event File Test",
                "provider": "openfda_cosmetic_event",
                "assistant_type": "data_source",
                "model_name": "openfda-cosmetic-event",
                "base_url": "https://api.fda.gov",
                "endpoint_path": "/cosmetic/event.json",
                "api_key": "test-key",
            })
            status, message = assistant._test_configuration()
            result = assistant.with_context(
                cosmetic_event_fallback_path=path,
            )._request_cosmetic_event_file_product("Dove Powder Stick 74g")

        self.assertEqual(status, "ready", message)
        self.assertIn("Dove Powder Stick 74g", result["meta_title"])
        self.assertIn("Inflammation", result["warnings"])
        self.assertIn("safety signal", result["public_description"])

    def test_openrouter_404_error_mentions_model(self):
        assistant = self.env["ab.seo.assistant"].create({
            "name": "OpenRouter Error Test",
            "provider": "openrouter",
            "assistant_type": "ai",
            "model_name": "missing/free-model",
            "base_url": "https://openrouter.ai/api/v1",
            "endpoint_path": "/chat/completions",
        })

        class FakeHttpError(HTTPError):
            def read(self):
                return b'{"error":{"message":"No endpoints found for missing/free-model."}}'

        message = assistant._format_http_error(FakeHttpError(
            "https://openrouter.ai/api/v1/chat/completions",
            404,
            "Not Found",
            {},
            None,
        ))

        self.assertIn("missing/free-model", message)
        self.assertIn("No endpoints found", message)
