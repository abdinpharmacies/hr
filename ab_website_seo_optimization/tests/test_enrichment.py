import base64
import io
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

import requests
from lxml import etree

from odoo import fields
from odoo.addons.base.models.ir_ui_view import get_view_arch_from_file
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..services.catalog import CATALOG
from ..services.seo_templates import deterministic
from ..services.datasets import records, spl_records
from ..services.providers import ProviderFailure, adapter, ai_response, gtin, match, validate_draft


@tagged("post_install", "-at_install")
class TestEnrichment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.card = cls.env["ab_product_card"].create({"name": "Enrichment Example"})
        cls.product = cls.env["ab_product"].create({"product_card_id": cls.card.id, "code": "SEO-ENRICHMENT", "allow_sale": True, "effective_material": "Example ingredient"})
        cls.template = cls.env["product.template"].create({"name": "Enrichment Example", "ab_product_id": cls.product.id, "is_published": True, "sale_ok": True})

    def provider(self, key="local_ai", **values):
        return self.env["ab.seo.assistant"].create(dict({"name": key, "provider": key, "model_name": "test-model",
            "assistant_type": "ai" if CATALOG[key]["scope"] == "generation" else "data_source", "base_url": "http://localhost:8000/v1" if key == "local_ai" else CATALOG[key].get("api_url", ""),
            "endpoint_path": "/chat/completions" if CATALOG[key]["scope"] == "generation" else "", "daily_limit": 100, "rpm_limit": 100,
            "license_reviewed": True, "license_review_note": "Test fixture license", "allow_remote": True, "retry_count": 1,
            "backoff_seconds": 0, "models_checked_at": fields.Datetime.now()}, **values))

    def test_enrichment_views_load_from_files(self):
        path = Path(__file__).resolve().parents[1] / "views" / "enrichment_views.xml"
        for node in etree.parse(str(path)).xpath('//record[@model="ir.ui.view"]'):
            xmlid = "ab_website_seo_optimization." + node.get("id")
            with self.subTest(view=xmlid):
                self.assertTrue(get_view_arch_from_file(str(path), xmlid))
        for language in ("en_US", "ar_001"):
            result = self.env["ab.product.seo"].with_context(read_arch_from_file=True, lang=language).get_view(view_type="form")
            self.assertEqual(etree.fromstring(result["arch"]).tag, "form")

    def response(self, status=200, payload=None, headers=None):
        response = Mock()
        response.status_code = status
        response.headers = headers or {}
        response.content = json.dumps(payload or {}).encode()
        response.json.return_value = payload or {"ok": True}
        response.iter_content.side_effect = lambda size: iter([response.content])
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def completion(self, product=None):
        product = product or self.template
        template, _context = self.env['ab_seo_template']._select(product)
        facts = {'name': product.name, 'product_code': product.ab_product_id.code, 'active_ingredients': product.ab_product_id.effective_material}
        content = deterministic(template._contract(), facts, 'en_US', lambda text: text)
        content = {k: v for k, v in content.items() if k in ('meta_title', 'meta_description', 'short_description', 'sections')}
        content['keywords'] = [product.name]
        return {"choices": [{"message": {"content": json.dumps(content)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}

    def pipeline(self, providers, **values):
        return self.env["ab_seo_pipeline"].create(dict({"name": "Test Pipeline", "domain": "general", "ai_mode": "always",
            "line_ids": [(0, 0, {"provider_id": p.id, "sequence": index * 10}) for index, p in enumerate(providers)]}, **values))

    def job(self, pipeline):
        job = self.env["ab.product.seo.bulk.optimization"].create({"name": "Enrichment acceptance", "pipeline_id": pipeline.id, "lang_mode": "en_US", "batch_limit": 100, "enrichment_enabled": True, "generation_mode": "ai", "regeneration_mode": "selected"})
        job.write({"state": "queued", "discovery_done": True, "total_count": 1})
        self.env["ab_seo_work_item"].create({"job_id": job.id, "product_id": self.template.id})
        return job

    def test_registry_and_ordering(self):
        self.assertGreaterEqual(len(CATALOG), 28)
        for key in CATALOG:
            self.assertEqual(adapter(key).key, key)
        a, b = self.provider(), self.provider()
        pipe = self.pipeline([b, a])
        self.assertEqual(pipe._providers(generation=True), b | a)
        b.active = False
        self.assertEqual(pipe._providers(generation=True), a)

    def test_category_routing_and_explicit_product_type(self):
        category = self.env["product.public.category"].create({"name": "Supplements fixture"})
        child = self.env["product.public.category"].create({"name": "Vitamins fixture", "parent_id": category.id})
        pipe = self.pipeline([], domain="supplement", category_ids=[(6, 0, category.ids)])
        self.template.public_categ_ids = child
        job = self.job(pipe)
        job.state = "draft"
        job.pipeline_id = False
        self.assertEqual(job.work_item_ids._select_pipeline(), pipe)
        self.template.ab_enrichment_domain = "food"
        self.assertEqual(job.work_item_ids._select_pipeline().domain, "food")

    def test_quota_wait_survives_repeated_ticks(self):
        provider = self.provider(daily_limit=1, used_today=1, last_used_date=fields.Date.today())
        job = self.job(self.pipeline([provider]))
        item = job.work_item_ids
        item.attempts = 5
        with patch("requests.request") as http:
            job._run_bulk_optimization_chunk()
            http.assert_not_called()
        self.assertEqual(item.state, "waiting")
        self.assertEqual(item.next_attempt_at, provider.disabled_until)
        self.assertEqual(job.processed_count, 0)

    def test_nested_malformed_provider_data(self):
        with TestCase.assertRaises(self, ProviderFailure):
            adapter("openfda").normalize({"openfda": "bad"})
        with TestCase.assertRaises(self, ProviderFailure):
            adapter("rxnorm").lookup({"name": "Example"}, lambda *a, **kw: {"idGroup": "bad"})
        with TestCase.assertRaises(self, ProviderFailure):
            ai_response("local_ai", {"choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": "bad"}})

    def test_rxnorm_attributes_and_relationships(self):
        attribute = b"123|||456|AUI|123|||RXN_STRENGTH|RXNORM|500 MG|N||\n"
        relation = b"789||CUI|RO|123||CUI|has_dose_form|100||RXNORM||||N||\n"
        self.assertEqual(list(records(io.BytesIO(attribute), "RXNSAT.RRF", "rxnorm"))[0]["strength"], "500 MG")
        self.assertEqual(list(records(io.BytesIO(relation), "RXNREL.RRF", "rxnorm"))[0]["scientific_context"]["target_rxcui"], "789")

    def test_acceptance_quota_failure_success_and_resume(self):
        a = self.provider(daily_limit=1, used_today=1, last_used_date=fields.Date.today())
        b = self.provider(base_url="http://localhost:8001/v1", retry_count=1)
        c = self.provider(base_url="http://localhost:8002/v1")
        job = self.job(self.pipeline([a, b, c]))
        with patch("requests.request", side_effect=[self.response(503), self.response(503), self.response(payload=self.completion())]) as http:
            job._run_bulk_optimization_chunk()
        item = job.work_item_ids
        self.assertEqual(item.state, "review_required")
        self.assertEqual(a.health, "quota")
        self.assertEqual(b.health, "cooldown")
        self.assertEqual(c.health, "ready")
        self.assertEqual(http.call_count, 3)
        self.assertEqual(job.processed_count, 1)
        self.assertEqual(job.state, "done")
        self.assertFalse(self.template.website_meta_title)
        evidence_ids = item.fact_ids.ids
        job.action_resume_job()
        with patch("requests.request") as http:
            job._run_bulk_optimization_chunk()
            http.assert_not_called()
        self.assertEqual(item.fact_ids.ids, evidence_ids)
        self.assertEqual(job.processed_count, 1)
        self.assertTrue(any(row.provider_id == c and row.content_kind == "GENERATED_TEXT" for row in item.fact_ids))
        self.assertEqual(c.total_tokens_today, 30)
        self.assertEqual(c.used_today, 1)
        next_product = self.env["ab_product"].create({"product_card_id": self.card.id, "code": "SEO-NEXT", "allow_sale": True, "effective_material": "Example ingredient"})
        next_template = self.env["product.template"].create({"name": "Next Example", "ab_product_id": next_product.id, "is_published": True, "sale_ok": True})
        next_item = self.env["ab_seo_work_item"].create({"job_id": job.id, "product_id": next_template.id})
        job.write({"state": "queued", "total_count": 2})
        with patch("requests.request", return_value=self.response(payload=self.completion(next_template))) as http:
            job._run_bulk_optimization_chunk()
        self.assertEqual(http.call_count, 1)
        self.assertTrue(http.call_args.args[1].startswith("http://localhost:8002/"))
        self.assertEqual(next_item.state, "review_required")
        self.assertEqual(job.processed_count, 2)
        self.assertEqual(job.state, "done")

    def test_429_retry_after_disables_without_sleep(self):
        provider = self.provider()
        with patch("requests.request", return_value=self.response(429, headers={"Retry-After": "120"})) as http, patch("time.sleep") as sleep:
            with TestCase.assertRaises(self, ProviderFailure) as caught:
                provider._request("GET", "/models")
        self.assertEqual(caught.exception.code, "rate_limit")
        self.assertEqual(http.call_count, 1)
        sleep.assert_not_called()
        self.assertGreater(provider.disabled_until, fields.Datetime.now())
        with patch("requests.request") as http:
            with TestCase.assertRaises(self, ProviderFailure):
                provider._request("GET", "/models")
            http.assert_not_called()

    def test_temporary_retry_timeout_and_malformed(self):
        provider = self.provider()
        with patch("requests.request", side_effect=[requests.Timeout(), self.response(payload={"data": []})]) as http:
            self.assertEqual(provider._request("GET", "/models"), {"data": []})
        self.assertEqual(http.call_count, 2)
        self.assertEqual(provider.used_today, 2)
        response = self.response()
        response.content = b"{broken"
        with patch("requests.request", return_value=response) as http:
            with TestCase.assertRaises(self, ProviderFailure) as caught:
                provider._request("GET", "/models")
        self.assertEqual(caught.exception.code, "malformed_response")
        self.assertEqual(http.call_count, 1)

    def test_permanent_authentication_failure_no_retry(self):
        provider = self.provider()
        with patch("requests.request", return_value=self.response(401)) as http:
            with TestCase.assertRaises(self, ProviderFailure):
                provider._request("GET", "/models")
        self.assertEqual(http.call_count, 1)
        self.assertEqual(provider.health, "auth")

    def test_quota_periods_and_token_reservation(self):
        provider = self.provider(monthly_limit=1)
        provider._reserve(20)
        with TestCase.assertRaises(self, ProviderFailure):
            provider._reserve(20)
        provider.action_reset_usage()
        provider.write({"daily_token_limit": 10})
        with TestCase.assertRaises(self, ProviderFailure):
            provider._reserve(11)
        self.assertEqual(provider.used_today, 0)

    def test_shared_quota(self):
        root = self.provider(daily_limit=1)
        child = self.provider(quota_group_id=root.id)
        child._reserve()
        with TestCase.assertRaises(self, ProviderFailure):
            root._reserve()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            root.quota_group_id = child

    def test_exact_fuzzy_and_conflicting_matching(self):
        row = adapter("egypt_a").normalize({"source_id": "123", "name": "Example", "manufacturer": "Lab", "strength": "500 mg", "dosage_form": "tablet", "barcode": "4006381333931"})
        self.assertEqual(gtin("4006381333931"), "04006381333931")
        self.assertFalse(gtin("4006381333932"))
        self.assertEqual(match({"gtin": "4006381333931"}, row)["match_score"], 1)
        self.assertEqual(match({"name": "Example", "manufacturer": "Lab"}, row)["matched_by"], "name_manufacturer")
        self.assertEqual(match({"name": "Example"}, row)["matched_by"], "fuzzy")
        self.assertEqual(match({"gtin": "4006381333931", "strength": "250 mg"}, row)["match_score"], 0)

    def test_bulk_import_local_index_and_duplicate_prevention(self):
        provider = self.provider("egypt_a", allow_remote=False)
        data = b'commercial_name_en,manufacturer,scientific_name\nExample,Lab,Ingredient\n'
        dataset = self.env["ab_seo_dataset"].create({"provider_id": provider.id, "filename": "sample.csv", "source_version": "test1", "upload": base64.b64encode(data)})
        with tempfile.TemporaryDirectory() as directory, patch.object(type(dataset), "_directory", return_value=Path(directory)), patch("requests.request") as http:
            dataset.action_queue_import()
            dataset._step()
            self.assertEqual(dataset.state, "normalize")
            dataset._step()
            dataset._step()
            self.assertEqual(dataset.state, "done")
            found = provider._lookup({"name": "Example", "manufacturer": "Lab"})
            self.assertEqual(found[0]["facts"]["active_ingredients"], "Ingredient")
            dataset.action_rebuild_index()
            dataset._step()
            self.assertEqual(self.env["ab_seo_source_record"].search_count([("provider_id", "=", provider.id)]), 1)
            self.assertEqual(self.env["ab_seo_source_identifier"].search_count([("provider_id", "=", provider.id)]), 1)
            http.assert_not_called()

    def test_local_first_api_fallback_and_negative_cache(self):
        provider = self.provider("upcitemdb")
        with patch("requests.request", return_value=self.response(payload={"items": []})) as http:
            for _index in range(2):
                with TestCase.assertRaises(self, ProviderFailure):
                    provider._lookup({"gtin": "4006381333931"})
        self.assertEqual(http.call_count, 1)

    def test_model_deprecation_and_openrouter_model_fallback(self):
        provider = self.provider("openrouter", api_key="mock-token", model_name="old", model_names="old\nnew", model_metadata={"ids": ["new"]})
        with patch("requests.request", return_value=self.response(payload=self.completion())) as http:
            result = provider._generate_grounded("Example", "en_US", {"name": "Example"}, [], "test")
        self.assertEqual(result["model"], "new")
        self.assertEqual(http.call_args.kwargs["json"]["model"], "new")
        provider.write({"model_names": "old"})
        with TestCase.assertRaises(self, ProviderFailure):
            provider._generate_grounded("Example", "en_US", {}, [], "test")

    def test_local_generation_and_generation_cache(self):
        provider = self.provider()
        with patch("requests.request", return_value=self.response(payload=self.completion())) as http:
            result = provider._generate_grounded("Example", "ar_001", {"name": "Example"}, [], "seo_v2")
            again = provider._generate_grounded("Example", "ar_001", {"name": "Example"}, [], "seo_v2")
        self.assertEqual(http.call_count, 1)
        self.assertTrue(again["cache_hit"])
        self.assertTrue(result["review_required"])
        self.assertNotIn("Authorization", http.call_args.kwargs["headers"])

    def test_hallucinations_and_safety_isolation(self):
        with TestCase.assertRaises(self, ProviderFailure):
            validate_draft({"meta_title": "Example", "meta_description": "Example", "active_ingredients": "invented"}, {"name": "Example"})
        content = validate_draft({"meta_title": "Example", "meta_description": "Safe during pregnancy; cures disease."}, {"name": "Example"})
        self.assertTrue(content["unverified_proposal"])
        self.assertNotIn("active_ingredients", content)
        provider = self.provider("openfda_cosmetic_event")
        with self.assertRaises(UserError):
            provider.generate_product_content("Example", "en_US")
        result = provider._normalize_cosmetic_event_items("Example", [{"reactions": ["rash"]}])
        self.assertNotIn("meta_description", result)
        self.assertNotIn("public_description", result)

    def test_license_restrictions_and_manual_sources(self):
        provider = self.provider("egypt_b")
        self.assertFalse(provider._allowed_for_commercial())
        provider.commercial_permission = True
        self.assertTrue(provider._allowed_for_commercial())
        for key in ("eda_eddb", "gs1", "cosing", "cir"):
            with TestCase.assertRaises(self, ProviderFailure) as error:
                adapter(key).lookup({"name": "Example"}, Mock())
            self.assertEqual(error.exception.code, "manual_verification_required")

    def test_provider_response_protocols(self):
        data = "{\"meta_title\":\"Example\"}"
        cases = {"cohere": {"message": {"content": [{"text": data}]}, "usage": {"tokens": {"input_tokens": 2, "output_tokens": 3}}},
                 "cloudflare": {"result": {"response": data}}, "google_gemini": {"candidates": [{"content": {"parts": [{"text": data}]}}]}}
        for key, response in cases.items():
            self.assertEqual(ai_response(key, response)[0], data)
        with TestCase.assertRaises(self, ProviderFailure):
            ai_response("groq", {"choices": []})

    def test_provider_normalizers(self):
        samples = {
            "egypt_a": {"commercial_name_en": "Example", "scientific_name": "Ingredient"},
            "egypt_b": {"id": 1, "name": "Example", "active": "Ingredient", "uses": "Generated claim"},
            "fda_ndc": {"product_id": "ndc1", "product_ndc": "1-2", "brand_name": "Example", "active_ingredients": [{"name": "A", "strength": "2mg"}]},
            "openfda": {"id": "label1", "openfda": {"brand_name": ["Example"], "product_ndc": ["1-2"]}},
            "dsld": {"id": 1, "fullName": "Example", "brandName": "Lab", "upcSku": "4006381333931"},
            "usda_fdc": {"fdcId": 1, "description": "Example", "foodNutrients": [{"name": "A"}]},
            "openbeautyfacts": {"code": "4006381333931", "product_name": "Example", "ingredients_text": "A"},
            "openfoodfacts": {"code": "4006381333931", "product_name": "Example", "nutriments": {"energy": 1}},
            "openproductsfacts": {"code": "4006381333931", "product_name": "Example"},
            "pubchem": {"CID": 1, "IUPACName": "Example", "InChI": "Example"},
            "chembl": {"molecule_chembl_id": "CHEMBL1", "pref_name": "Example"},
            "drugcentral": {"ID": 1, "INN": "Example", "CAS_RN": "1-2-3"},
            "cosing": {"source_id": "1", "inci": "Example", "cas": "1-2-3", "functions": ["emollient"]},
            "cir": {"source_id": "1", "name": "Example", "references": ["official report"]},
            "gs1": {"source_id": "1", "name": "Example", "gtin": "4006381333931"},
            "upcitemdb": {"ean": "4006381333931", "title": "Example"},
            "rxnorm": {"source_id": "1", "rxcui": "1", "name": "Example"},
            "ready_api": {"name": "Example"},
            "eda_eddb": {"source_id": "1", "name": "Example", "registration": "EDA1"},
        }
        for key, data in samples.items():
            with self.subTest(provider=key):
                self.assertEqual(adapter(key).normalize(data)["facts"]["name"], "Example")

    def test_streaming_json_and_rxnorm(self):
        data = io.BytesIO(json.dumps({"results": [{"id": 1}, {"id": 2}]}).encode())
        self.assertEqual(len(list(records(data, "label.json", "openfda"))), 2)
        row = "123|ENG|P|L|PF|S|Y|AUI|||CODE|RXNORM|SCD|CODE|Example|0|N||\n"
        result = list(records(io.BytesIO(row.encode()), "RXNCONSO.RRF", "rxnorm"))
        self.assertEqual(result[0]["rxcui"], "123")

    def test_dailymed_spl_parser(self):
        xml = b'<document xmlns="urn:hl7-org:v3"><setId root="set1"/><versionNumber value="2"/><component><manufacturedProduct><manufacturedProduct><code code="123-456"/><name>Example</name><formCode displayName="Tablet"/></manufacturedProduct></manufacturedProduct></component></document>'
        result = list(spl_records(io.BytesIO(xml)))
        self.assertEqual(result[0]["ndc"], "123-456")
        self.assertEqual(result[0]["scientific_context"]["version"], "2")
        provider = self.provider("dailymed")
        response = self.response()
        response.content = xml
        with patch("requests.request", return_value=response) as http:
            result = provider._lookup({"source_ids": {"dailymed": "set1"}})
        self.assertTrue(http.call_args.args[1].endswith("/spls/set1.xml"))
        self.assertEqual(result[0]["facts"]["name"], "Example")

    def test_background_enqueue_has_no_network_or_eager_work(self):
        job = self.env["ab.product.seo.bulk.optimization"].create({"name": "Bounded discovery", "batch_limit": 100})
        with patch("requests.request") as http:
            job.action_fill_with_ai_for_published_products()
            self.assertEqual(job.state, "queued")
            self.assertFalse(job.work_item_ids)
            http.assert_not_called()
        job._discover_chunk(limit=1)
        cursor = job.discovery_cursor
        job._discover_chunk(limit=1)
        self.assertGreaterEqual(job.discovery_cursor, cursor)
        self.assertEqual(len(job.work_item_ids.product_id), len(job.work_item_ids))

    def test_review_gate_and_audit_immutability(self):
        job = self.job(self.pipeline([], ai_mode="off"))
        job._run_bulk_optimization_chunk()
        item = job.work_item_ids
        item.seo_id.action_submit_review()
        with self.assertRaises(ValidationError):
            item.seo_id.action_approve()
        translation = item.seo_id.translation_ids.filtered("enrichment_item_id")
        translation.review_notes = "Verified product identity; conservative text only."
        translation.action_review_evidence()
        item.seo_id.action_approve()
        self.assertTrue(translation.current_version_id.enrichment_provenance)
        with self.assertRaises(UserError):
            item.fact_ids[:1].write({"accepted": True})
        item.seo_id.action_publish()
        self.assertTrue(self.template.website_meta_title)

    def test_user_cannot_configure_or_reset_providers(self):
        group = self.env.ref("ab_website_seo_optimization.group_ab_website_seo_optimization_user")
        user = self.env["res.users"].create({"name": "Enrichment read only", "login": "enrichment_readonly_test", "group_ids": [(6, 0, [group.id])]})
        provider = self.provider()
        with self.assertRaises(AccessError):
            provider.with_user(user).action_reset_usage()
        with self.assertRaises(AccessError):
            provider.with_user(user).read(["api_key"])

    def test_company_scope_covers_job_and_provenance(self):
        other = self.env["res.company"].create({"name": "Enrichment other company"})
        group = self.env.ref("ab_website_seo_optimization.group_ab_website_seo_optimization_user")
        user = self.env["res.users"].create({"name": "Company reader", "login": "enrichment_company_reader", "company_id": self.env.company.id,
                                            "company_ids": [(6, 0, self.env.company.ids)], "group_ids": [(6, 0, group.ids)]})
        job = self.job(self.pipeline([], ai_mode="off"))
        job.state = "draft"
        job.company_id = other
        item = job.work_item_ids
        evidence = item._evidence("name", "Example", accepted=True)
        for record in (job, item, evidence):
            with self.assertRaises(AccessError):
                record.with_user(user).with_context(allowed_company_ids=self.env.company.ids).read(["id"])

    def test_generation_cache_reuses_equivalent_sources_across_jobs(self):
        provider = self.provider()
        first_job = self.job(self.pipeline([provider]))
        second_job = self.job(first_job.pipeline_id)
        facts = {"name": "Example", "manufacturer": "Lab"}
        first_source = first_job.work_item_ids._evidence("manufacturer", "Lab", accepted=True)
        second_source = second_job.work_item_ids._evidence("manufacturer", "Lab", accepted=True)
        with patch("requests.request", return_value=self.response(payload=self.completion())) as http:
            first_result = provider._generate_grounded("Example", "en_US", facts, first_source.ids, "seo_v2")
            second_result = provider._generate_grounded("Example", "en_US", facts, second_source.ids, "seo_v2")
        self.assertEqual(http.call_count, 1)
        self.assertTrue(second_result["cache_hit"])
        self.assertEqual(second_result["input_sources"], second_source.ids)
        self.assertEqual(first_result["normalized_input_hash"], second_result["normalized_input_hash"])

    def test_programmer_failure_stops_job(self):
        job = self.job(self.pipeline([], ai_mode="off"))
        with patch.object(type(self.env["ab_seo_work_item"]), "_process", side_effect=RuntimeError("programmer bug")):
            with self.assertRaises(RuntimeError):
                job._run_bulk_optimization_chunk()

    def test_completed_download_recovers_after_uncommitted_checkpoint(self):
        provider = self.provider("egypt_a")
        dataset = self.env["ab_seo_dataset"].create({"provider_id": provider.id, "source_version": "fixture", "filename": "fixture.csv", "url": "https://example.test/data.csv", "state": "download"})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            content = b"name,manufacturer\nExample,Lab\n"
            (root / "raw").write_bytes(content)
            with patch.object(type(dataset), "_directory", return_value=root), patch("requests.get", return_value=self.response(416, headers={"Content-Range": "bytes */%s" % len(content)})):
                dataset._download_chunk()
            self.assertEqual(dataset.state, "normalize")
            self.assertTrue(dataset.checksum)
