import base64
import binascii
import csv
import hashlib
import io
import json
import re

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class LegacyPublicationImport(models.TransientModel):
    _name = "ab_legacy_publication_import"
    _description = "Legacy Website Publication Import"

    source_file = fields.Binary(string="Old Website Export", required=True, attachment=False)
    source_filename = fields.Char(string="File Name")
    website_id = fields.Many2one(
        "website", required=True,
        default=lambda self: self.env["website"].search(
            [("company_id", "in", self.env.companies.ids)], limit=1,
        ),
    )
    state = fields.Selection(
        [("draft", "Draft"), ("review", "Ready to Apply"), ("done", "Applied")],
        default="draft", readonly=True,
    )
    source_digest = fields.Char(readonly=True)
    exported_at = fields.Char(string="Exported At", readonly=True)
    published_count = fields.Integer(string="Unique Products to Match", readonly=True)
    missing_count = fields.Integer(string="Codes Missing in New Catalog", readonly=True)
    ineligible_count = fields.Integer(string="Products Not Eligible for Publication", readonly=True)
    skipped_code_sample = fields.Text(string="Skipped Code Examples", readonly=True)
    create_count = fields.Integer(string="Products to Add", readonly=True)
    publish_count = fields.Integer(string="Products to Publish", readonly=True)
    unpublish_count = fields.Integer(string="Products to Unpublish", readonly=True)

    def _check_manager(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only system administrators can reconcile website publication."))
        self.check_access("write")
        if self.website_id.company_id not in self.env.companies:
            raise AccessError(_("The selected website is outside your allowed companies."))

    def _load_source(self):
        self.ensure_one()
        self._check_manager()
        try:
            raw = base64.b64decode(self.source_file or b"", validate=True)
        except (binascii.Error, ValueError):
            raise UserError(_("Upload a valid publication export JSON or CSV file.")) from None
        if len(raw) > 20 * 1024 * 1024:
            raise UserError(_("The publication export must not exceed 20 MB."))
        if self.source_filename and self.source_filename.lower().endswith(".csv"):
            return self._load_csv_source(raw)
        try:
            source = json.loads(raw)
        except (UnicodeError, ValueError):
            raise UserError(_("Upload a valid publication export JSON or CSV file.")) from None
        if (
            not isinstance(source, dict)
            or source.get("source") != "https://abdinpharmacies.com"
            or source.get("model") != "product.template"
            or source.get("publication_field") not in ("is_published", "website_published")
            or not isinstance(source.get("exported_at"), str)
            or not isinstance(source.get("products"), list)
            or not isinstance(source.get("published_count"), int)
            or source["published_count"] != len(source["products"])
            or not 0 < source["published_count"] <= 200000
        ):
            raise UserError(_("The old website publication export is incomplete or invalid."))
        codes = set()
        source_ids = set()
        names_without_code = set()
        for row in source["products"]:
            if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] <= 0:
                raise UserError(_("The old website publication export contains an invalid product."))
            code = row.get("default_code")
            if not isinstance(code, str) or not code.strip():
                name = row.get("name")
                if not isinstance(name, str) or not name.strip():
                    raise UserError(_("Every published old website product must have a code."))
                names_without_code.add(name.strip())
                if row["id"] in source_ids:
                    raise UserError(_("The old website publication export contains duplicate IDs or codes."))
                source_ids.add(row["id"])
                continue
            code = code.strip()
            if row["id"] in source_ids or code in codes:
                raise UserError(_("The old website publication export contains duplicate IDs or codes."))
            source_ids.add(row["id"])
            codes.add(code)
        self._resolve_uncoded_names(names_without_code, codes)
        return raw, source, codes

    def _load_csv_source(self, raw):
        try:
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
            if not reader.fieldnames or not {"Name", "Internal Reference"}.issubset(reader.fieldnames):
                raise UserError(_("The CSV export must include Name and Internal Reference columns."))
            codes = set()
            names_without_code = set()
            for row in reader:
                if None in row:
                    raise UserError(_("The CSV export contains a malformed row."))
                name = (row["Name"] or "").strip()
                code = (row["Internal Reference"] or "").strip()
                if not name and not code:
                    if any(value for field, value in row.items() if field not in ("Website Product Category", "Tags") and value):
                        raise UserError(_("The CSV export contains a product without a name or code."))
                    continue
                if not name:
                    raise UserError(_("The CSV export contains a product without a name."))
                if code:
                    if code in codes:
                        raise UserError(_("The CSV export contains duplicate product codes."))
                    codes.add(code)
                else:
                    if name in names_without_code:
                        raise UserError(_("The CSV export contains duplicate product names without codes."))
                    names_without_code.add(name)
        except (UnicodeError, csv.Error):
            raise UserError(_("Upload a valid publication export JSON or CSV file.")) from None
        if not codes and not names_without_code or len(codes) + len(names_without_code) > 200000:
            raise UserError(_("The old website publication export is incomplete or invalid."))
        self._resolve_uncoded_names(names_without_code, codes)
        return raw, {"exported_at": ""}, codes

    def _resolve_uncoded_names(self, names_without_code, codes):
        Product = self.env["ab_product"].sudo().with_context(active_test=False)
        for name in sorted(names_without_code):
            words = name.replace("--", " ").split()
            domain = [("name", "ilike", word) for word in words[:3]]
            products = Product.search(domain).filtered(
                lambda product: self._publication_name_key(product.name) == self._publication_name_key(name)
            )
            if len(products) != 1 or not products.code:
                raise UserError(_("An export product without a code could not be matched uniquely: %s") % name)
            codes.add(products.code)

    @staticmethod
    def _publication_name_key(name):
        normalized = re.sub(r"\s+", " ", name.strip().upper().rstrip("- "))
        return re.sub(r" 1 BOX$", "", normalized)

    def _plan(self, codes):
        Template = self.env["product.template"].sudo().with_context(active_test=False)
        scope = [
            ("company_id", "in", [False, self.website_id.company_id.id]),
            ("website_id", "in", [False, self.website_id.id]),
        ]
        current = Template.search(scope)
        by_code = {}
        for template in current:
            code = template.ab_product_id.code if template.ab_product_id else template.default_code
            if not code or code not in codes:
                continue
            if code in by_code:
                raise UserError(_("Multiple new website products have the same code. Resolve duplicates first."))
            by_code[code] = template
        remaining = sorted(codes - by_code.keys())
        Product = self.env["ab_product"].sudo().with_context(active_test=False)
        products_by_code = {}
        for offset in range(0, len(remaining), 500):
            for product in Product.search([("code", "in", remaining[offset:offset + 500])]):
                if product.code in products_by_code:
                    raise UserError(_("Multiple Abdin products have the same code. Resolve duplicates first."))
                products_by_code[product.code] = product
        missing = set(remaining) - products_by_code.keys()
        linked_elsewhere = Template.search([("ab_product_id", "in", [product.id for product in products_by_code.values()])]) - current
        if linked_elsewhere:
            raise UserError(_("Some matching products belong to another website or company."))
        ineligible = {
            code for code in codes
            if (
                (code in products_by_code and not (
                    products_by_code[code].active and products_by_code[code].allow_sale
                    and products_by_code[code].website_sale_available
                ))
                or (code in by_code and not (
                    by_code[code].active and by_code[code].sale_ok
                    and (not by_code[code].ab_product_id or (
                        by_code[code].ab_product_id.active
                        and by_code[code].ab_product_id.allow_sale
                        and by_code[code].ab_product_id.website_sale_available
                    ))
                ))
            )
        }
        eligible_codes = codes - missing - ineligible
        if not eligible_codes:
            raise UserError(_("No export products match eligible new website products."))
        to_create = Product.browse([products_by_code[code].id for code in remaining if code in eligible_codes])
        to_publish = current.filtered(
            lambda template: not template.is_published
            and (template.ab_product_id.code if template.ab_product_id else template.default_code) in eligible_codes
        )
        to_unpublish = current.filtered(
            lambda template: template.is_published
            and (template.ab_product_id.code if template.ab_product_id else template.default_code) not in eligible_codes
        )
        return to_create, to_publish, to_unpublish, missing, ineligible

    def action_preview(self):
        self.ensure_one()
        if self.state == "done":
            raise UserError(_("This publication import has already been applied."))
        raw, source, codes = self._load_source()
        to_create, to_publish, to_unpublish, missing, ineligible = self._plan(codes)
        self.write({
            "state": "review", "source_digest": hashlib.sha256(raw).hexdigest(),
            "exported_at": source["exported_at"],
            "published_count": len(codes), "create_count": len(to_create),
            "publish_count": len(to_create) + len(to_publish),
            "unpublish_count": len(to_unpublish),
            "missing_count": len(missing), "ineligible_count": len(ineligible),
            "skipped_code_sample": ", ".join(sorted(missing | ineligible)[:20]),
        })
        return self._open_form()

    def action_apply(self):
        self.ensure_one()
        raw, source, codes = self._load_source()
        if self.state != "review" or hashlib.sha256(raw).hexdigest() != self.source_digest:
            raise UserError(_("Preview this publication export again before applying it."))
        self.env["ab_product"]._lock_website_sync()
        to_create, to_publish, to_unpublish, missing, ineligible = self._plan(codes)
        if (
            len(codes) != self.published_count
            or len(to_create) != self.create_count
            or len(to_create) + len(to_publish) != self.publish_count
            or len(to_unpublish) != self.unpublish_count
            or len(missing) != self.missing_count
            or len(ineligible) != self.ineligible_count
        ):
            raise UserError(_("Publication changed since preview. Preview the export again."))
        if to_create:
            to_create._sync_website_products(create_missing=True, publish_requested=True)
        if to_publish:
            to_publish.write({"is_published": True})
        if to_unpublish:
            to_unpublish.write({"is_published": False})
        self.write({"state": "done"})
        return self._open_form()

    def _open_form(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("ab_website_sale_product.view_legacy_publication_import_form").id,
            "target": "new",
        }
