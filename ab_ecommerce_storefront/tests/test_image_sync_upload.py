import io
import os
import zipfile

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
