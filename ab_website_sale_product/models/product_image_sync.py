import base64
import hashlib
import logging
import os
from collections import defaultdict

from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from .ab_product import (
    DEFAULT_WEBSITE_IMAGE_DIRECTORY,
    WEBSITE_IMAGE_EXTENSIONS,
    WEBSITE_PLACEHOLDER_IMAGE_PATH,
)

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - Odoo normally depends on Pillow.
    Image = None
    UnidentifiedImageError = OSError


_logger = logging.getLogger(__name__)

MAIN_IMAGE_NAMES = ("main",)
ORDERED_IMAGE_NAMES = tuple("%02d" % number for number in range(1, 100))
IMAGE_CONFIG_PARAMETER = "ab_website_sale_product.image_directory"


class ProductImageSyncService(models.AbstractModel):
    _name = "ab.website.product.image.sync.service"
    _description = "Abdin Website Product Image Sync Service"

    @api.model
    def check_image_sync_access(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can synchronize product images."))

    @api.model
    def get_default_image_root(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param(IMAGE_CONFIG_PARAMETER)
            or DEFAULT_WEBSITE_IMAGE_DIRECTORY
        )

    @api.model
    def normalize_image_root(self, directory_path=None):
        directory_path = (directory_path or self.get_default_image_root() or "").strip()
        if not directory_path:
            raise UserError(_("Enter an images directory."))
        image_root = os.path.realpath(os.path.abspath(os.path.expanduser(directory_path)))
        if not os.path.isdir(image_root):
            raise UserError(_("Directory does not exist: %s") % image_root)
        if not os.access(image_root, os.R_OK):
            raise UserError(_("Directory is not readable by the Odoo server: %s") % image_root)
        return image_root

    @api.model
    def scan_image_root(self, directory_path=None):
        image_root = self.normalize_image_root(directory_path)
        _logger.info("Product image scan started", extra={"image_root": image_root})
        entries = []
        invalid_entries = []
        supported_extensions = {extension.lower() for extension in WEBSITE_IMAGE_EXTENSIONS}
        for current_root, __dirnames, filenames in os.walk(image_root, followlinks=False):
            for filename in filenames:
                extension = os.path.splitext(filename)[1].lower()
                if extension not in supported_extensions:
                    continue
                absolute_path = os.path.realpath(os.path.join(current_root, filename))
                try:
                    if os.path.commonpath([image_root, absolute_path]) != image_root:
                        continue
                    stat = os.stat(absolute_path)
                except OSError as error:
                    invalid_entries.append(self._make_invalid_entry(image_root, absolute_path, filename, str(error)))
                    continue
                if not stat.st_size:
                    invalid_entries.append(self._make_invalid_entry(image_root, absolute_path, filename, _("Empty image file.")))
                    continue
                relative_path = os.path.relpath(absolute_path, image_root)
                parent_names = [
                    part
                    for part in os.path.dirname(relative_path).split(os.sep)
                    if part and part != "."
                ]
                entries.append({
                    "absolute_path": absolute_path,
                    "relative_path": relative_path,
                    "filename": filename,
                    "filename_without_extension": os.path.splitext(filename)[0],
                    "parent_directory": parent_names[-1] if parent_names else "",
                    "parent_directory_names": parent_names,
                    "extension": extension,
                    "file_size": stat.st_size,
                    "checksum": self._file_sha256(absolute_path),
                })
        _logger.info(
            "Product image scan completed: root=%s files=%s invalid=%s",
            image_root,
            len(entries),
            len(invalid_entries),
        )
        return {
            "image_root": image_root,
            "entries": entries,
            "invalid_entries": invalid_entries,
        }

    @api.model
    def _make_invalid_entry(self, image_root, absolute_path, filename, reason):
        try:
            relative_path = os.path.relpath(absolute_path, image_root)
        except ValueError:
            relative_path = filename
        return {
            "absolute_path": absolute_path,
            "relative_path": relative_path,
            "filename": filename,
            "filename_without_extension": os.path.splitext(filename)[0],
            "parent_directory": "",
            "parent_directory_names": [],
            "extension": os.path.splitext(filename)[1].lower(),
            "file_size": 0,
            "checksum": "",
            "invalid_reason": reason,
        }

    @api.model
    def _file_sha256(self, absolute_path):
        digest = hashlib.sha256()
        with open(absolute_path, "rb") as image_file:
            for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @api.model
    def build_image_index(self, entries):
        by_token = defaultdict(list)
        for entry in entries:
            for token in self._entry_tokens(entry):
                by_token[token].append(entry)
        return {"by_token": by_token, "entries": entries}

    @api.model
    def _normalize_identifier(self, value):
        value = str(value or "").strip()
        return value.casefold() if value else ""

    @api.model
    def _entry_tokens(self, entry):
        tokens = {
            self._normalize_identifier(entry.get("filename_without_extension")),
        }
        for parent_name in entry.get("parent_directory_names") or []:
            tokens.add(self._normalize_identifier(parent_name))
        tokens.discard("")
        return tokens

    @api.model
    def _product_identifiers(self, product):
        identifiers = []
        if product.code:
            identifiers.append(("code", product.code))
        for barcode in product.barcode_ids.filtered("name"):
            identifiers.append(("barcode", barcode.name))
        if "eplus_serial" in product._fields and product.eplus_serial:
            identifiers.append(("eplus_serial", product.eplus_serial))
        return [
            (method, raw_value, self._normalize_identifier(raw_value))
            for method, raw_value in identifiers
            if self._normalize_identifier(raw_value)
        ]

    @api.model
    def _get_website_products(self, product_domain=None):
        domain = [("website_product_tmpl_id", "!=", False)]
        if product_domain:
            domain += product_domain
        return self.env["ab_product"].sudo().with_context(active_test=False).search(domain)

    @api.model
    def prepare_sync_plan(self, directory_path=None, products=None, product_domain=None):
        scan = self.scan_image_root(directory_path)
        image_index = self.build_image_index(scan["entries"])
        products = products.sudo() if products is not None else self._get_website_products(product_domain)
        summary = self._new_summary(len(products), len(scan["entries"]))
        placeholder_checksum = self._placeholder_image_sha256()
        report = []
        for invalid_entry in scan["invalid_entries"]:
            summary["invalid"] += 1
            report.append(self._report_line(
                status="invalid",
                reason=invalid_entry.get("invalid_reason") or _("Invalid image file."),
                image_entry=invalid_entry,
            ))
        for product in products:
            line = self._plan_product_image(product, image_index, placeholder_checksum)
            report.append(line)
            summary[line["status"]] = summary.get(line["status"], 0) + 1
            if line["status"] == "unchanged":
                summary["matched"] += 1
            if line["status"] == "matched":
                summary["to_update"] += 1
                summary["replacements" if line["replaces_existing"] else "new_images"] += 1
        return {
            "image_root": scan["image_root"],
            "summary": summary,
            "report": report,
        }

    @api.model
    def _new_summary(self, product_count, image_count):
        return {
            "products_scanned": product_count,
            "images_found": image_count,
            "matched": 0,
            "missing": 0,
            "ambiguous": 0,
            "invalid": 0,
            "error": 0,
            "updated": 0,
            "unchanged": 0,
            "to_update": 0,
            "new_images": 0,
            "replacements": 0,
            "kept_existing": 0,
        }

    @api.model
    def _plan_product_image(self, product, image_index, placeholder_checksum=""):
        candidates = self._match_product_candidates(product, image_index)
        if not candidates:
            return self._report_line(
                product=product,
                status="missing",
                reason=_("No matching image was found. Existing Odoo image, if any, will be kept."),
            )
        selected, reason = self._select_primary_image(candidates)
        if not selected:
            return self._report_line(
                product=product,
                status="ambiguous",
                reason=reason,
                image_entry=candidates[0]["entry"],
                match_method=candidates[0]["method"],
                matched_identifier=candidates[0]["identifier"],
            )
        image_entry = selected["entry"]
        valid, validation_reason = self._validate_image_entry(image_entry)
        if not valid:
            return self._report_line(
                product=product,
                status="invalid",
                reason=validation_reason,
                image_entry=image_entry,
                match_method=selected["method"],
                matched_identifier=selected["identifier"],
            )
        template = product.website_product_tmpl_id
        current_checksum = self._template_image_sha256(template)
        if current_checksum == image_entry["checksum"] or (
            template.website_image_source_checksum == image_entry["checksum"]
            and template.website_image_applied_checksum == current_checksum
        ):
            return self._report_line(
                product=product,
                status="unchanged",
                reason=_("The current Odoo image already matches the source file checksum."),
                image_entry=image_entry,
                match_method=selected["method"],
                matched_identifier=selected["identifier"],
                current_checksum=current_checksum,
            )
        replaces_existing = bool(template.image_1920) and current_checksum != placeholder_checksum
        return self._report_line(
            product=product,
            status="matched",
            reason=(
                _("A different source image matches this product's existing image.")
                if replaces_existing
                else _("Image is ready to synchronize.")
            ),
            image_entry=image_entry,
            match_method=selected["method"],
            matched_identifier=selected["identifier"],
            replaces_existing=replaces_existing,
            current_checksum=current_checksum,
        )

    @api.model
    def _match_product_candidates(self, product, image_index):
        seen_paths = set()
        candidates = []
        for method, raw_identifier, token in self._product_identifiers(product):
            for entry in image_index["by_token"].get(token, []):
                absolute_path = entry["absolute_path"]
                if absolute_path in seen_paths:
                    continue
                seen_paths.add(absolute_path)
                candidates.append({
                    "entry": entry,
                    "method": method,
                    "identifier": str(raw_identifier),
                    "method_priority": self._identifier_priority(method),
                    "specificity": self._entry_specificity(entry, token),
                })
            if candidates:
                break
        return candidates

    @api.model
    def _identifier_priority(self, method):
        return {
            "code": 1,
            "barcode": 2,
            "eplus_serial": 3,
        }.get(method, 99)

    @api.model
    def _entry_specificity(self, entry, token):
        filename_token = self._normalize_identifier(entry.get("filename_without_extension"))
        parent_tokens = [
            self._normalize_identifier(name)
            for name in entry.get("parent_directory_names") or []
        ]
        if filename_token == token:
            return 5
        if token in parent_tokens:
            return 4
        return 0

    @api.model
    def _select_primary_image(self, candidates):
        if len(candidates) == 1:
            return candidates[0], ""
        ranked = sorted(candidates, key=self._candidate_sort_key)
        best = ranked[0]
        if self._candidate_sort_key(best) == self._candidate_sort_key(ranked[1]):
            return None, _("Multiple matching images were found without a deterministic primary image.")
        return best, ""

    @api.model
    def _candidate_sort_key(self, candidate):
        entry = candidate["entry"]
        stem = self._normalize_identifier(entry.get("filename_without_extension"))
        if stem in MAIN_IMAGE_NAMES:
            name_rank = 0
        elif stem in ORDERED_IMAGE_NAMES:
            name_rank = 10 + ORDERED_IMAGE_NAMES.index(stem)
        else:
            name_rank = 200
        return (
            candidate["method_priority"],
            name_rank,
            -candidate["specificity"],
        )

    @api.model
    def _validate_image_entry(self, image_entry):
        absolute_path = image_entry.get("absolute_path")
        if not absolute_path or not os.path.isfile(absolute_path):
            return False, _("Image file does not exist.")
        if not os.access(absolute_path, os.R_OK):
            return False, _("Image file is not readable.")
        if not image_entry.get("file_size"):
            return False, _("Image file is empty.")
        if Image is None:
            return True, ""
        try:
            with Image.open(absolute_path) as image:
                image.verify()
        except Exception as error:
            return False, _("Invalid image file: %s") % error
        return True, ""

    @api.model
    def _template_image_sha256(self, template):
        if not template or not template.image_1920:
            return ""
        try:
            image_data = base64.b64decode(template.image_1920)
        except (TypeError, ValueError):
            return ""
        return hashlib.sha256(image_data).hexdigest()

    @api.model
    def _placeholder_image_sha256(self):
        if not os.path.isfile(WEBSITE_PLACEHOLDER_IMAGE_PATH):
            return ""
        return self._file_sha256(WEBSITE_PLACEHOLDER_IMAGE_PATH)

    @api.model
    def apply_sync_plan(self, plan, batch_size=100, replace_existing=True):
        report = []
        summary = dict(plan["summary"])
        updates = [line for line in plan["report"] if line["status"] == "matched" and line.get("product_id")]
        _logger.info(
            "Product image synchronization started: root=%s matched=%s pending_updates=%s",
            plan.get("image_root"),
            summary.get("matched", 0),
            len(updates),
        )
        Product = self.env["ab_product"].sudo()
        for line in plan["report"]:
            if line["status"] != "matched" or not line.get("product_id"):
                report.append(line)
                continue
            if line.get("replaces_existing") and not replace_existing:
                summary["kept_existing"] += 1
                report.append(dict(
                    line,
                    status="kept",
                    reason=_("Existing Odoo image kept by user choice."),
                ))
                continue
            product = Product.browse(line["product_id"])
            try:
                image_path = line["image_path"]
                with open(image_path, "rb") as image_file:
                    image_payload = base64.b64encode(image_file.read())
                with self.env.cr.savepoint():
                    template = product.website_product_tmpl_id.sudo().with_context(bin_size=False)
                    if not template._apply_website_sync_image(image_payload):
                        summary["unchanged"] += 1
                        report.append(dict(line, status="unchanged", reason=_("The current Odoo image already matches the source file checksum.")))
                        continue
                updated_line = dict(line, status="updated", reason=_("Image synchronized."))
                summary["updated"] += 1
                report.append(updated_line)
            except (SerializationFailure, DeadlockDetected):
                raise
            except Exception as error:
                _logger.exception("Failed to synchronize product image for ab_product id=%s", product.id)
                summary["error"] += 1
                report.append(dict(line, status="error", reason=str(error)))
            if len(report) % batch_size == 0:
                self.env.flush_all()
        _logger.info(
            "Product image synchronization completed: updated=%s unchanged=%s missing=%s ambiguous=%s invalid=%s errors=%s",
            summary.get("updated", 0),
            summary.get("unchanged", 0),
            summary.get("missing", 0),
            summary.get("ambiguous", 0),
            summary.get("invalid", 0),
            summary.get("error", 0),
        )
        return dict(plan, summary=summary, report=report)

    @api.model
    def _report_line(
        self,
        product=None,
        status="missing",
        reason="",
        image_entry=None,
        match_method="",
        matched_identifier="",
        replaces_existing=False,
        current_checksum="",
    ):
        image_entry = image_entry or {}
        return {
            "product_code": product.code if product else "",
            "product_name": product.display_name if product else "",
            "product_id": product.id if product else False,
            "matched_identifier": matched_identifier or "",
            "image_path": image_entry.get("absolute_path", ""),
            "relative_path": image_entry.get("relative_path", ""),
            "match_method": match_method or "",
            "status": status,
            "reason": reason or "",
            "checksum": image_entry.get("checksum", ""),
            "replaces_existing": replaces_existing,
            "current_checksum": current_checksum or "",
        }

    @api.model
    def format_summary(self, plan):
        summary = plan["summary"]
        labels = [
            ("products_scanned", _("Products scanned")),
            ("images_found", _("Images found")),
            ("matched", _("Matched products")),
            ("missing", _("Missing images")),
            ("ambiguous", _("Ambiguous matches")),
            ("invalid", _("Invalid image files")),
            ("unchanged", _("Already synchronized")),
            ("to_update", _("Images requiring update")),
            ("new_images", _("New images")),
            ("replacements", _("Existing images requiring replacement")),
            ("updated", _("Updated images")),
            ("kept_existing", _("Existing images kept")),
            ("error", _("Errors")),
        ]
        return "\n".join(
            "%s: %s" % (label, summary.get(key, 0))
            for key, label in labels
        )
