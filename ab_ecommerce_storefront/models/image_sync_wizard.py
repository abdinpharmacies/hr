import os
import shutil
import tempfile
import zipfile
from pathlib import PurePosixPath

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


MAX_IMAGE_FILES = 10000
MAX_IMAGE_BYTES = 30 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1000 * 1000 * 1000
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


class StorefrontImageSyncWizard(models.TransientModel):
    _inherit = "ab.website.sale.add.many.by.codes.wizard"

    source_mode = fields.Selection(
        [
            ("folder", "Folder on this device"),
            ("zip", "ZIP file on this device"),
        ],
        default="folder",
        required=True,
        string="Image source",
    )
    upload_ready = fields.Boolean(readonly=True)
    upload_source_mode = fields.Char(readonly=True)
    preview_source_mode = fields.Char(readonly=True)
    upload_name = fields.Char(readonly=True)
    upload_file_count = fields.Integer(readonly=True)
    upload_total_bytes = fields.Integer(readonly=True)
    upload_directory = fields.Char(readonly=True)

    def _is_staging_directory(self, directory):
        if not directory:
            return False
        real_directory = os.path.realpath(directory)
        return (
            os.path.dirname(real_directory) == os.path.realpath(tempfile.gettempdir())
            and os.path.basename(real_directory).startswith("ab_storefront_image_sync_")
        )

    def _check_upload_access(self):
        self.ensure_one()
        self._check_image_sync_access()
        if self.create_uid != self.env.user:
            raise AccessError(_("You can only upload images to your own synchronization session."))

    def _validated_upload_directory(self):
        self._check_upload_access()
        if (
            not self.upload_ready
            or not self.upload_directory
            or self.upload_source_mode != self.source_mode
        ):
            raise UserError(_("Choose and upload an image folder or ZIP file first."))
        directory = os.path.realpath(self.upload_directory)
        if not self._is_staging_directory(directory):
            raise UserError(_("The uploaded image folder is unavailable."))
        return self.env["ab.website.product.image.sync.service"].normalize_image_root(directory)

    def _get_directory_path(self):
        self.ensure_one()
        return self._validated_upload_directory()

    def action_preview_images(self):
        self.ensure_one()
        directory = self._validated_upload_directory()
        plan = self.env["ab.website.product.image.sync.service"].prepare_sync_plan(directory)
        return self._write_image_sync_report(plan)

    def _prepare_image_sync_plan(self):
        self.ensure_one()
        directory = self._validated_upload_directory()
        service = self.env["ab.website.product.image.sync.service"]
        return service, service.prepare_sync_plan(directory)

    def _write_image_sync_report(self, plan, confirmation_required=False):
        self.ensure_one()
        original_path = self.directory_path
        action = super()._write_image_sync_report(plan, confirmation_required=confirmation_required)
        self.preview_source_mode = self.source_mode
        self.directory_path = original_path
        return action

    def _start_image_upload(self, source_mode, upload_name):
        self._check_upload_access()
        if source_mode not in ("folder", "zip") or source_mode != self.source_mode:
            raise UserError(_("Select the matching image source before uploading."))
        if self._is_staging_directory(self.upload_directory):
            shutil.rmtree(self.upload_directory, ignore_errors=True)
        directory = tempfile.mkdtemp(prefix="ab_storefront_image_sync_")
        self.image_sync_line_ids.unlink()
        self.write({
            "upload_directory": directory,
            "upload_ready": False,
            "upload_source_mode": source_mode,
            "preview_source_mode": False,
            "upload_name": (upload_name or "")[:255],
            "upload_file_count": 0,
            "upload_total_bytes": 0,
            "image_sync_summary": False,
            "image_sync_confirmation_required": False,
        })

    def _image_upload_path(self, relative_path):
        if not relative_path or len(relative_path) > 1024:
            raise UserError(_("An uploaded image has an invalid path."))
        parts = PurePosixPath(relative_path.replace("\\", "/")).parts
        if (
            not parts
            or any(part in ("", ".", "..") for part in parts)
            or relative_path.startswith(("/", "\\"))
        ):
            raise UserError(_("An uploaded image has an invalid path."))
        if any(":" in part for part in parts):
            raise UserError(_("An uploaded image has an invalid path."))
        path = os.path.realpath(os.path.join(self.upload_directory, *parts))
        root = os.path.realpath(self.upload_directory)
        if os.path.commonpath((root, path)) != root:
            raise UserError(_("An uploaded image has an invalid path."))
        return path

    def _save_image_file(self, stream, relative_path, declared_size):
        self._check_upload_access()
        if self.upload_ready or not self.upload_directory or self.source_mode != "folder":
            raise UserError(_("Start a folder upload before adding images."))
        if os.path.splitext(relative_path)[1].lower() not in IMAGE_EXTENSIONS:
            return
        if (
            self.upload_file_count >= MAX_IMAGE_FILES
            or self.upload_total_bytes + declared_size > MAX_TOTAL_BYTES
        ):
            raise UserError(_("This image folder exceeds the upload limit."))
        if declared_size > MAX_IMAGE_BYTES:
            raise UserError(_("An image exceeds the 30 MB file limit."))
        destination = self._image_upload_path(relative_path)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        written = 0
        with open(destination, "wb") as image_file:
            while chunk := stream.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_IMAGE_BYTES or self.upload_total_bytes + written > MAX_TOTAL_BYTES:
                    raise UserError(_("This image folder exceeds the upload limit."))
                image_file.write(chunk)
        self.write({
            "upload_file_count": self.upload_file_count + 1,
            "upload_total_bytes": self.upload_total_bytes + written,
        })

    def _extract_image_archive(self, stream):
        self._check_upload_access()
        if self.upload_ready or not self.upload_directory or self.source_mode != "zip":
            raise UserError(_("Start a ZIP upload before adding images."))
        with zipfile.ZipFile(stream) as archive:
            if len(archive.infolist()) > MAX_IMAGE_FILES * 2:
                raise UserError(_("This ZIP file exceeds the upload limit."))
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            images = [
                entry for entry in entries
                if os.path.splitext(entry.filename)[1].lower() in IMAGE_EXTENSIONS
            ]
            if len({entry.filename for entry in images}) != len(images):
                raise UserError(_("The ZIP contains duplicate image paths."))
            if len(images) > MAX_IMAGE_FILES or sum(entry.file_size for entry in images) > MAX_TOTAL_BYTES:
                raise UserError(_("This ZIP file exceeds the upload limit."))
            for entry in images:
                if (
                    entry.file_size > MAX_IMAGE_BYTES
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000
                ):
                    raise UserError(_("The ZIP contains an unsupported image file."))
                with archive.open(entry) as image_file:
                    self._save_archive_image(image_file, entry.filename, entry.file_size)

    def _save_archive_image(self, stream, relative_path, declared_size):
        destination = self._image_upload_path(relative_path)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        written = 0
        with open(destination, "wb") as image_file:
            while chunk := stream.read(1024 * 1024):
                written += len(chunk)
                if written > declared_size or written > MAX_IMAGE_BYTES:
                    raise UserError(_("The ZIP contains an unsupported image file."))
                image_file.write(chunk)
        self.write({
            "upload_file_count": self.upload_file_count + 1,
            "upload_total_bytes": self.upload_total_bytes + written,
        })

    def _finish_image_upload(self):
        self._check_upload_access()
        if not self.upload_directory or not self.upload_file_count:
            raise UserError(_("No supported image files were selected."))
        self.upload_ready = True

    def unlink(self):
        directories = self.mapped("upload_directory")
        result = super().unlink()
        for directory in directories:
            if self._is_staging_directory(directory):
                shutil.rmtree(directory, ignore_errors=True)
        return result


class StorefrontImageSyncProduct(models.Model):
    _inherit = "ab_product"

    def action_open_sync_images_wizard(self):
        action = super().action_open_sync_images_wizard()
        wizard = self.env["ab.website.sale.add.many.by.codes.wizard"].create({})
        action["res_id"] = wizard.id
        return action
