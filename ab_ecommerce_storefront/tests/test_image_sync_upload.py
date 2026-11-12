import io
import os
import zipfile
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestStorefrontImageSyncUpload(TransactionCase):
    def setUp(self):
        super().setUp()
        self.admin = self.env.ref("base.user_admin")
        self.Wizard = self.env["ab.website.sale.add.many.by.codes.wizard"].with_user(self.admin)

    def _wizard(self, mode):
        wizard = self.Wizard.create({"source_mode": mode})
        self.addCleanup(wizard.unlink)
        return wizard

    def test_folder_upload_keeps_relative_paths_and_rejects_traversal(self):
        wizard = self._wizard("folder")
        wizard._start_image_upload("folder", "Product Photos")
        with self.assertRaises(UserError):
            wizard._save_image_file(io.BytesIO(b"image"), "../outside.jpg", 5)
        wizard._save_image_file(io.BytesIO(b"image"), "Product Photos/123/main.jpg", 5)
        wizard._finish_image_upload()
        self.assertEqual(wizard.upload_file_count, 1)
        self.assertTrue(os.path.isfile(os.path.join(wizard._get_directory_path(), "Product Photos", "123", "main.jpg")))

    def test_zip_upload_and_direct_access_check(self):
        wizard = self._wizard("zip")
        wizard._start_image_upload("zip", "photos.zip")
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("123/main.jpg", b"image")
            archive.writestr("readme.txt", b"ignored")
        data.seek(0)
        wizard._extract_image_archive(data)
        wizard._finish_image_upload()
        self.assertEqual(wizard.upload_file_count, 1)
        self.assertTrue(os.path.isfile(os.path.join(wizard._get_directory_path(), "123", "main.jpg")))
        public_user = self.env.ref("base.public_user")
        with self.assertRaises(AccessError):
            wizard.with_user(public_user)._validated_upload_directory()

    def test_zip_rejects_duplicate_image_paths(self):
        wizard = self._wizard("zip")
        wizard._start_image_upload("zip", "duplicate.zip")
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("123/main.jpg", b"first")
            archive.writestr("123/main.jpg", b"second")
        data.seek(0)
        with self.assertRaises(UserError):
            wizard._extract_image_archive(data)
        self.assertEqual(wizard.upload_file_count, 0)

    def test_upload_sync_uses_refresh_and_publication_plan(self):
        wizard = self._wizard("folder")
        wizard._start_image_upload("folder", "Photos")
        wizard._save_image_file(io.BytesIO(b"image"), "123.png", 5)
        wizard._finish_image_upload()
        Service = type(self.env["ab.website.product.image.sync.service"])
        plan = {"summary": {}, "report": []}
        with patch.object(Service, "prepare_publication_sync_plan", return_value=plan) as prepare, \
             patch.object(Service, "apply_sync_plan", return_value=plan) as apply, \
             patch.object(type(wizard), "_write_image_sync_report", return_value=True):
            self.assertTrue(wizard.action_sync_images())
        prepare.assert_called_once_with(wizard._get_directory_path())
        apply.assert_called_once_with(plan, publish_requested=True)

    def test_preview_does_not_refresh_eplus(self):
        wizard = self._wizard("folder")
        wizard._start_image_upload("folder", "Photos")
        wizard._save_image_file(io.BytesIO(b"image"), "123.png", 5)
        wizard._finish_image_upload()
        Service = type(self.env["ab.website.product.image.sync.service"])
        with patch.object(Service, "prepare_sync_plan", return_value={}), \
             patch.object(Service, "prepare_publication_sync_plan") as refresh, \
             patch.object(type(wizard), "_write_image_sync_report", return_value=True):
            self.assertTrue(wizard.action_preview_images())
        refresh.assert_not_called()
