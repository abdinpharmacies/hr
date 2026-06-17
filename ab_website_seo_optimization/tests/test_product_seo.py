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
        })

    def test_generate_approve_publish_native_fields(self):
        seo = self.env["ab.product.seo"].create({
            "ab_product_id": self.ab_product.id,
        })

        seo.action_generate_draft()
        self.assertEqual(seo.state, "generated")
        self.assertTrue(seo.translation_ids.filtered(lambda rec: rec.meta_title))

        seo.action_submit_review()
        seo.action_approve()
        self.assertEqual(seo.state, "approved")
        self.assertTrue(seo.translation_ids.mapped("current_version_id"))

        seo.action_publish()
        self.assertEqual(seo.state, "published")
        self.assertTrue(self.template.website_meta_title)
        self.assertTrue(self.template.website_meta_description)
        self.assertTrue(self.template.website_meta_keywords)
        self.assertTrue(seo.publish_log_ids)

    def test_seo_records_are_archived_not_deleted(self):
        seo = self.env["ab.product.seo"].create({
            "ab_product_id": self.ab_product.id,
        })
        with self.assertRaises(UserError):
            seo.unlink()

    def test_bulk_optimization_publishes_only_published_products(self):
        unpublished_template = self.env["product.template"].create({
            "name": "Unpublished SEO Product",
            "sale_ok": True,
        })
        self.template.write({"is_published": True})

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

        self.assertTrue(self.template.ab_drug_data_id)
        self.assertTrue(self.template.ab_drug_data_id.common_uses)

    def test_bulk_optimization_batches_only_abdin_linked_products(self):
        unlinked_templates = self.env["product.template"]
        for index in range(3):
            unlinked_templates |= self.env["product.template"].create({
                "name": "Unlinked Published Product %s" % index,
                "sale_ok": True,
                "is_published": True,
            })
        self.template.write({"is_published": True})

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
        self.template.write({"is_published": True})
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
        self.template.write({"is_published": True})

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
        self.assertTrue(self.template.ab_drug_data_id.with_context(lang="ar_001").warnings)

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

    def test_generated_drug_data_uses_structured_response(self):
        drug_data = self.env["ab.product.drug.data"].create({
            "product_template_id": self.template.id,
        })
        drug_data._apply_generated_content({
            "drug_data": {
                "scientific_name": "Ibuprofen",
                "commercial_names": "Advil, Brufen",
                "drug_class": "medicine",
                "regulatory_status": "OTC",
                "common_uses": "Pain, fever, and inflammation relief.",
                "side_effects": "Stomach upset and dizziness may occur.",
                "warnings": "Avoid with active stomach ulcer unless directed by a physician.",
                "pregnancy": "Avoid in third trimester.",
                "breastfeeding": "Ask a pharmacist before use.",
                "storage": "Store below 30C away from moisture.",
                "interactions": "May interact with anticoagulants.",
                "source_label": "Structured API Test",
                "source_type": "assistant",
            }
        }, lang_code="en_US")

        self.assertEqual(drug_data.scientific_name, "Ibuprofen")
        self.assertEqual(drug_data.regulatory_status, "OTC")
        self.assertIn("Pain", drug_data.common_uses)
        self.assertIn("ulcer", drug_data.warnings)
        self.assertNotIn("See product leaflet", drug_data.common_uses)

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
