import hashlib
import re

from odoo import _, fields, models
from odoo.exceptions import UserError


class AbWebsiteSaleAddManyByCodesWizard(models.TransientModel):
    _name = "ab.website.sale.add.many.by.codes.wizard"
    _description = "Add Many Abdin Products By Codes"

    codes_text = fields.Text(
        string="Codes",
        help="Enter product codes separated by commas.",
    )
    directory_path = fields.Char(
        string="Images Directory",
        default=lambda self: self.env["ab_product"]._get_default_website_image_directory(),
        help="Server directory containing image files named by product code, for example CODE001.jpg.",
    )
    image_sync_summary = fields.Text(readonly=True)
    image_sync_confirmation_required = fields.Boolean(readonly=True)
    image_sync_confirmation_message = fields.Text(
        string="Replacement Confirmation",
        readonly=True,
    )
    image_sync_replacement_count = fields.Integer(readonly=True)
    image_sync_replacement_signature = fields.Char(readonly=True)
    image_sync_line_ids = fields.One2many(
        "ab.website.sale.image.sync.report.line",
        "wizard_id",
        string="Image Synchronization Report",
        readonly=True,
    )

    def action_sync_codes(self):
        self.ensure_one()
        raw_codes = self.codes_text or ""
        codes = [
            code.strip()
            for code in re.split(r"[,\\n\\r]+", raw_codes)
            if code and code.strip()
        ]
        if not codes:
            raise UserError(_("Enter at least one product code."))

        seen = set()
        unique_codes = []
        for code in codes:
            if code not in seen:
                seen.add(code)
                unique_codes.append(code)

        products = self.env["ab_product"].sudo().with_context(active_test=False).search([
            ("code", "in", unique_codes),
            ("allow_sale", "=", True),
        ])
        products_by_code = {product.code: product for product in products if product.code}
        missing_codes = [code for code in unique_codes if code not in products_by_code]
        matched_products = self.env["ab_product"].browse([product.id for product in products_by_code.values()])

        synced_templates = matched_products._sync_website_products() if matched_products else self.env["product.template"]
        message = _(
            "Synced %(matched)s product(s) to eCommerce. Missing codes: %(missing)s."
        ) % {
            "matched": len(matched_products),
            "missing": ", ".join(missing_codes) if missing_codes else _("None"),
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Add Many By Codes"),
                "message": message,
                "type": "success" if matched_products else "warning",
                "sticky": bool(missing_codes),
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def _get_directory_path(self):
        self.ensure_one()
        return self.env["ab.website.product.image.sync.service"].normalize_image_root(self.directory_path)

    def _check_image_sync_access(self):
        self.env["ab.website.product.image.sync.service"].check_image_sync_access()

    def _open_image_sync_wizard(self):
        self.ensure_one()
        self._check_image_sync_access()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sync Images"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("ab_website_sale_product.view_sync_images_wizard_form").id,
            "target": "new",
        }

    def _replacement_signature(self, plan):
        replacements = sorted(
            "%s:%s:%s" % (
                line["product_id"],
                line.get("checksum", ""),
                line.get("current_checksum", ""),
            )
            for line in plan["report"]
            if line["status"] == "matched" and line.get("replaces_existing")
        )
        return hashlib.sha256("\n".join(replacements).encode()).hexdigest()

    def _write_image_sync_report(self, plan, confirmation_required=False):
        self.ensure_one()
        Service = self.env["ab.website.product.image.sync.service"]
        Line = self.env["ab.website.sale.image.sync.report.line"].sudo()
        replacement_count = plan["summary"].get("replacements", 0)
        confirmation_message = ""
        if confirmation_required:
            confirmation_message = _(
                "%(replacement_count)s matched image(s) belong to products that already have images. "
                "Do you want to replace them? %(new_count)s new image(s) can be added without replacing existing images."
            ) % {
                "replacement_count": replacement_count,
                "new_count": plan["summary"].get("new_images", 0),
            }
        self.image_sync_line_ids.unlink()
        self.write({
            "directory_path": plan["image_root"],
            "image_sync_summary": Service.format_summary(plan),
            "image_sync_confirmation_required": confirmation_required,
            "image_sync_confirmation_message": confirmation_message,
            "image_sync_replacement_count": replacement_count if confirmation_required else 0,
            "image_sync_replacement_signature": (
                self._replacement_signature(plan) if confirmation_required else False
            ),
        })
        for index in range(0, len(plan["report"]), 1000):
            Line.create([
                dict(line, wizard_id=self.id)
                for line in plan["report"][index:index + 1000]
            ])
        return self._open_image_sync_wizard()

    def action_preview_images(self):
        self.ensure_one()
        self._check_image_sync_access()
        directory_path = self._get_directory_path()
        self.env["ir.config_parameter"].sudo().set_param(
            "ab_website_sale_product.image_directory",
            directory_path,
        )
        plan = self.env["ab.website.product.image.sync.service"].prepare_sync_plan(directory_path)
        return self._write_image_sync_report(plan)

    def _prepare_image_sync_plan(self):
        self.ensure_one()
        self._check_image_sync_access()
        directory_path = self._get_directory_path()
        self.env["ir.config_parameter"].sudo().set_param(
            "ab_website_sale_product.image_directory",
            directory_path,
        )
        Service = self.env["ab.website.product.image.sync.service"]
        return Service, Service.prepare_sync_plan(directory_path)

    def action_sync_images(self):
        self.ensure_one()
        Service, plan = self._prepare_image_sync_plan()
        if plan["summary"].get("replacements"):
            return self._write_image_sync_report(plan, confirmation_required=True)
        result = Service.apply_sync_plan(plan)
        return self._write_image_sync_report(result)

    def action_confirm_replace_images(self):
        self.ensure_one()
        Service, plan = self._prepare_image_sync_plan()
        replacement_count = plan["summary"].get("replacements", 0)
        if replacement_count and self._replacement_signature(plan) != self.image_sync_replacement_signature:
            return self._write_image_sync_report(plan, confirmation_required=True)
        result = Service.apply_sync_plan(plan, replace_existing=True)
        return self._write_image_sync_report(result)

    def action_sync_new_images_only(self):
        self.ensure_one()
        Service, plan = self._prepare_image_sync_plan()
        result = Service.apply_sync_plan(plan, replace_existing=False)
        return self._write_image_sync_report(result)


