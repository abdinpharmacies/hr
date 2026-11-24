from math import isfinite

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..wizard.offer_workbook import _benefit, _draft_date, _november_offers, _offer_text, draft_source_evidence


class OfferDraft(models.Model):
    _name = "ab_storefront_offer_draft"
    _description = "Offer Review Draft"
    _order = "id"

    name = fields.Char(required=True)
    website_id = fields.Many2one("website", required=True, readonly=True, ondelete="restrict")
    company_id = fields.Many2one(related="website_id.company_id", store=True)
    sheet_key = fields.Char(required=True, readonly=True)
    source = fields.Char(readonly=True)
    original_terms = fields.Text(readonly=True)
    reason = fields.Text(string="Reason for Review", readonly=True)
    display_reason = fields.Text(string="Reason for Review", compute="_compute_display_reason")
    details = fields.Text(string="Product Codes and Brands", readonly=True)
    review_evidence = fields.Json(readonly=True)
    review_explanation = fields.Text(string="What Needs Review", compute="_compute_review_explanation")
    stock_review = fields.Boolean(string="Stock Review", readonly=True)
    manual_only = fields.Boolean(string="Requires Separate Setup", readonly=True)
    date_from = fields.Date()
    date_to = fields.Date()
    product_ids = fields.Many2many("product.product", string="Eligible Products", context={"active_test": False})
    group_qty = fields.Integer(string="Qualifying Group Size", default=1)
    discount_qty = fields.Integer(string="Discounted Units per Group", default=1)
    rate = fields.Float(string="Discount Percentage")
    fixed_price = fields.Float(string="Final Unit Price in EGP", digits="Product Price")
    priority = fields.Integer()
    note = fields.Text(string="Review Notes")
    state = fields.Selection([
        ("draft", "Draft"), ("applied", "Applied"), ("skipped", "Set Aside"),
    ], default="draft", required=True, readonly=True)
    program_id = fields.Many2one("loyalty.program", readonly=True, ondelete="restrict",
                                 groups="sales_team.group_sale_manager")

    _unique_source = models.Constraint("UNIQUE(website_id, sheet_key)", "This sheet row already has a draft.")

    def _reason_messages(self):
        return {
            **self.env["ab_storefront_offer_sheet"]._source_issue_labels(),
            "matches": _("Review matches"),
            "unmatched": _("No matching store products"),
            "existing": _("The existing program needs manual review"),
            "imported": _("Already imported"),
            "stock": _("No available stock for: %s"),
            "quantity": _("Available stock is below the qualifying group size of %s."),
        }

    def _reason_translations(self):
        target = self._reason_messages()
        labels = {}
        formats = {}
        for lang in {"en_US", *(code for code, _name in self.env["res.lang"].get_installed())}:
            for key, message in self.with_context(lang=lang)._reason_messages().items():
                if "%s" in message:
                    prefix, suffix = message.split("%s", 1)
                    formats[prefix, suffix] = target[key]
                else:
                    labels[message] = target[key]
        return labels, formats

    @staticmethod
    def _localize_reason(text, labels, formats):
        if not text:
            return text
        parts = []
        for part in text.split(" / "):
            translated = labels.get(part, part)
            for (prefix, suffix), template in formats.items():
                if part.startswith(prefix) and part.endswith(suffix):
                    translated = template % part[len(prefix):len(part) - len(suffix)]
                    break
            parts.append(translated)
        return " / ".join(parts)

    @api.depends("reason")
    @api.depends_context("lang")
    def _compute_display_reason(self):
        labels, formats = self._reason_translations()
        for draft in self:
            draft.display_reason = self._localize_reason(draft.reason, labels, formats)

    @api.depends("review_evidence", "sheet_key", "original_terms", "reason", "details", "source", "name")
    @api.depends_context("lang")
    def _compute_review_explanation(self):
        labels, formats = self._reason_translations()
        for draft in self:
            evidence = draft.review_evidence or draft._saved_review_evidence()
            if evidence.get("stock_issue"):
                evidence = dict(evidence, stock_issue=self._localize_reason(evidence["stock_issue"], labels, formats))
            draft.review_explanation = "\n".join(draft._explain_evidence(evidence))

    def _saved_review_evidence(self):
        terms = (self.original_terms or "").splitlines()
        start, _, end = (terms[-1] if terms else "").partition(" — ")
        row = {"name": self.name or "", "offer": terms[0] if terms else "", "description": "\n".join(terms[1:-1]),
               "start": start, "end": end, "issues": []}
        saved_lines = (self.details or "").splitlines()
        reasons = set((self.reason or "").split(" / "))
        markers = set()
        sheet = self.env["ab_storefront_offer_sheet"]
        for language in {"en_US", self.env.lang, *(lang for lang, _name in self.env["res.lang"].get_installed())}:
            localized = sheet.with_context(lang=language)
            row["issues"].extend(key for key, label in localized._source_issue_labels().items() if label in reasons)
            markers.update((localized.env._("Code missing from store"), localized.env._("Code matches multiple products"),
                            localized.env._("Conflicting product identity")))
        reference = _november_offers()
        original = next((r for r in reference["offers"] if r["key"] == self.sheet_key), None)
        codes = [line.partition("  ")[0] for line in saved_lines]
        evidence = dict(row, products={})
        if (original and codes == original["codes"] and original["start"] == start and original["end"] == end
                and original["description"].strip() == row["description"].strip()
                and sheet._offer_label(original) == row["offer"]):
            evidence = draft_source_evidence(dict(original, issues=row["issues"]), reference, {})
            evidence["reference"] = bool(evidence["products"])
        evidence["saved_lines"] = [line for line in saved_lines if
            line.split(" | ", 1)[0].rsplit(" — ", 1)[-1] in markers or
            any(not all(_benefit(token.strip())[3] for token in part.split(","))
                for part in line.split(" | ")[1:])]
        return evidence

    def _explain_evidence(self, data):
        issues = data["issues"]
        lines = []
        if "dates" in issues:
            start, end = data["start"], data["end"]
            first, last = _draft_date(start), _draft_date(end)
            if not start:
                lines.append(_("The From cell is empty. Enter the offer start date."))
            elif not first:
                lines.append(_("The start date in From could not be read: %s", start))
            if not end:
                lines.append(_("The To cell is empty. Enter the offer end date."))
            elif not last:
                lines.append(_("The end date in To could not be read: %s", end))
            if first and last and last < first:
                lines.append(_("The end date %(end)s is before the start date %(start)s.", end=end, start=start))
        offer = _offer_text(data["offer"] or "")
        if "codes" in issues:
            lines.append(_("No codes were confirmed for %(name)s with offer %(offer)s in the Offer Codes tab.",
                           name=data["name"], offer=offer))
        if "terms" in issues:
            lines.append(_("The offer value is %(offer)s. Compare it with the description: %(description)s",
                           offer=offer, description=data["description"] or _("No description supplied")))
        if "scope" in issues:
            lines.append(_("Confirm which products are included or excluded by the terms for %s.", data["name"]))
        if "allocation" in issues:
            lines.append(_("The allocation for each participating branch must be confirmed for %s.", data["name"]))
        if "gift" in issues:
            lines.append(_("Identify the purchased product and the separate gift product for %s.", data["name"]))
        if data.get("existing_program"):
            lines.append(_("Review the existing offer before changing its products or rules: %s", data["existing_program"]))
        if data.get("reference"):
            lines.append(_("The November reference lists the following code details for this offer."))
        products = data["products"]
        for code, product in products.items():
            findings = []
            if "identities" in product:
                findings.append(_("The same code appears in the codes tab with these product and group names: %s",
                                  " / ".join(f"{name} ({group})" for name, group in product["identities"])))
            for name, internal, linked in product.get("identifiers", []):
                findings.append(_("Store product %(name)s has internal code %(internal)s and linked code %(linked)s.",
                                  name=name, internal=internal, linked=linked))
            if "candidates" in product:
                candidates = product["candidates"]
                findings.append(_("This code matched multiple store products: %s", " / ".join(candidates)) if candidates
                                else _("No active saleable product matched this code for this website and company."))
            if product.get("store_name"):
                findings.append(_("The sheet name differs from the store name: %s", product["store_name"]))
            if product.get("variant_brands"):
                findings.append(_("The variants have different sheet brands: %s", " / ".join(product["variant_brands"])))
            if product.get("brand"):
                sheet_brand, current, count, inactive = product["brand"]
                if current:
                    findings.append(_("Sheet brand: %(sheet)s. Store brand: %(store)s.", sheet=sheet_brand, store=current))
                if count > 1:
                    findings.append(_("More than one store brand matches %s.", sheet_brand))
                if inactive:
                    findings.append(_("The matching brand is archived: %s", sheet_brand))
            if product.get("offers"):
                values = [_offer_text(value) for value in product["offers"]]
                findings.append(_("The codes tab lists %(values)s for this code. The offer row specifies %(offer)s.",
                                  values=" / ".join(values), offer=offer))
            if findings:
                lines.append(f"{code} · {product['name']} — " + " ".join(findings))
        if data.get("stock_issue"):
            lines.append(data["stock_issue"])
        lines.extend(data.get("saved_lines", []))
        if "identity" in issues and not any("identities" in p or "identifiers" in p for p in products.values()):
            lines.append(_("The sheet flagged a product identity conflict. Compare the original names and groups for the listed codes."))
        if not lines and (data.get("review") or self.reason):
            lines.append(_("Confirm the listed codes and offer terms against the source row: %s", self.source))
        return lines

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_("Drafts are created by the spreadsheet import."))

    @api.model
    def _from_sheet(self, values):
        model = self.with_context({}, lang=self.env.lang, allowed_company_ids=[self.env.company.id])
        return super(OfferDraft, model).create(values)

    def _reopen_stock_review(self, values):
        self.ensure_one()
        self._check_decision()
        if not self.stock_review:
            raise UserError(_("This row requires separate offer setup."))
        return super().write(values)

    def write(self, values):
        self.check_access("write")
        self.lock_for_update(allow_referencing=True)
        allowed = {"name", "date_from", "date_to", "product_ids", "group_qty", "discount_qty",
                   "rate", "fixed_price", "priority", "note"}
        if values.keys() - allowed or any(d.state != "draft" for d in self):
            raise AccessError(_("Only pending draft terms can be edited."))
        if values.keys() - {"note"} and self.filtered("stock_review"):
            raise AccessError(_("Only pending draft terms can be edited."))
        product_ids = set()
        for command in values.get("product_ids", []):
            if command[0] == Command.SET:
                product_ids.update(command[2])
            elif command[0] == Command.LINK:
                product_ids.add(command[1])
            elif command[0] not in (Command.UNLINK, Command.CLEAR):
                raise ValidationError(_("Select existing products for this offer."))
        if product_ids:
            products = self.env["product.product"].browse(product_ids)
            for draft in self:
                draft._validate_products(products)
        return super().write(values)

    @api.constrains("product_ids", "website_id")
    def _check_products(self):
        for draft in self:
            draft._validate_products(draft.with_context(active_test=False).product_ids)

    def _validate_products(self, products):
        products.check_access("read")
        if any(not p.active or not p.sale_ok or (p.company_id and p.company_id != self.company_id)
               or (p.website_id and p.website_id != self.website_id) for p in products):
            raise ValidationError(_("Select active saleable products for this website and company."))

    def _check_decision(self):
        self.ensure_one()
        self.check_access("write")
        if not self.env.user.has_group("sales_team.group_sale_manager") or self.company_id != self.env.company:
            raise AccessError(_("Only a sales manager in the current company can decide this draft."))
        self.website_id.check_access("read")
        self.website_id.lock_for_update(allow_referencing=True)
        self.lock_for_update(allow_referencing=True)

    def action_set_aside(self):
        self._check_decision()
        if self.state == "draft":
            super().write({"state": "skipped"})

    def action_apply(self):
        self._check_decision()
        if self.state == "applied":
            return
        if self.state != "draft" or self.manual_only:
            raise UserError(_("This row requires separate offer setup."))
        if self.stock_review:
            program = self.program_id.with_context(active_test=False)
            if (not program or program.company_id != self.company_id or program.website_id != self.website_id
                    or self.sheet_key != f"stock-review:{program.ab_sheet_key}" or program.ab_storefront_offer_id
                    or len(program.rule_ids) != 1 or len(program.reward_ids) != 1):
                raise UserError(_("This row requires separate offer setup."))
            program.check_access("write")
            program.lock_for_update(allow_referencing=True)
            if program.date_to and program.date_to < fields.Date.context_today(self):
                raise UserError(_("This offer has expired."))
            persisted = program.sudo()
            eligible = persisted.rule_ids.product_ids & persisted.reward_ids.discount_product_ids
            products = self.env["product.product"].with_context(active_test=True).search([
                ("id", "in", eligible.ids), ("sale_ok", "=", True),
                ("website_id", "in", [False, self.website_id.id]), ("company_id", "in", [False, self.company_id.id]),
            ])
            if set(products.ids) != set(eligible.ids):
                raise UserError(_("The existing program needs manual review"))
            quantities = self.website_id._ab_offer_available_quantities(products)
            issue = self.website_id._ab_offer_stock_issue(products, quantities, program.ab_sheet_group_qty)
            if issue:
                raise UserError(issue)
            self.website_id._ab_publish_offer_products(products)
            wizard = self.env["ab_storefront_offer_sheet"].new({"website_id": self.website_id.id})
            wizard._set_stock_review_program_active(program, True)
            super().write({"state": "applied"})
            return
        if not self.date_from or not self.date_to or self.date_from > self.date_to or not self.product_ids:
            raise UserError(_("Set a valid period and select the eligible products."))
        if (not 1 <= self.discount_qty <= self.group_qty or self.priority < 0
                or not isfinite(self.rate) or not 0 < self.rate <= 100
                or not isfinite(self.fixed_price) or self.fixed_price < 0
                or (self.fixed_price and self.rate != 100)):
            raise UserError(_("Check the quantities and percentage. A fixed unit price requires a 100% reward."))
        self._check_products()
        if self.env["loyalty.program"].with_context(active_test=False).search_count([
            ("website_id", "=", self.website_id.id), ("company_id", "=", self.company_id.id),
            ("ab_sheet_key", "=", self.sheet_key),
        ]):
            raise UserError(_("An offer already exists for this row. Review the existing offer."))
        quantities = self.website_id._ab_offer_available_quantities(self.product_ids)
        issue = self.website_id._ab_offer_stock_issue(self.product_ids, quantities, self.group_qty)
        if issue:
            raise UserError(issue)
        if self.date_to >= fields.Date.context_today(self):
            self.website_id._ab_publish_offer_products(self.product_ids)
        benefit = f"{self.fixed_price:g} EGP" if self.fixed_price else f"{self.rate:g}%"
        if self.group_qty > 1:
            benefit = _("%(benefit)s on %(units)s of every %(quantity)s units",
                        benefit=benefit, units=self.discount_qty, quantity=self.group_qty)
        row = {"key": self.sheet_key, "name": self.name, "offer": benefit,
               "start": self.date_from, "end": self.date_to, "bundle": self.group_qty,
               "units": self.discount_qty, "rate": self.rate, "fixed": self.fixed_price}
        wizard = self.env["ab_storefront_offer_sheet"].new({"website_id": self.website_id.id})
        program = wizard._create_program(row, self.product_ids.ids, self.priority)
        super().write({"state": "applied", "program_id": program.id})
