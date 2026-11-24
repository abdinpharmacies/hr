import base64
from datetime import date
from io import BytesIO
from unittest.mock import patch

from openpyxl import Workbook

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase, new_test_user

from ..wizard import offer_sheet
from ..wizard.offer_sheet import _november_offers, _product_name_matches
from ..wizard.offer_workbook import parse_offer_workbook


@tagged("post_install", "-at_install")
class TestOfferSheetImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref("website.default_website")
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.website.company_id.id)], limit=1)
        cls.website.warehouse_id = cls.warehouse
        cls.manager = new_test_user(cls.env, login="sheet_manager", groups="sales_team.group_sale_manager")
        cls.staff = new_test_user(cls.env, login="sheet_staff", groups="sales_team.group_sale_salesman")
        cls.wizards = cls.env["ab_storefront_offer_sheet"].with_user(cls.manager)
        cls.file_data = cls.make_workbook("Alejon", "1+1")
        cls.sheet = parse_offer_workbook(base64.b64decode(cls.file_data), _november_offers())
        cls.row = cls.sheet["offers"][0]
        cls.code = cls.row["codes"][0]

    @staticmethod
    def make_workbook(company, offer):
        workbook = Workbook()
        schedule = workbook.active
        schedule.append(["Company", "Offer", "Description", "From", "To"])
        schedule.append([company, offer, "", date(2026, 11, 1), date(2026, 11, 30)])
        codes = workbook.create_sheet("Offer Codes")
        codes.append(["00035", "Serum 50 ML", offer, company])
        codes.append(["00036", "Cream 30 GM", offer, company])
        data = BytesIO()
        workbook.save(data)
        return base64.b64encode(data.getvalue())

    def test_upload_changes_contents_and_requires_new_preview(self):
        wizard, _line = self.preview()
        wizard.write({"workbook": self.make_workbook("Different brand", "2+1")})
        with self.assertRaises(UserError):
            wizard.action_apply()
        wizard.action_preview()
        self.assertEqual(wizard.line_ids.name, "Different brand")
        self.assertEqual(wizard.line_ids.offer, "2+1")
        wizard.workbook = base64.b64encode(b"invalid Excel data")
        with self.assertRaises(UserError):
            wizard.action_preview()

    def product(self, code, quantity=5):
        product = self.env["product.product"].create({
            "default_code": code, "name": self.sheet["products"][code][0], "list_price": 100,
            "website_id": self.website.id, "is_storable": True, "is_published": False,
        })
        if quantity:
            self.env["stock.quant"].with_context(inventory_mode=True).create({
                "product_id": product.id, "location_id": self.warehouse.lot_stock_id.id,
                "inventory_quantity": quantity,
            }).action_apply_inventory()
        return product

    def test_stock_and_publication_on_import_and_retry(self):
        first, second = self.product(self.code), self.product(self.row["codes"][1], quantity=0)
        first.product_tmpl_id.website_id = False
        row = dict(self.row, start="2020-01-01", end="2099-01-01", review=False)
        with patch.object(offer_sheet, "parse_offer_workbook", return_value=dict(self.sheet, offers=[row])):
            wizard, line = self.preview()
            self.assertFalse(line.available)
            self.assertIn(second.default_code, line.details)
            result = wizard.action_apply()
            draft = self.env[result["res_model"]].with_user(self.manager).search(result["domain"])
            with self.assertRaises(UserError):
                draft.action_apply()
            self.assertFalse(first.is_published)
            self.assertFalse(second.is_published)
            draft.product_ids = first
            draft.action_apply()
            self.assertTrue(first.is_published)
            self.assertEqual(first.website_id, self.website)
            self.assertFalse(second.is_published)
            first.product_tmpl_id.is_published = False
            row["codes"] = [self.code]
            self.preview()[0].action_apply()
            self.assertTrue(first.is_published)
            self.assertFalse(second.is_published)
            self.assertEqual(draft.program_id.rule_ids.product_ids, first)

    def test_reimport_suspends_whole_program_and_restores_same_rules(self):
        first, second = [self.product(code) for code in self.row["codes"]]
        row = dict(self.row, start="2020-01-01", end="2099-01-01", review=False)
        with patch.object(offer_sheet, "parse_offer_workbook", return_value=dict(self.sheet, offers=[row])):
            self.preview()[0].action_apply()
            program = self.env["loyalty.program"].with_context(active_test=False).search([("ab_sheet_key", "=", row["key"])])
            rules, rewards = program.rule_ids, program.reward_ids
            first.product_tmpl_id.is_published = False
            stale, _line = self.preview()
            quant = self.env["stock.quant"].with_context(inventory_mode=True).search([
                ("product_id", "=", second.id), ("location_id", "=", self.warehouse.lot_stock_id.id),
            ])
            quant.inventory_quantity = 0
            quant.action_apply_inventory()
            with self.assertRaises(UserError):
                stale.action_apply()
            self.assertTrue(program.active)
            unrelated = self.env["product.product"].create({"name": "Unrelated service", "type": "service"})
            service = rewards.discount_line_product_id
            rewards.discount_line_product_id = unrelated
            with self.assertRaises(UserError):
                self.preview()[0].action_apply()
            self.assertTrue(unrelated.active)
            self.assertTrue(program.active)
            rewards.discount_line_product_id = service
            result = self.preview()[0].action_apply()
            self.assertFalse(program.active)
            self.assertFalse(first.is_published)
            drafts = self.env[result["res_model"]].with_user(self.manager)
            draft = drafts.search(result["domain"])
            self.assertTrue(draft.stock_review)
            self.assertEqual(draft.program_id, program)
            self.assertEqual(draft.product_ids, first | second)
            self.preview()[0].action_apply()
            self.assertEqual(drafts.search_count([("program_id", "=", program.id), ("stock_review", "=", True)]), 1)
            with self.assertRaises(UserError):
                draft.action_apply()
            with self.assertRaises(AccessError):
                draft.write({"product_ids": [Command.set(first.ids)]})
            self.assertFalse(program.active)
            self.env["stock.quant"].with_context(inventory_mode=True).create({
                "product_id": second.id, "location_id": self.warehouse.lot_stock_id.id,
                "inventory_quantity": 5,
            }).action_apply_inventory()
            self.preview()[0].action_apply()
            self.assertFalse(program.active)
            draft.action_apply()
            self.assertTrue(program.active)
            self.assertTrue(first.is_published)
            self.assertEqual(draft.state, "applied")
            self.assertEqual(program.rule_ids, rules)
            self.assertEqual(program.reward_ids, rewards)
            rules.product_ids = first
            rewards.discount_product_ids = first
            second.product_tmpl_id.is_published = False
            self.preview()[0].action_apply()
            self.assertFalse(second.is_published)
            self.assertEqual(program.rule_ids.product_ids, first)
            program.active = False
            self.preview()[0].action_apply()
            self.assertFalse(program.active)

    def test_stock_loss_after_preview_preserves_publication(self):
        product = self.product(self.code)
        row = dict(self.row, codes=[self.code], review=False)
        with patch.object(offer_sheet, "parse_offer_workbook", return_value=dict(self.sheet, offers=[row])):
            wizard, line = self.preview()
            self.assertTrue(line.available)
            quant = self.env["stock.quant"].with_context(inventory_mode=True).search([
                ("product_id", "=", product.id), ("location_id", "=", self.warehouse.lot_stock_id.id),
            ])
            quant.inventory_quantity = 0
            quant.action_apply_inventory()
            with self.assertRaises(UserError):
                wizard.action_apply()
            self.assertFalse(product.is_published)
            self.assertFalse(self.env["loyalty.program"].search([("ab_sheet_key", "=", row["key"])]))

    def test_single_product_bundle_needs_enough_stock(self):
        self.product(self.code, quantity=1)
        row = dict(self.row, codes=[self.code], review=False)
        with patch.object(offer_sheet, "parse_offer_workbook", return_value=dict(self.sheet, offers=[row])):
            wizard, line = self.preview()
            self.assertFalse(line.available)
            self.assertIn("group size", line.result)
            self.assertEqual(wizard.action_apply()["res_model"], "ab_storefront_offer_draft")

    def preview(self):
        wizard = self.wizards.create({"workbook": self.file_data, "filename": "offers.xlsx"})
        wizard.action_preview()
        return wizard, wizard.line_ids.filtered(lambda line: line.sheet_key == self.row["key"])

    def test_bulk_apply_ready_and_save_uncertain(self):
        first, second = [self.product(code) for code in self.row["codes"]]
        reviewed = dict(self.row, review=False, codes=[self.code])
        uncertain = dict(self.row, key="missing-dates", issues=["dates"], start="", end="")
        sheet = dict(self.sheet, offers=[reviewed, uncertain])
        with patch.object(offer_sheet, "parse_offer_workbook", return_value=sheet):
            wizard, line = self.preview()
            wizard.include_brands = True
            line.priority = 5
            self.assertTrue(line.available)
            self.assertFalse(self.env["ab_storefront_offer_draft"].search([]))
            wizard.action_apply()
            programs = self.env["loyalty.program"].search([("ab_sheet_key", "=", self.row["key"])])
            self.assertEqual(programs.rule_ids.product_ids, first)
            self.assertEqual(programs.reward_ids.discount_product_ids, first)
            self.assertEqual(programs.ab_sheet_priority, 5)
            self.assertEqual(first.ab_storefront_brand_id.name.lower(), "alejon")
            draft = self.env["ab_storefront_offer_draft"].search([("sheet_key", "=", "missing-dates")])
            self.assertEqual(draft.state, "draft")
            self.assertEqual(draft.product_ids, first | second)
            draft.write({"note": "Keep the correction"})
            wizard.action_apply()
            reviewed["codes"] = self.row["codes"]
            other, line = self.preview()
            self.assertTrue(line.available)
            other.action_apply()
            self.assertEqual(programs.rule_ids.product_ids, first | second)
            self.assertEqual(programs.ab_sheet_priority, 5)
            self.assertEqual(draft.note, "Keep the correction")
            self.assertEqual(self.env["ab_storefront_offer_draft"].search_count([("sheet_key", "=", "missing-dates")]), 1)

    def test_draft_employee_correction_and_manager_approval(self):
        product = self.product(self.code)
        wizard, line = self.preview()
        self.assertFalse(line.available)
        result = wizard.action_apply()
        self.assertEqual(result["res_model"], "ab_storefront_offer_draft")
        draft = self.env[result["res_model"]].search(result["domain"])
        reviewer = new_test_user(self.env, login="draft_reviewer",
                                 groups="base.group_user,ab_ecommerce_storefront.group_offer_draft_reviewer")
        self.assertIn(self.env.ref("ab_ecommerce_storefront.menu_offer_drafts").id,
                      self.env["ir.ui.menu"].with_user(reviewer)._visible_menu_ids())
        with self.assertRaises(AccessError):
            draft.with_user(self.staff).read(["name"])
        editable = draft.with_user(reviewer)
        editable.write({"rate": 20, "group_qty": 1, "discount_qty": 1,
                        "product_ids": [Command.set(product.ids)], "note": "Confirmed"})
        with self.assertRaises(AccessError):
            editable.action_apply()
        with self.assertRaises(AccessError):
            editable.write({"state": "applied"})
        with self.assertRaises(ValidationError):
            editable.write({"product_ids": [Command.delete(product.id)]})
        other_website = self.website.copy({"name": "Other shop"})
        other_product = self.env["product.product"].create({"name": "Other item", "website_id": other_website.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            editable.write({"product_ids": [Command.link(other_product.id)]})
        other_company = self.env["res.company"].create({"name": "Other draft company"})
        other_manager = new_test_user(self.env, login="other_draft_manager", groups="sales_team.group_sale_manager",
                                      company_id=other_company.id, company_ids=[Command.set(other_company.ids)])
        with self.assertRaises(AccessError):
            draft.with_user(other_manager).read(["name"])
        manager_draft = draft.with_user(self.manager)
        manager_draft.date_to = False
        with self.assertRaises(UserError):
            manager_draft.action_apply()
        manager_draft.date_to = date(2026, 11, 30)
        manager_draft.action_apply()
        manager_draft.action_apply()
        self.assertEqual(draft.state, "applied")
        self.assertEqual(draft.program_id.rule_ids.product_ids, product)
        self.assertEqual(draft.program_id.reward_ids.discount, 20)
        self.assertEqual(draft.program_id.website_id, self.website)
        with self.assertRaises(AccessError):
            editable.write({"rate": 80})
        self.preview()[0].action_apply()
        self.assertEqual(self.env["loyalty.program"].search_count([("ab_sheet_key", "=", self.row["key"])]), 1)

    def test_ambiguous_terms_and_identity_require_correction(self):
        product = self.product(self.code)
        sheet = dict(self.sheet, offers=[dict(self.row, issues=["terms", "identity"])])
        with patch.object(offer_sheet, "parse_offer_workbook", return_value=sheet):
            wizard, _line = self.preview()
            wizard.include_brands = False
            result = wizard.action_apply()
            draft = self.env[result["res_model"]].with_user(self.manager).search(result["domain"])
            self.assertFalse(draft.product_ids)
            self.assertFalse(draft.rate)
            self.assertIn(self.code, draft.details)
            with self.assertRaises(UserError):
                draft.action_apply()
            draft.product_ids = product
            with self.assertRaises(UserError):
                draft.action_apply()
            draft.rate = 25
            draft.with_context(lang="en_US").action_apply()
            self.assertEqual(draft.program_id.reward_ids.discount, 25)
            self.assertIn("25% on 1 of every 2 units", draft.program_id.with_context(lang="en_US").name)

    def test_gift_stays_in_review(self):
        self.product(self.code)
        sheet = dict(self.sheet, offers=[dict(self.row, issues=["gift"])])
        with patch.object(offer_sheet, "parse_offer_workbook", return_value=sheet):
            wizard, line = self.preview()
            result = wizard.action_apply()
            draft = self.env[result["res_model"]].with_user(self.manager).search(result["domain"])
            self.assertTrue(draft.manual_only)
            with self.assertRaises(UserError):
                draft.action_apply()
            draft.action_set_aside()
            wizard.action_apply()
            self.assertEqual(draft.state, "skipped")
            self.assertFalse(self.env["loyalty.program"].search([("ab_sheet_key", "=", self.row["key"])]))

    def test_publish_gift_draft_as_storefront_offer(self):
        paid = self.product(self.code)
        gift = self.product(self.row["codes"][1], quantity=0)
        model = self.env["ab_storefront_offer_draft"]
        draft = model._from_sheet({
            "name": "Separate gift", "sheet_key": "gift-test", "website_id": self.website.id,
            "manual_only": True, "review_evidence": {"issues": ["gift"]},
            "product_ids": [Command.set((paid | gift).ids)],
            "date_from": date(2020, 1, 1), "date_to": date(2099, 1, 1),
        }).with_user(self.manager)
        action = draft.action_prepare_storefront_offer()
        offers = self.env[action["res_model"]].with_user(self.manager).with_context(**action["context"])
        vals = {"product_id": paid.id, "second_product_ids": [Command.set(gift.ids)]}
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            offers.with_user(self.staff).create(vals)
        with self.assertRaisesRegex(UserError, "No available stock"), self.env.cr.savepoint():
            offers.create(vals)
        self.assertFalse(paid.is_published)
        self.assertFalse(gift.is_published)
        self.assertEqual(draft.state, "draft")
        self.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": gift.id, "location_id": self.warehouse.lot_stock_id.id, "inventory_quantity": 1,
        }).action_apply_inventory()
        published = offers.create(vals)
        self.assertEqual(draft.storefront_offer_id, published)
        self.assertEqual(draft.state, "applied")
        self.assertTrue(paid.is_published and gift.is_published)
        self.assertTrue(published.generated_program_ids.active)
        overview = self.env["ab_storefront_offer_overview"].search([("name", "=", "Separate gift")])
        self.assertEqual(overview.source, "manual")
        with self.assertRaisesRegex(UserError, "pending draft"), self.env.cr.savepoint():
            offers.create(vals)

    def test_publish_draft_budget_and_group(self):
        paid, extra = [self.product(code) for code in self.row["codes"]]
        vals = {"name": "Group", "sheet_key": "group-test", "website_id": self.website.id,
                "product_ids": [Command.set((paid | extra).ids)], "rate": 37,
                "date_from": date(2020, 1, 1), "date_to": date(2099, 1, 1)}
        model = self.env["ab_storefront_offer_draft"]
        budget = model._from_sheet(dict(vals, sheet_key="budget-test", review_evidence={"issues": ["allocation"]}))
        with self.assertRaisesRegex(UserError, "allocation"):
            budget.with_user(self.manager).action_prepare_storefront_offer()
        draft = model._from_sheet(vals).with_user(self.manager)
        action = draft.action_prepare_storefront_offer()
        offers = self.env[action["res_model"]].with_user(self.manager).with_context(**action["context"])
        with self.assertRaisesRegex(UserError, "all confirmed"), self.env.cr.savepoint():
            offers.create({"second_product_ids": [Command.clear()]})
        offer = Form(offers, view=action["views"][0][0]).save()
        self.assertEqual(offer._qualifying_products(), paid | extra)
        self.assertEqual(offer.generated_program_ids.reward_ids.discount, 37)
        self.assertTrue(paid.is_published and extra.is_published)
        self.assertEqual(draft.storefront_offer_id, offer)

    def test_publish_other_storefront_types_from_draft(self):
        main, other = [self.product(code) for code in self.row["codes"]]
        pricelist = self.env["product.pricelist"].create({
            "name": "Draft prices", "website_id": self.website.id, "company_id": self.website.company_id.id,
            "currency_id": self.env.ref("base.EGP").id,
        })
        for kind, terms in [
            ("second_half", {"second_item_mode": "same"}),
            ("mix_discount", {"collection_product_line_ids": [Command.create({"product_id": other.id})]}),
            ("percent", {"pricelist_id": pricelist.id, "percentage_rate": "30"}),
            ("amount", {"pricelist_id": pricelist.id, "amount_discount": "custom", "custom_amount_discount": 5}),
            ("price", {"pricelist_id": pricelist.id, "price_before": 100, "price_after": 90}),
        ]:
            with self.subTest(kind=kind):
                draft = self.env["ab_storefront_offer_draft"]._from_sheet({
                    "name": kind, "sheet_key": kind, "website_id": self.website.id,
                    "product_ids": [Command.set(main.ids)], "date_from": date(2020, 1, 1), "date_to": date(2099, 1, 1),
                }).with_user(self.manager)
                action = draft.action_prepare_storefront_offer()
                offer = self.env[action["res_model"]].with_user(self.manager).with_context(**action["context"]).create(
                    dict(terms, offer_type=kind)
                )
                self.assertEqual(draft.storefront_offer_id, offer)
                self.assertTrue(offer.generated_program_ids or offer.price_rule_ids)
                self.assertTrue(main.is_published)
                offer.active = False

    def test_details_name_only_the_affected_codes_and_dates(self):
        self.product(self.code)
        row = dict(self.row, issues=["dates"], start="", end="not a date")
        with patch.object(offer_sheet, "parse_offer_workbook", return_value=dict(self.sheet, offers=[row])):
            wizard, _line = self.preview()
            result = wizard.action_apply()
            draft = self.env[result["res_model"]].search(result["domain"])
        english = draft.with_context(lang="en_US").review_explanation
        self.assertIn("The From cell is empty", english)
        self.assertIn("end date in To could not be read: not a date", english)
        self.assertIn("00036 · Cream 30 GM", english)
        self.assertNotIn("00035", english)
        for start, end, expected in [
            ("2026-11-15", "", "The To cell is empty"),
            ("invalid", "2026-11-30", "start date in From could not be read: invalid"),
            ("2026-11-15", "1900-01-21", "end date 1900-01-21 is before the start date 2026-11-15"),
        ]:
            lines = draft.with_context(lang="en_US")._explain_evidence(dict(draft.review_evidence, start=start, end=end))
            self.assertIn(expected, "\n".join(lines))

    def test_saved_review_reason_uses_reader_language(self):
        self.env["res.lang"]._activate_lang("ar_001")
        draft = self.env["ab_storefront_offer_draft"].new({
            "reason": "Review matches / No available stock for: [123] Serum",
            "review_evidence": {"issues": [], "products": {}, "offer": "",
                                "stock_issue": "No available stock for: [123] Serum"},
        })
        arabic = draft.with_context(lang="ar_001")
        english = draft.with_context(lang="en_US")
        self.assertNotIn("Review matches", arabic.display_reason)
        self.assertNotIn("No available stock", arabic.display_reason)
        self.assertIn("[123] Serum", arabic.display_reason)
        self.assertIn(arabic.review_explanation, arabic.display_reason)
        self.assertEqual(english.display_reason, draft.reason)
        draft.reason = arabic.display_reason
        self.assertEqual(english.display_reason, "Review matches / No available stock for: [123] Serum")

    def test_filter_by_localized_review_reason(self):
        self.env["res.lang"]._activate_lang("ar_001")
        model = self.env["ab_storefront_offer_draft"].with_user(self.manager)
        drafts = model._from_sheet([
            {"name": reason, "reason": reason, "sheet_key": f"reason-filter-{index}",
             "website_id": self.website.id}
            for index, reason in enumerate((
                "Review matches", "Review matches", "Review matches / Missing or invalid dates",
                "No available stock for: [123] Serum",
            ))
        ])
        arabic = model.with_context(lang="ar_001")
        label = drafts[0].with_context(lang="ar_001").display_reason
        self.assertNotEqual(label, "Review matches")
        scope = [("id", "in", drafts.ids)]
        for operator, query, expected in (
            ("ilike", label.split()[0], drafts[:3]),
            ("=", label, drafts[:2]),
            ("not ilike", label, drafts[3:]),
            ("ilike", "[123] serum", drafts[3:]),
        ):
            self.assertEqual(arabic.search(scope + [("display_reason", operator, query)]).ids, expected.ids)
        self.assertEqual(model.with_context(lang="en_US").search(
            scope + [("display_reason", "ilike", "missing or invalid")]
        ).ids, drafts[2:3].ids)

    def test_glovive_saved_draft_uses_reference_and_saved_match_notes(self):
        ref = _november_offers()
        row = next(r for r in ref["offers"] if r["name"] == "Glovive" and r["source"] == "white friday #25")
        details = [f"{code}  {ref['products'][code][0]}" for code in row["codes"]]
        details[1] += " | Store name: GLOVIVE EYE CONTOUR GEL 30 ML 1 BOX"
        draft = self.env["ab_storefront_offer_draft"].new({
            "sheet_key": row["key"], "source": row["source"], "reason": "Conflicting product identity",
            "original_terms": "\n".join([row["offer"], row["description"], f"{row['start']} — {row['end']}"]),
            "details": "\n".join(details),
        })
        result = draft.with_context(lang="en_US").review_explanation
        for value in ("115474", "115475", "115476", "G-Doux", "GLOVIVE", "60 M (G-Doux)", "60 ML (GLOVIVE)",
                      "105709", "November reference"):
            self.assertIn(value, result)
        self.assertNotIn("105708", result)
        self.assertNotIn("date", result)
        draft.details = "00036  Cream 30 GM — Code missing from store"
        actual = draft.with_context(lang="en_US").review_explanation
        self.assertNotIn("115475", actual)
        self.assertIn("00036", actual)

    def test_uploaded_conflicting_identities_preserve_both_names(self):
        workbook = Workbook()
        schedule = workbook.active
        schedule.append(["Company", "Offer", "Description", "From", "To"])
        schedule.append(["First", "25%", "35%", date(2026, 11, 1), date(2026, 11, 30)])
        tab = workbook.create_sheet("Offer Codes")
        tab.append(["001", "First Item 30 ML", "25%", "First"])
        tab.append(["001", "Another Item 50 ML", "35%", "Other group"])
        buffer = BytesIO()
        workbook.save(buffer)
        wizard = self.wizards.create({"workbook": base64.b64encode(buffer.getvalue())})
        wizard.action_preview()
        result = wizard.action_apply()
        draft = self.env[result["res_model"]].search(result["domain"]).with_context(lang="en_US")
        for value in ("001", "First Item 30 ML (First)", "Another Item 50 ML (Other group)", "25%", "35%"):
            self.assertIn(value, draft.review_explanation)
        self.assertFalse(draft.program_id)

    def test_name_matching_preserves_strength_and_pack(self):
        self.assertTrue(_product_name_matches("SERUM 50ML", "Serum 50 ml 1 BOX, 1 UNIT"))
        self.assertFalse(_product_name_matches("SERUM 10.5 MG", "SERUM 105 MG 1 BOX"))
        self.assertFalse(_product_name_matches("SERUM 50 ML", "SERUM 50 ML 2 BOX"))
        self.assertFalse(_product_name_matches("SERUM 50 ML", "SERUM 150 ML 1 BOX"))

    def test_brand_without_promotion(self):
        product = self.product(self.code)
        wizard, _line = self.preview()
        self.assertIn(self.code, wizard.brand_summary)
        wizard.include_brands = True
        wizard.action_apply()
        self.assertEqual(product.ab_storefront_brand_id.name.lower(), "alejon")
        self.assertFalse(self.env["loyalty.program"].search([("ab_sheet_key", "=", self.row["key"])]))

    def test_offer_import_does_not_link_brands_when_disabled(self):
        product = self.product(self.code)
        row = dict(self.row, review=False, codes=[self.code])
        with patch.object(offer_sheet, "parse_offer_workbook", return_value=dict(self.sheet, offers=[row])):
            wizard, _line = self.preview()
            self.assertFalse(wizard.include_brands)
            wizard.action_apply()
        self.assertTrue(self.env["loyalty.program"].search([("ab_sheet_key", "=", row["key"])]))
        self.assertFalse(product.ab_storefront_brand_id)

    def test_discount_list_entry_and_company_boundary(self):
        sheet_view = self.env.ref("ab_ecommerce_storefront.discount_program_sheet_list")
        discount_list = self.env.ref("loyalty.action_loyalty_program_tree_discount_loyalty")
        self.assertEqual(discount_list.view_id, sheet_view)
        arch = self.env["loyalty.program"].with_user(self.manager).get_view(sheet_view.id, "list")["arch"]
        overview = self.env["ab_storefront_offer_overview"].with_user(self.manager)
        view = self.env.ref("ab_ecommerce_storefront.offer_overview_list")
        drafts = self.env.ref("ab_ecommerce_storefront.action_offer_drafts")
        self.assertIn(f'name="{drafts.id}"', overview.get_view(view.id, "list")["arch"])
        self.assertIn('display="always"', arch)
        form = self.env.ref("ab_ecommerce_storefront.offer_sheet_form")
        upload_arch = self.wizards.get_view(form.id, "form")["arch"]
        self.assertNotIn('name="website_id"', upload_arch)
        self.assertIn('name="workbook"', upload_arch)
        website = self.website.copy({"name": "Other company shop", "company_id": self.env["res.company"].create({
            "name": "Other sheet company",
        }).id})
        with self.assertRaises(AccessError):
            self.wizards.create({"website_id": website.id, "workbook": self.file_data}).action_preview()

    def test_stale_preview_and_access(self):
        self.product(self.code)
        wizard, line = self.preview()
        self.product(self.row["codes"][1])
        with self.assertRaises(UserError):
            wizard.action_apply()
        with self.assertRaises(AccessError):
            wizard.with_user(self.staff).action_apply()
        with self.assertRaises(AccessError):
            self.wizards.with_user(self.staff).create({"website_id": self.website.id, "workbook": self.file_data, "filename": "offers.xlsx"})