class AbProduct(models.Model):
    _inherit = "ab_product"

    def action_open_add_many_by_codes_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Add Many By Codes"),
            "res_model": "ab.website.sale.add.many.by.codes.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def action_open_sync_images_wizard(self):
        self.env["ab.website.product.image.sync.service"].check_image_sync_access()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sync Images"),
            "res_model": "ab.website.sale.add.many.by.codes.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("ab_website_sale_product.view_sync_images_wizard_form").id,
            "target": "new",
        }


class AbWebsiteSaleImageSyncReportLine(models.TransientModel):
    _name = "ab.website.sale.image.sync.report.line"
    _description = "Product Image Synchronization Report Line"
    _order = "id"

    wizard_id = fields.Many2one(
        "ab.website.sale.add.many.by.codes.wizard",
        required=True,
        ondelete="cascade",
    )
    product_code = fields.Char(readonly=True)
    product_name = fields.Char(readonly=True)
    product_id = fields.Integer(readonly=True)
    matched_identifier = fields.Char(readonly=True)
    image_path = fields.Char(readonly=True)
    relative_path = fields.Char(readonly=True)
    match_method = fields.Char(readonly=True)
    status = fields.Selection(
        selection=[
            ("matched", "Matched"),
            ("updated", "Updated"),
            ("unchanged", "Unchanged"),
            ("kept", "Kept Existing"),
            ("missing", "Missing"),
            ("ambiguous", "Ambiguous"),
            ("invalid", "Invalid"),
            ("error", "Error"),
        ],
        readonly=True,
    )
    reason = fields.Char(readonly=True)
    checksum = fields.Char(readonly=True)
    current_checksum = fields.Char(readonly=True)
    replaces_existing = fields.Boolean(readonly=True)
