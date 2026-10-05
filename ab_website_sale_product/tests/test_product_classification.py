from unittest.mock import patch
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged, new_test_user
from odoo.addons.integration_queue_job.job import Job

from ..services.classification import classify_local, taxonomy_key
from ..services.historical import build_index, historical_index
from ..services.web_research import WebResearchProvider


@tagged("post_install", "-at_install")
class TestProductClassification(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("ir_attachment.location", "db")
        cls.Run = cls.env["ab_product_classification_run"]
        cls.Result = cls.env["ab_product_classification_result"]
        cls.Taxonomy = cls.env["ab_product_classification_taxonomy"]
        cls.Taxonomy.action_prepare()
        cls.nodes = cls.Taxonomy._category_map()
        cls.website = cls.env["website"].search([], limit=1)
        cls.user = new_test_user(cls.env, login="classification_denied", groups="base.group_user")

    def product(self, name="LEVCET ORAL DROPS 20ML", code="CLS-LEVCET"):
        return self.env["ab_product"].create({"name": name, "product_card_name": name, "code": code, "website_sale_available": True})

    def make_run(self, products):
        run = self.Run._internal().create({"name": "Classification test", "state": "running", "scope": "all", "requested_by": self.env.uid, "company_id": self.env.company.id, "website_id": self.website.id, "total_products": len(products), "snapshot_done": True})
        self.Result._internal().create([{"run_id": run.id, "ab_product_id": p.id, "product_id": p.website_product_tmpl_id.id, "product_key": f"ab:{p.id}", "product_code": p.code, "product_name": p.name or p.product_card_name} for p in products])
        return run

    def process(self, run):
        run._internal()._process_batch()
        return run.result_ids

    def node(self, root, child=None):
        return self.nodes[taxonomy_key((root, child) if child else (root,))]

    def test_local_known_patterns(self):
        samples = {
            "LEVCET ORAL DROPS 20ML": ("Medicines", "Allergy"),
            "MYSTERY ORAL DROPS 20ML": ("Medicines",),
            "LOREAL ELVIVE DREAM LONG RESCUE MASK 300ML": ("Hair Care", "Hair Masks"),
            "ELVIVE SHAMPOO 400ML": ("Hair Care", "Shampoo"),
            "HAIR SERUM 50ML": ("Hair Care", "Hair Oils & Serums"),
            "BIODERMA PHOTODERM SPF 50": ("Skin Care & Beauty", "Sun Care"),
            "FACIAL CLEANSER 200ML": ("Skin Care & Beauty", "Face Cleansing"),
            "HYDROCORTISONE CREAM 1%": ("Medicines", "Dermatology"),
            "BABY SHAMPOO 200ML": ("Mother & Baby", "Baby Skin & Hair"),
            "TOOTHPASTE 100ML": ("Personal Care", "Oral Care"),
        }
        for name, path in samples.items():
            with self.subTest(name=name):
                self.assertEqual(classify_local({"name": name})["path"], path)

    def test_unknown_and_generic_cream_need_review(self):
        for name in ("UNKNOWN 123", "CREAM 50G", "ORAL", "HAIR", "EARTH CREAM", "CORAL DECORATION"):
            outcome = classify_local({"name": name})
            self.assertEqual(outcome["method"], "needs_review")
            self.assertFalse(outcome["path"])

    def test_historical_code_join(self):
        products = [{"template_id": "10", "template_default_code": " 001234 "}]
        categories = [{"id": "15", "name": "MEDICINES", "parent_id": ""}, {"id": "77", "name": "Allergy", "parent_id": "15"}]
        relations = [{"product_template_id": "10", "product_public_category_id": "77"}]
        result = build_index(products, categories, relations)["001234"]
        self.assertEqual(result["path"], ("Medicines", "Allergy"))
        self.assertEqual(result["historical"][0]["path"], ["MEDICINES", "Allergy"])

    def test_historical_conflicts_and_duplicate_codes(self):
        products = [{"template_id": "10", "template_default_code": "C"}]
        categories = [{"id": "77", "name": "Allergy", "parent_id": ""}, {"id": "855", "name": "Hair Dye", "parent_id": ""}]
        relations = [{"product_template_id": "10", "product_public_category_id": i} for i in ("77", "855")]
        self.assertTrue(build_index(products, categories, relations)["c"]["blocked"])
        products.append({"template_id": "11", "template_default_code": "C"})
        self.assertTrue(build_index(products, categories, relations[:1])["c"]["blocked"])

    def test_historical_promotion_is_not_taxonomy(self):
        index = build_index([{"template_id": "10", "template_default_code": "C"}], [{"id": "1222", "name": "Home Promo", "parent_id": ""}, {"id": "77", "name": "Allergy", "parent_id": "1222"}], [{"product_template_id": "10", "product_public_category_id": "77"}])
        self.assertFalse(index["c"]["path"])

    def test_bundled_reference_is_cached_and_real(self):
        index = historical_index()
        self.assertIs(index, historical_index())
        self.assertGreater(len(index), 20000)
        self.assertTrue(any(row["path"] for row in index.values()))

    def test_manual_wins_and_sync_preserves_it(self):
        product = self.product()
        template = product._sync_website_products()
        row = self.process(self.make_run(product))
        chosen = self.node("Hair Care", "Shampoo")
        row.proposed_node_id = chosen
        row.action_accept()
        product.write({"name": "HYDROCORTISONE CREAM", "product_card_name": "HYDROCORTISONE CREAM"})
        new = self.process(self.make_run(product))
        self.assertEqual(new.method, "manual")
        self.assertEqual(new.node_id, chosen)
        product._sync_website_products()
        self.assertEqual(template.public_categ_ids, chosen.category_id)
        self.assertEqual(len(row.review_ids), 1)
        self.assertEqual(row.evidence["outcome"]["method"], "local_rule")

    def test_automatic_assignment_sync_and_reuse(self):
        product = self.product()
        product._sync_website_products()
        first = self.process(self.make_run(product))
        second = self.process(self.make_run(product))
        self.assertEqual(second.reused_result_id, first)
        product.write({"name": "ELVIVE SHAMPOO", "product_card_name": "ELVIVE SHAMPOO"})
        product._sync_website_products()
        self.assertEqual(product.website_product_tmpl_id.public_categ_ids, first.node_id.category_id)
        third = self.process(self.make_run(product))
        self.assertEqual(third.node_id, self.node("Hair Care", "Shampoo"))

    def test_unknown_sync_does_not_clear_existing_category(self):
        product = self.product("UNKNOWN", "CLS-UNKNOWN")
        template = product._sync_website_products()
        template.public_categ_ids = self.node("Medicines").category_id
        product._sync_website_products()
        self.assertEqual(template.public_categ_ids, self.node("Medicines").category_id)

    def test_web_only_unresolved_and_persisted(self):
        known = self.product()
        unknown = self.product("MYSTERY PRODUCT", "CLS-UNKNOWN")
        payload = {"provider": "fixture", "query": '"MYSTERY PRODUCT"', "sources": [{"url": "https://example.test/product", "title": "MYSTERY PRODUCT SHAMPOO", "evidence": "Hair shampoo"}], "error": ""}
        with patch.object(WebResearchProvider, "research", return_value=payload) as research:
            results = self.process(self.make_run(known | unknown))
        self.assertEqual(research.call_count, 1)
        row = results.filtered(lambda r: r.ab_product_id == unknown)
        self.assertEqual(row.method, "web_research")
        self.assertEqual(row.source_url, payload["sources"][0]["url"])
        self.assertTrue(row.researched_at)
        self.assertEqual(row.node_id, self.node("Hair Care", "Shampoo"))

    def test_web_configuration_missing_and_cache(self):
        product = self.product("UNKNOWN", "CLS-UNKNOWN")
        with patch.object(WebResearchProvider, "research", wraps=WebResearchProvider().research) as research:
            first = self.process(self.make_run(product))
            second = self.process(self.make_run(product))
        self.assertEqual(first.status, "needs_review")
        self.assertEqual(second.status, "needs_review")
        self.assertEqual(research.call_count, 1)
        self.assertIn("not configured", first.error_message)

    def test_historical_conflict_does_not_search_web(self):
        product = self.product()
        row = self.make_run(product).result_ids
        with patch.object(WebResearchProvider, "research") as research:
            row._internal()._classify(self.nodes, {product.code.casefold(): {"path": (), "blocked": True, "method": "needs_review", "reason": "Conflicting historical categories"}}, None)
        research.assert_not_called()
        self.assertEqual(row.status, "needs_review")

    def test_failed_product_does_not_abort_batch(self):
        first = self.product()
        second = self.product("ELVIVE SHAMPOO", "CLS-SHAMPOO")
        run = self.make_run(first | second)
        original = type(self.Result)._classify
        def classify(record, *args):
            if record.ab_product_id == first:
                raise ValueError("Isolated test failure")
            return original(record, *args)
        with patch.object(type(self.Result), "_classify", classify):
            self.process(run)
        self.assertEqual(run.failed_count, 1)
        self.assertEqual(run.classified_products, 1)
        self.assertEqual(run.processed_products, 2)
        self.assertEqual(run.state, "completed")

    def test_resume_checkpoint_counts_and_unique_primary(self):
        products = self.product() | self.product("ELVIVE SHAMPOO", "CLS-SHAMPOO")
        run = self.make_run(products)
        run.batch_size = 1
        self.process(run)
        first = run.result_ids.filtered(lambda r: r.status == "classified")
        processed_at = first.processed_at
        self.assertEqual(run.progress_percent, 50)
        self.process(self.Run.browse(run.id))
        self.assertEqual(first.processed_at, processed_at)
        status = run.get_status()
        self.assertEqual(status["percent"], 100)
        self.assertEqual(sum(r["classified"] for r in status["category_counts"]), 2)
        self.assertEqual(len(run.result_ids), 2)

    def test_pause_stop_resume(self):
        run = self.make_run(self.product())
        run.action_pause()
        run._process_checkpoint()
        self.assertEqual(run.processed_products, 0)
        self.assertEqual(run.state, "paused")
        run.action_stop()
        self.assertEqual(run.state, "stopped")
        with patch.object(type(self.Run), "_enqueue"):
            run.action_resume()
        self.assertEqual(run.state, "queued")
        self.process(run)
        self.assertEqual(run.state, "completed")

    def test_ignore_and_reset_are_permanent_and_audited(self):
        product = self.product()
        row = self.process(self.make_run(product))
        row.action_ignore()
        second = self.process(self.make_run(product))
        self.assertTrue(second.ignored)
        self.assertEqual(second.method, "manual")
        second.action_reset_manual()
        third = self.process(self.make_run(product))
        self.assertEqual(third.method, "local_rule")
        self.assertFalse(third.ignored)
        self.assertEqual(row.review_ids.decision, "ignore")

    def test_unauthorized_and_audit_tampering(self):
        run = self.make_run(self.product())
        for call in (lambda: self.Run.with_user(self.user).dashboard(), lambda: run.with_user(self.user).action_stop(), lambda: run.with_user(self.user).read(["state"]), lambda: run.with_context(classification_internal=True).write({"state": "completed"}), lambda: run.unlink()):
            with self.assertRaises(AccessError):
                call()

    def test_start_only_enqueues_and_snapshot_is_background(self):
        self.env["product.template"].create({"name": "New classification candidate"})
        with patch.object(type(self.Run), "_enqueue") as enqueue:
            run_id = self.Run.start_classification(website_id=self.website.id)
        run = self.Run.browse(run_id)
        enqueue.assert_called_once()
        self.assertEqual(run.state, "queued")
        self.assertFalse(run.result_ids)
        self.assertFalse(run.snapshot_done)

    def test_unlinked_website_template(self):
        template = self.env["product.template"].create({"name": "FACIAL CLEANSER", "default_code": "CLS-UNLINKED"})
        run = self.make_run(self.env["ab_product"])
        row = self.Result._internal().create({"run_id": run.id, "product_id": template.id, "product_key": f"template:{template.id}", "product_name": template.name})
        self.process(run)
        self.assertEqual(row.status, "classified")
        self.assertEqual(template.public_categ_ids, self.node("Skin Care & Beauty", "Face Cleansing").category_id)

    def test_categories_page_inherits_original_crud(self):
        action = self.env.ref("website_sale.product_public_category_action")
        self.assertEqual(action.res_model, "product.public.category")
        view = self.env.ref("ab_website_sale_product.category_classification_button")
        self.assertEqual(view.inherit_id, self.env.ref("website_sale.product_public_category_tree_view"))
        self.assertIn("Classify Products", view.arch_db)
        self.assertEqual(self.env.ref("ab_website_sale_product.action_product_classification").path, "ecommerce-product-classification")

    def test_taxonomy_is_closed_and_setup_idempotent(self):
        categories = self.env["product.public.category"].search_count([])
        self.Taxonomy.action_prepare()
        self.assertEqual(self.env["product.public.category"].search_count([]), categories)
        with self.assertRaises(AccessError):
            self.Taxonomy.create({"name": "Invented", "key": "invented"})
        with self.assertRaises(AccessError):
            self.node("Medicines").write({"name": "Invented"})

    def test_real_queue_checkpoint_and_recovery(self):
        self.product()
        run = self.Run.browse(self.Run.with_user(self.env.ref("base.user_admin")).start_classification(scope="all", website_id=self.website.id))
        job = Job.load(self.env, run.queue_uuid)
        self.assertEqual(job.channel, "root.classification")
        job.set_started()
        job.store()
        job.perform()
        job.set_done()
        job.store()
        self.assertTrue(run.snapshot_done)
        self.assertEqual(len(run.result_ids), 1)
        next_job = Job.load(self.env, run.queue_uuid)
        self.assertNotEqual(next_job.uuid, job.uuid)
        next_job.set_started()
        next_job.date_started = fields.Datetime.now() - timedelta(minutes=15)
        next_job.store()
        self.Run._recover_interrupted()
        recovered = Job.load(self.env, run.queue_uuid)
        self.assertEqual(recovered.state, "pending")
        recovered.perform()
        self.assertEqual(run.state, "completed")
        self.assertEqual(run.processed_products, 1)
        recovered.perform()
        self.assertEqual(len(run.result_ids), 1)

    def test_research_provider_failure_is_reviewable(self):
        product = self.product("UNKNOWN", "CLS-UNKNOWN")
        with patch.object(WebResearchProvider, "research", side_effect=TimeoutError):
            row = self.process(self.make_run(product))
        self.assertEqual(row.status, "needs_review")
        self.assertIn("TimeoutError", row.error_message)

    def test_real_historical_mapping_precedes_local(self):
        index = historical_index()
        code, old = next((code, old) for code, old in index.items() if old.get("path"))
        product = self.product("UNKNOWN", code)
        row = self.process(self.make_run(product))
        self.assertEqual(row.method, "historical_mapping")
        self.assertEqual(row.node_id.key, taxonomy_key(old["path"]))
        self.assertTrue(row.historical_evidence)

    def test_invalid_direct_result_write_is_denied(self):
        row = self.process(self.make_run(self.product()))
        with self.assertRaises(AccessError):
            row.with_context(classification_internal=False).write({"status": "classified", "node_id": False})
        with self.assertRaises(AccessError):
            row.with_user(self.user).action_accept()

    def test_company_rule_blocks_other_company_run(self):
        other = self.env["res.company"].create({"name": "Classification other company"})
        admin = new_test_user(self.env, login="classification_admin", groups="base.group_system", company_id=self.env.company.id, company_ids=[Command.set(self.env.company.ids)])
        run = self.make_run(self.product())
        run._internal().company_id = other
        with self.assertRaises(AccessError):
            run.with_user(admin).read(["state"])

    def test_duplicate_run_product_is_rejected(self):
        from psycopg2.errors import UniqueViolation
        product = self.product()
        run = self.make_run(product)
        with self.assertRaises(UniqueViolation), self.env.cr.savepoint():
            self.Result._internal().create({"run_id": run.id, "product_key": f"ab:{product.id}"})

    def test_busy_pause_is_queued_and_control_recovers(self):
        run = self.make_run(self.product())
        with patch.object(type(self.Run), "try_lock_for_update", return_value=self.Run.browse()):
            self.assertFalse(run.with_user(self.env.ref("base.user_admin")).action_pause())
        queued = self.env["queue.job"].search([("identity_key", "=", f"classification-control:{run.id}:paused")])
        job = Job.load(self.env, queued.uuid)
        job.set_started()
        job.date_started = fields.Datetime.now() - timedelta(minutes=15)
        job.store()
        with patch.object(type(self.Run), "_enqueue"):
            self.Run._recover_interrupted()
        recovered = Job.load(self.env, queued.uuid)
        self.assertEqual(recovered.state, "pending")
        recovered.perform()
        self.assertEqual(run.state, "paused")

    def test_start_and_resume_do_not_wait_for_catalog_lock(self):
        run = self.make_run(self.product())
        run.action_pause()
        with patch.object(type(self.env["ab_product"]), "_lock_website_sync", return_value=False) as lock:
            with self.assertRaises(UserError):
                self.Run.start_classification(website_id=self.website.id)
            with self.assertRaises(UserError):
                run.action_resume()
        self.assertEqual(lock.call_count, 2)
        self.assertTrue(all(call.kwargs == {"wait": False} for call in lock.call_args_list))
