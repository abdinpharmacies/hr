import os
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
        directory_path = (self.directory_path or "").strip()
        if not directory_path:
            raise UserError(_("Enter an images directory."))
        directory_path = os.path.abspath(os.path.expanduser(directory_path))
        if not os.path.isdir(directory_path):
            raise UserError(_("Directory does not exist: %s") % directory_path)
        if not os.access(directory_path, os.R_OK):
            raise UserError(_("Directory is not readable by the Odoo server: %s") % directory_path)
        return directory_path

    def action_sync_images(self):
        self.ensure_one()
        directory_path = self._get_directory_path()
        self.env["ir.config_parameter"].sudo().set_param(
            "ab_website_sale_product.image_directory",
            directory_path,
        )

        products = self.env["ab_product"].sudo().with_context(active_test=False).search([
            ("website_product_tmpl_id", "!=", False),
        ])
        synced_count = 0
        missing_codes = []
        failed_codes = []
        for product in products:
            image_path = product._find_website_image_file(directory_path)
            if not image_path:
                if product.code:
                    missing_codes.append(product.code)
                continue
            try:
                product._sync_website_product_image_from_file(image_path)
                synced_count += 1
            except OSError:
                failed_codes.append(product.code or str(product.id))

        message = _("Synced %(synced)s image(s). Missing: %(missing)s. Failed: %(failed)s.") % {
            "synced": synced_count,
            "missing": len(missing_codes),
            "failed": len(failed_codes),
        }
        if missing_codes[:10]:
            message += _(" First missing codes: %s.") % ", ".join(missing_codes[:10])
        if failed_codes[:10]:
            message += _(" Failed codes: %s.") % ", ".join(failed_codes[:10])

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sync Product Images"),
                "message": message,
                "type": "success" if synced_count else "warning",
                "sticky": bool(missing_codes or failed_codes),
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }


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
        return {
            "type": "ir.actions.act_window",
            "name": _("Sync Images"),
            "res_model": "ab.website.sale.add.many.by.codes.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("ab_website_sale_product.view_sync_images_wizard_form").id,
            "target": "new",
        }
