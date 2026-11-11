from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


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

    def test_internal_user_cannot_clear_status_or_import(self):
        with self.assertRaises(AccessError):
            self.product.with_user(self.reader).write({"website_sync_pending": False})
        with self.assertRaises(AccessError):
            self.snapshot.with_user(self.reader)._import_eplus_catalog_batch()
