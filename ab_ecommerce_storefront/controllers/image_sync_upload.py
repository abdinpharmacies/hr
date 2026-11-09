import zipfile

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request


class StorefrontImageSyncUpload(http.Controller):
    @http.route("/ab_storefront/image_sync/upload", type="http", auth="user", methods=["POST"])
    def image_sync_upload(self, wizard_id=None, operation=None, **kwargs):
        try:
            wizard = request.env["ab.website.sale.add.many.by.codes.wizard"].browse(
                int(wizard_id or 0)
            ).exists()
            if not wizard:
                raise UserError(request.env._("The image synchronization session is no longer available."))
            wizard._check_upload_access()
            if operation == "start":
                wizard._start_image_upload(kwargs.get("source_mode"), kwargs.get("upload_name", ""))
            elif operation == "folder":
                uploads = request.httprequest.files.getlist("files")
                paths = request.httprequest.form.getlist("paths")
                if len(uploads) != len(paths):
                    raise UserError(request.env._("The selected image files could not be read."))
                for upload, path in zip(uploads, paths):
                    wizard._save_image_file(upload.stream, path, upload.content_length or 0)
            elif operation == "zip":
                upload = request.httprequest.files.get("file")
                if not upload:
                    raise UserError(request.env._("Choose a ZIP file first."))
                if (
                    request.httprequest.content_length
                    and request.httprequest.content_length > 512 * 1024 * 1024
                ):
                    raise UserError(request.env._("The ZIP file exceeds the 512 MB upload limit."))
                wizard._extract_image_archive(upload.stream)
            elif operation == "finish":
                wizard._finish_image_upload()
            else:
                raise UserError(request.env._("Invalid image upload operation."))
            return request.make_json_response({
                "ready": wizard.upload_ready,
                "count": wizard.upload_file_count,
                "name": wizard.upload_name,
            })
        except (UserError, AccessError, ValueError, zipfile.BadZipFile) as error:
            return request.make_json_response({"error": str(error)}, status=400)
        except RuntimeError:
            return request.make_json_response(
                {"error": request.env._("The ZIP file could not be opened.")},
                status=400,
            )
