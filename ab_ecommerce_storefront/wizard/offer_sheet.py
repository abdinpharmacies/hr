import base64
import binascii
import hashlib
import re
import unicodedata
from collections import defaultdict

from odoo import Command, _, fields, models
from odoo.exceptions import AccessError, UserError

from .offer_workbook import _draft_date, _november_offers, _offer_text, draft_source_evidence, parse_offer_workbook


def _normalized(value):
    return re.sub(r"[^\w]+", "", (value or "").casefold())


_SELLING_UNIT_SUFFIX = re.compile(
    r"\s+1\s+(?:box|one unit|unit|bottle|tube|spray|packet)"
    r"(?:,\s*1\s+(?:one unit|unit|bottle))?\s*$", re.IGNORECASE,
)


def _product_name_matches(source, catalog_name):
    def tokens(name):
        return re.findall(r"\d+(?:[.,]\d+)?|[^\W\d_]+|[+/%×-]", unicodedata.normalize("NFKC", name).casefold())

    expected = tokens(source)
    actual = catalog_name or ""
    return expected == tokens(actual) or expected == tokens(_SELLING_UNIT_SUFFIX.sub("", actual))


class OfferSheet(models.TransientModel):
    _name = "ab_storefront_offer_sheet"
    _description = "Storefront Offer Sheet"

    website_id = fields.Many2one("website", required=True, default=lambda self: self.env["website"].search(
        [("company_id", "=", self.env.company.id)], limit=1))
    workbook = fields.Binary(string="Excel Workbook", attachment=False, required=True)
    filename = fields.Char(string="File Name")
    preview_digest = fields.Char(readonly=True)
    include_brands = fields.Boolean(string="Link verified brands from the entire sheet")
    brand_summary = fields.Text(string="Brand Links", readonly=True)
    brand_signature = fields.Char(readonly=True)
    line_ids = fields.One2many("ab_storefront_offer_sheet_line", "wizard_id", string="Offers")

    def _check_scope(self):
        self.ensure_one()
        self.check_access("write")
        if not self.env.user.has_group("sales_team.group_sale_manager") or self.website_id.company_id != self.env.company:
            raise AccessError(_("Choose a website in your current company."))
        self.website_id.check_access("read")

    def _uploaded_file(self):
        encoded = self.with_context(bin_size=False).workbook
        if not encoded or (self.filename and not self.filename.lower().endswith(".xlsx")):
            raise UserError(_("Choose a readable Excel workbook (.xlsx)."))
        if len(encoded) > 16 * 1024 * 1024:
            raise UserError(_("The workbook is too large."))
        try:
            return base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise UserError(_("Choose a readable Excel workbook (.xlsx).")) from exc

    def _source_issue_labels(self):
        return {
            "dates": _("Missing or invalid dates"), "allocation": _("Branch allocation required"),
            "gift": _("Specific gift product required"), "identity": _("Conflicting product identity"),
            "terms": _("Offer and description disagree"), "scope": _("Eligible items need clarification"),
            "codes": _("No confirmed product codes"),
        }

    def _snapshot(self, payload):
        sheet = parse_offer_workbook(payload, _november_offers())
        products = self.env["product.product"].with_context(lang="en_US")
        codes = list(sheet["products"])
        scope = fields.Domain([
            ("company_id", "in", [False, self.env.company.id]),
            ("website_id", "in", [False, self.website_id.id]), ("sale_ok", "=", True),
        ])
        variants = products.search_fetch(scope & (fields.Domain("default_code", "in", codes)
            | fields.Domain("ab_product_id.code", "in", codes)), ["default_code", "ab_product_id", "product_tmpl_id"])
        by_code = defaultdict(list)
        conflicting_codes = set()
        for product in variants:
            identifiers = {product.default_code, product.ab_product_id.code} - {False}
            if len(identifiers) > 1:
                conflicting_codes.update(identifiers)
            for code in identifiers:
                by_code[code].append(product)
        brands = defaultdict(list)
        for brand in self.env["ab_product_company"].with_context(active_test=False).search_fetch([], ["name", "active"]):
            brands[_normalized(brand.name)].append(brand)
        installed = self.env["loyalty.program"].with_context(active_test=False).search([
            ("website_id", "=", self.website_id.id), ("company_id", "=", self.env.company.id),
            ("ab_sheet_key", "!=", False)])
        existing = {program.ab_sheet_key: program for program in installed}
        issues = self._source_issue_labels()
        template_brands = defaultdict(set)
        for code, (_source_name, name) in sheet["products"].items():
            if name and len(by_code[code]) == 1:
                template_brands[by_code[code][0].product_tmpl_id.id].add(_normalized(name))
        matches = {}
        product_problems = {}
        brand_products = defaultdict(set)
        brand_summary = defaultdict(list)
        for code, (name, brand_name) in sheet["products"].items():
            candidates = by_code[code]
            heading = f"{code}  {name}"
            if code in conflicting_codes:
                product_problems[code] = {"identifiers": [[p.name, p.default_code, p.ab_product_id.code]
                                          for p in candidates if p.default_code and p.ab_product_id.code
                                          and p.default_code != p.ab_product_id.code]}
                matches[code] = (False, False, f"{heading} — {issues['identity']}", True)
                continue
            if len(candidates) != 1:
                product_problems[code] = {"candidates": [p.display_name for p in candidates]}
                reason = _("Code missing from store") if not candidates else _("Code matches multiple products")
                matches[code] = (False, False, f"{heading} — {reason}", True)
                continue
            product = candidates[0]
            current = product.ab_storefront_brand_id
            choices = brands[_normalized(brand_name)]
            blocked_brand = len(choices) > 1 or (choices and not choices[0].active)
            note = []
            problem = {}
            if not any(_product_name_matches(name, candidate) for candidate in (product.name, product.ab_product_id.name)):
                problem["store_name"] = product.name
                note.append(_("Store name: %s", product.name))
            if len(template_brands[product.product_tmpl_id.id]) > 1:
                problem["variant_brands"] = sorted(template_brands[product.product_tmpl_id.id])
                note.append(_("The variants have different sheet brands"))
                brand_name = False
            if blocked_brand or (current and _normalized(current.name) != _normalized(brand_name)):
                problem["brand"] = [sheet["products"][code][1], current.name or "", len(choices), bool(choices and not choices[0].active)]
                note.append(_("Existing brand needs review: %s", current.name or brand_name))
                brand_name = False
            if brand_name:
                heading += f" — {brand_name}"
            if brand_name and not note and not current:
                brand_products[brand_name].add(product.id)
                brand_summary[brand_name].append(code)
            if problem:
                product_problems[code] = problem
            matches[code] = (product, brand_name, " | ".join([heading, *note]), bool(note))

        entries = {}
        for row in sheet["offers"]:
            picked = {}
            details = []
            review = row.get("review", False)
            for code in row["codes"]:
                product, brand_name, detail, flag = matches[code]
                if "terms" in row["issues"]:
                    rates = [_offer_text(value) for value in sheet["code_offers"][code]]
                    detail = f"{detail} | {', '.join(rates)}"
                details.append(detail)
                review |= flag
                if product:
                    picked[product.id] = brand_name
            reasons = [issues[issue] for issue in row["issues"]]
            if not picked and not reasons:
                reasons.append(_("No matching store products"))
            key = row["key"]
            program = existing.get(key)
            pending = set(picked)
            already_imported = False
            if program:
                imported_ids = set(program.ab_sheet_imported_product_ids.ids)
                pending.difference_update(imported_ids)
                if imported_ids.difference(picked):
                    reasons.append(_("The existing program needs manual review"))
                elif not pending:
                    already_imported = True
                    reasons.append(_("Already imported"))
                elif not program.active or len(program.rule_ids) != 1 or len(program.reward_ids) != 1:
                    reasons.append(_("The existing program needs manual review"))
            evidence = draft_source_evidence(row, sheet, product_problems) if reasons or review else {}
            if program and not already_imported and reasons:
                evidence["existing_program"] = program.name
            state = (self.website_id.id, picked, details, reasons, review, sorted(pending), program.ab_sheet_priority if program else 0)
            fingerprint = hashlib.sha256(repr(state).encode()).hexdigest()
            entries[key] = dict(row=row, evidence=evidence, products=picked, details="\n".join(details), review=review,
                                reason=" / ".join(reasons), signature=fingerprint, existing=program, pending=pending, already_imported=already_imported)
        brand_text = "\n".join(f"{name} ({len(items)}) — {', '.join(sorted(items))}"
                               for name, items in sorted(brand_summary.items()))
        brand_signature = hashlib.sha256(repr(sorted(
            (name, sorted(ids)) for name, ids in brand_products.items()
        )).encode()).hexdigest()
        other_programs = installed.filtered(lambda program: program.active and program.ab_sheet_key not in entries)
        return entries, brands, brand_products, brand_text, brand_signature, other_programs

    def action_preview(self):
        self._check_scope()
        payload = self._uploaded_file()
        entries, _brands, _products, summary, signature, other_programs = self._snapshot(payload)
        self.write({"brand_summary": summary, "brand_signature": signature, "preview_digest": hashlib.sha256(payload).hexdigest()})
        saved = self.env["ab_storefront_offer_draft"].search([
            ("website_id", "=", self.website_id.id), ("sheet_key", "in", list(entries)),
        ])
        saved_by_key = {draft.sheet_key: draft for draft in saved}
        state_labels = dict(saved._fields["state"]._description_selection(self.env))
        commands = [Command.clear()]
        for key, entry in entries.items():
            row = entry["row"]
            start, end = row["start"], row["end"]
            overlaps = []
            for other in entries.values():
                if other is entry or entry["reason"]:
                    continue
                program = other["existing"]
                if program:
                    if not program.active:
                        continue
                    from_date = fields.Date.to_string(program.date_from) or ""
                    to_date = fields.Date.to_string(program.date_to) or "9999-12-31"
                    product_ids = program.rule_ids.product_ids.ids
                elif not other["reason"]:
                    from_date, to_date = other["row"]["start"], other["row"]["end"]
                    product_ids = other["products"]
                else:
                    continue
                if start <= to_date and end >= from_date and not entry["products"].keys().isdisjoint(product_ids):
                    overlaps.append(other["row"]["source"])
            if not entry["reason"]:
                for program in other_programs:
                    if (not program.date_from or fields.Date.to_string(program.date_from) <= end) and (
                        not program.date_to or fields.Date.to_string(program.date_to) >= start
                    ) and not entry["products"].keys().isdisjoint(program.rule_ids.product_ids.ids):
                        overlaps.append(program.name)
            status = entry["reason"]
            if key in saved_by_key:
                status = state_labels[saved_by_key[key].state]
            if entry["existing"] and not status and not entry["review"]:
                status = _("Additional matched products")
            if not status:
                status = _("Review matches") if entry["review"] else _("Ready")
            commands.append(Command.create({
                "sheet_key": key, "name": row["name"], "offer": self._offer_label(row), "source": row["source"],
                "description": row["description"], "period": f"{start} — {end}", "result": status,
                "details": entry["details"], "overlap": "\n".join(overlaps), "signature": entry["signature"],
                "available": not (key in saved_by_key or entry["reason"] or entry["review"]), "matched": len(entry["products"]),
                "priority": entry["existing"].ab_sheet_priority if entry["existing"] else 0,
            }))
        self.line_ids = commands
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
                "name": _("Add Offers from a Spreadsheet"), "view_mode": "form", "target": "new"}

    @staticmethod
    def _offer_label(row):
        if re.fullmatch(r"0\.\d+|1", row["offer"]):
            return f"{row['rate']:g}%"
        return row["offer"]

    def action_apply(self):
        self._check_scope()
        payload = self._uploaded_file()
        if not self.preview_digest or hashlib.sha256(payload).hexdigest() != self.preview_digest:
            raise UserError(_("The selection needs a new preview."))
        self.website_id.lock_for_update(allow_referencing=True)
        entries, brands, brand_products, _text, signature, _other_programs = self._snapshot(payload)
        draft_model = self.env["ab_storefront_offer_draft"]
        drafts = draft_model.search([("website_id", "=", self.website_id.id), ("sheet_key", "in", list(entries))])
        known = set(drafts.mapped("sheet_key"))
        if self.include_brands and self.brand_signature != signature and brand_products:
            raise UserError(_("The selection needs a new preview."))
        lines = {line.sheet_key: line for line in self.line_ids}
        if lines.keys() != entries.keys() or len(lines) != len(self.line_ids):
            raise UserError(_("The selection needs a new preview."))
        programs = self.env["loyalty.program"]
        assignments = defaultdict(set)
        draft_values = []
        for key, entry in entries.items():
            line = lines[key]
            existing = entry["existing"]
            if key in known or entry["already_imported"]:
                continue
            if line.signature != entry["signature"] or line.priority < 0:
                raise UserError(_("The selection needs a new preview."))
            row = entry["row"]
            if entry["reason"] or entry["review"]:
                start, end = _draft_date(row["start"]), _draft_date(row["end"])
                confirmed_ids = [] if {"identity", "codes", "scope"}.intersection(row["issues"]) else sorted(entry["products"])
                draft_values.append({
                    "website_id": self.website_id.id, "sheet_key": key, "name": row["name"] or row["source"],
                    "source": f"{self.filename or ''} · {row['source']}",
                    "review_evidence": entry["evidence"],
                    "original_terms": "\n".join(filter(None, [self._offer_label(row), row["description"], f"{row['start']} — {row['end']}"])),
                    "reason": entry["reason"] or _("Review matches"), "details": entry["details"],
                    "program_id": existing.id if existing else False,
                    "manual_only": bool(existing or {"gift", "allocation"}.intersection(row["issues"])),
                    "date_from": start, "date_to": end if not (start and end and end < start) else False,
                    "group_qty": row["bundle"], "discount_qty": row["units"],
                    "rate": 0 if "terms" in row["issues"] else row["rate"],
                    "fixed_price": 0 if "terms" in row["issues"] else row["fixed"], "priority": line.priority,
                    "product_ids": [Command.set(confirmed_ids)],
                })
                continue
            ids = sorted(entry["pending"])
            if existing:
                existing.rule_ids.write({"product_ids": [Command.link(i) for i in ids]})
                existing.reward_ids.write({"discount_product_ids": [Command.link(i) for i in ids]})
                existing.write({"ab_sheet_imported_product_ids": [Command.link(i) for i in ids],
                                "ab_sheet_priority": line.priority})
                programs |= existing
            else:
                programs |= self._create_program(row, ids, line.priority)
            for product_id, brand_name in entry["products"].items():
                if self.include_brands and product_id in entry["pending"] and brand_name:
                    assignments[brand_name].add(product_id)
        if draft_values:
            drafts |= draft_model._from_sheet(draft_values)
        if self.include_brands:
            for name, ids in brand_products.items():
                assignments[name].update(ids)
        for name, ids in assignments.items():
            templates = self.env["product.product"].browse(ids).product_tmpl_id.filtered(lambda p: not p.ab_storefront_brand_id)
            if not templates:
                continue
            templates.check_access("read")
            templates.lock_for_update(allow_referencing=True)
            choices = brands[_normalized(name)]
            brand = choices[0] if choices else self.env["ab_product_company"].with_context({}).sudo().create({
                "name": name, "ab_sheet_brand_key": _normalized(name)})
            templates.with_context({}).sudo().write({"ab_sheet_brand_id": brand.id})
        pending_drafts = drafts.filtered(lambda draft: draft.state == "draft")
        if pending_drafts:
            return {"type": "ir.actions.act_window", "res_model": draft_model._name, "view_mode": "list,form",
                    "name": _("Applied: %(applied)s · Awaiting review: %(pending)s",
                              applied=len(programs), pending=len(pending_drafts)),
                    "domain": [("id", "in", pending_drafts.ids)]}
        if not programs:
            return {"type": "ir.actions.act_window_close"}
        return {"type": "ir.actions.act_window", "res_model": "loyalty.program", "view_mode": "list,form",
                "name": _("Imported Offers"), "domain": [("id", "in", programs.ids)]}

    def _create_program(self, row, product_ids, priority):
        name = f"{row['name']} · {self._offer_label(row)}"
        program_model = self.env["loyalty.program"]
        rule = {
            "mode": "auto", "minimum_qty": row["bundle"], "minimum_amount": 0,
            "reward_point_mode": "order", "reward_point_amount": 1,
            "product_ids": [Command.set(product_ids)],
        }
        reward = {
            "reward_type": "discount", "discount_mode": "percent", "description": name,
            "discount_applicability": "cheapest", "discount": row["rate"], "required_points": 1,
            "discount_product_ids": [Command.set(product_ids)],
        }
        values = {
            "name": name, "program_type": "promotion", "company_id": self.env.company.id,
            "website_id": self.website_id.id, "sale_ok": False, "ecommerce_ok": True,
            "portal_visible": False, "trigger": "auto", "applies_on": "current",
            "date_from": row["start"], "date_to": row["end"], "ab_sheet_key": row["key"],
            "ab_sheet_group_qty": row["bundle"], "ab_sheet_discount_qty": row["units"],
            "ab_sheet_priority": priority, "ab_sheet_fixed_price": row["fixed"],
            "ab_sheet_imported_product_ids": [Command.set(product_ids)],
            "rule_ids": [Command.create(rule)], "reward_ids": [Command.create(reward)],
            "communication_plan_ids": [],
        }
        if "pos_ok" in program_model._fields:
            values["pos_ok"] = False
        program_model.check_access("create")
        factory = program_model.with_context(
            {}, lang=self.env.lang, allowed_company_ids=[self.env.company.id],
        ).sudo()
        return program_model.browse(factory.create(values).id)


class OfferSheetLine(models.TransientModel):
    _name = "ab_storefront_offer_sheet_line"
    _description = "Offer Sheet Preview Line"

    wizard_id = fields.Many2one("ab_storefront_offer_sheet", required=True, ondelete="cascade")
    sheet_key = fields.Char(readonly=True)
    name = fields.Char(readonly=True)
    offer = fields.Char(readonly=True)
    source = fields.Char(readonly=True)
    period = fields.Char(readonly=True)
    description = fields.Text(readonly=True)
    details = fields.Text(string="Product Codes and Brands", readonly=True)
    result = fields.Char(readonly=True)
    matched = fields.Integer(readonly=True)
    overlap = fields.Text(string="Overlapping Sheet Rows", readonly=True)
    signature = fields.Char(readonly=True)
    available = fields.Boolean(readonly=True)
    priority = fields.Integer(help="Zero chooses the best saving. A higher priority takes precedence for overlapping items.")
