from unittest.mock import patch

from odoo.addons.integration_queue_job.exception import RetryableJobError
from odoo.addons.integration_queue_job.tests.common import trap_jobs
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.addons.ab_odoo_replication.models.ab_odoo_replication import OdooReplication


@tagged("post_install", "-at_install")
class TestReplicaCatalogImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context={**cls.env.context, "install_mode": False})
        policies = cls.env["ab_odoo_replication_override"].search([
            ("model_name", "in", ["ab_product", "ab_product_card"]), ("active", "=", True),
        ])
        policies.write({"active": False})
        cls.product = cls.env["ab_product"].create({
            "product_card_name": "Replica website sync test", "code": "REPLICA-SYNC-TEST",
            "eplus_serial": 99177100, "website_sale_available": True, "default_price": 42.5,
        })
        policies.write({"active": True})
        cls.snapshot = cls.env["ab_eplus_stock_snapshot"].create({
            "itm_id": cls.product.eplus_serial, "itm_code": cls.product.code,
            "itm_qty": 2, "product_id": cls.product.id, "matched_by": "eplus_serial",
        })
        cls.admin = cls.env.ref("base.user_admin")
        cls.reader = new_test_user(cls.env, login="replica_catalog_reader", groups="base.group_user")

    def test_admin_import_creates_unpublished_template_and_clears_pending(self):
        self.assertTrue(self.product.website_sync_pending)
        self.snapshot.with_user(self.admin)._import_eplus_catalog_batch()
        template = self.product.website_product_tmpl_id
        self.assertTrue(template)
        self.assertFalse(template.is_published)
        self.assertEqual(template.list_price, 42.5)
        self.assertFalse(self.product.website_sync_pending)
        self.snapshot.with_user(self.admin)._import_eplus_catalog_batch()
        self.assertEqual(self.product.website_product_tmpl_id, template)

    def test_admin_cannot_change_master_identifiers_prices_or_create_products(self):
        product = self.product.with_user(self.admin).sudo()
        for values in [
            {"code": "changed"}, {"eplus_serial": 99177101}, {"default_price": 1},
            {"website_sync_pending": False, "code": "changed"},
        ]:
            with self.assertRaises(AccessError):
                product.write(values)
        with self.assertRaises(AccessError):
            product.create({"product_card_name": "Blocked replica product", "code": "BLOCKED"})

    def test_replicated_master_price_updates_linked_website_price(self):
        template = self.product._sync_website_products(create_missing=True)
        policies = self.env["ab_odoo_replication_override"].search([
            ("model_name", "=", "ab_product"), ("active", "=", True),
        ])
        policies.write({"active": False})
        with patch.object(type(self.product), "_sync_linked_website_base_prices", return_value=True):
            self.product.write({"default_price": 73.0})
        policies.write({"active": True})
        self.assertEqual(template.list_price, 42.5)
        self.product._after_force_id_replication("write", {
            self.product.id: {"default_price": 73.0},
        })
        self.assertEqual(template.list_price, 73.0)

    def test_missing_master_product_does_not_block_matched_website_draft(self):
        unmatched = self.env["ab_eplus_stock_snapshot"].create({
            "itm_id": 99177102, "itm_code": "UNMATCHED-REPLICA-TEST", "itm_qty": 1,
        })
        with patch.object(type(unmatched), "_fetch_eplus_catalog_names", return_value={
            unmatched.itm_id: [(unmatched.itm_code, "Real name", "Real name", True)],
        }):
            (unmatched | self.snapshot).with_user(self.admin)._import_eplus_catalog_batch()
        self.assertFalse(unmatched.product_id)
        self.assertTrue(self.product.website_product_tmpl_id)
        self.assertFalse(self.product.website_product_tmpl_id.is_published)
        self.assertFalse(self.product.website_sync_pending)

    def _stale_website_price(self):
        template = self.product._sync_website_products(create_missing=True)
        with patch.object(type(self.product), "_sync_linked_website_base_prices", return_value=True):
            self.product.sudo().with_context(replication=True).write({"default_price": 73.0})
        self.assertEqual(template.list_price, 42.5)
        return template

    def test_replication_without_new_source_rows_repairs_stale_price(self):
        template = self._stale_website_price()
        replication = self.env["ab_odoo_replication"].with_context(lang="en_US")
        with patch.object(OdooReplication, "_replicate_model", return_value=None):
            replication.replicate_model("ab_product", commit=False)
        self.assertEqual(template.list_price, 73.0)
        self.assertTrue(template.message_ids.filtered(
            lambda message: "Website base price changed from" in str(message.body)
        ))
        with patch.object(type(template), "write") as write:
            self.assertEqual(replication._reconcile_website_base_prices(), 0)
            write.assert_not_called()

    def test_price_reconciliation_preserves_caller_transaction(self):
        template = self._stale_website_price()
        with patch.object(type(self.env.cr), "commit") as commit:
            self.env["ab_odoo_replication"]._reconcile_website_base_prices(commit=False)
            commit.assert_not_called()
        self.assertEqual(template.list_price, 73.0)

    def test_scoped_and_unrelated_replication_do_not_reconcile_prices(self):
        template = self._stale_website_price()
        replication = self.env["ab_odoo_replication"]
        with patch.object(OdooReplication, "_replicate_model", return_value=None):
            replication.replicate_model("ab_product_card", commit=False)
            replication.replicate_model("ab_product", commit=False, extra_domain=[("id", "=", self.product.id)])
        self.assertEqual(template.list_price, 42.5)

    def test_failed_source_replication_does_not_reconcile_prices(self):
        template = self._stale_website_price()
        with patch.object(OdooReplication, "_replicate_model", side_effect=RuntimeError("Source unavailable")):
            with self.assertRaises(RuntimeError):
                self.env["ab_odoo_replication"].replicate_model("ab_product", commit=False)
        self.assertEqual(template.list_price, 42.5)

    def test_price_reconciliation_does_not_elevate_reader_access(self):
        template = self._stale_website_price()
        with self.assertRaises(AccessError):
            with self.env.cr.savepoint():
                self.env["ab_odoo_replication"].with_user(self.reader)._reconcile_website_base_prices()
        self.assertEqual(template.list_price, 42.5)

    def test_price_reconciliation_respects_allowed_companies(self):
        template = self._stale_website_price()
        company = self.env["res.company"].create({"name": "Other replica company"})
        template.company_id = company
        replication = self.env["ab_odoo_replication"].with_user(self.admin).sudo(False).with_context(
            allowed_company_ids=[self.env.company.id],
        )
        replication._reconcile_website_base_prices()
        self.assertEqual(template.list_price, 42.5)

    def test_internal_user_cannot_clear_status_or_import(self):
        with self.assertRaises(AccessError):
            self.product.with_user(self.reader).write({"website_sync_pending": False})
        with self.assertRaises(AccessError):
            self.snapshot.with_user(self.reader)._import_eplus_catalog_batch()

    def test_completed_barcode_replication_queues_stock_then_inventory(self):
        replication = self.env["ab_odoo_replication"].with_user(self.admin)
        Snapshot = self.env["ab_eplus_stock_snapshot"].with_user(self.admin)
        Inventory = self.env["ab_eplus_inventory_sync_job"].with_user(self.admin)
        with patch.object(OdooReplication, "_replicate_model", return_value=None), trap_jobs() as trap:
            replication.replicate_model("ab_product_barcode", commit=True)
            trap.assert_jobs_count(3)
            trap.assert_enqueued_job(Snapshot._refresh_after_replication)
            trap.assert_enqueued_job(Snapshot._refresh_branches_after_replication)
            trap.assert_enqueued_job(Inventory._start_after_replication)

    def test_uncommitted_scoped_and_failed_replication_do_not_queue_stock(self):
        replication = self.env["ab_odoo_replication"].with_user(self.admin)
        with patch.object(OdooReplication, "_replicate_model", return_value=None), trap_jobs() as trap:
            replication.replicate_model("ab_product_barcode", commit=False)
            replication.replicate_model(
                "ab_product_barcode", commit=True, extra_domain=[("id", "=", self.product.id)],
            )
            replication.replicate_model("ab_product", commit=False)
            trap.assert_jobs_count(0)
        with patch.object(OdooReplication, "_replicate_model", side_effect=RuntimeError("offline")):
            with patch.object(type(replication), "_queue_eplus_stock_refresh") as enqueue:
                with self.assertRaises(RuntimeError):
                    replication.replicate_model("ab_product_barcode", commit=True)
                enqueue.assert_not_called()

    def test_reader_cannot_run_post_replication_refresh_or_inventory_sync(self):
        with self.assertRaises(AccessError):
            self.env["ab_eplus_stock_snapshot"].with_user(self.reader)._refresh_after_replication()
        with self.assertRaises(AccessError):
            self.env["ab_eplus_stock_snapshot"].with_user(self.reader)._refresh_branches_after_replication()
        with self.assertRaises(AccessError):
            self.env["ab_eplus_inventory_sync_job"].with_user(self.reader)._start_after_replication()

    def test_stock_refresh_rejects_sharp_drop_and_retries_source_failure(self):
        snapshot = self.env["ab_eplus_stock_snapshot"].with_user(self.admin)
        with (
            patch.object(type(snapshot), "search_count", side_effect=[100, 1]),
            patch.object(type(snapshot), "action_refresh_from_eplus"),
        ):
            with self.assertRaises(UserError):
                snapshot._refresh_after_replication()
        with patch.object(type(snapshot), "action_refresh_from_eplus", side_effect=UserError("offline")):
            with self.assertRaises(RetryableJobError):
                snapshot._refresh_after_replication()
