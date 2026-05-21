import re

from odoo import _, fields, models
from odoo.exceptions import UserError


class AbWebsiteSaleAddManyByCodesWizard(models.TransientModel):
    _name = "ab.website.sale.add.many.by.codes.wizard"
    _description = "Add Many Abdin Products By Codes"

    codes_text = fields.Text(
        string="Codes",
        required=True,
        help="Enter product codes separated by commas.",
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
