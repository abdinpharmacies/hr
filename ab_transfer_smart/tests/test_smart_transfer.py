# -*- coding: utf-8 -*-
import io
import zipfile

import xlsxwriter

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.ab_transfer_smart.models.ab_transfer_header import (
    SMART_EXPORT_COMPANY_NAME,
    SMART_STAGE_PURCHASE_PREPARATION,
    SMART_STAGE_PRE_SUBMIT,
    SMART_STAGE_SUBMIT,
    SMART_STAGE_STORE_PREPARATION,
    SMART_STAGE_STORE_REVISION,
    SMART_LINE_SOURCE_DOMAIN,
    SMART_LINE_SOURCE_WIZARD,
    SMART_ROW_BRANCH_STOCK_QTY,
    SMART_ROW_LAST_MONTH_SALES,
    SMART_ROW_PREVIOUS_MONTH_SALES,
    SMART_ROW_PRODUCT_SERIAL,
    SMART_ROW_THIRD_MONTH_SALES,
    SMART_ROW_TOTAL_3_MONTHS_SALES,
    SMART_STOCK_METHOD_NORMAL,
    SMART_STOCK_METHOD_WEIGHTED,
)


class TestSmartTransfer(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env.user.write({
            "group_ids": [
                (4, self.env.ref("ab_transfer_smart.group_transfer_smart_purchase").id),
                (4, self.env.ref("ab_transfer_smart.group_trnasfer_smart_store_preparation").id),
                (4, self.env.ref("ab_transfer_smart.group_trnasfer_smart_store_revision").id),
            ],
        })

    def _create_store_or_skip(self, vals):
        try:
            return self.env["ab_store"].create(vals)
        except ValidationError as error:
            if "Replication Database" in str(error):
                self.skipTest("Replica database blocks creating ab_store test records.")
            raise

    def _create_smart_uom(self):
        category = self.env["ab_product_uom_category"].create({
            "name": "Smart Transfer Test UOM",
            "active": True,
        })
        return self.env["ab_product_uom"].create({
            "name": "Smart Unit",
            "category_id": category.id,
            "factor": 1.0,
        })

    def _create_smart_product(self, code, eplus_serial, uom, location=None):
        card = self.env["ab_product_card"].create({
            "name": code,
        })
        vals = {
            "product_card_id": card.id,
            "code": code,
            "uom_category_id": uom.category_id.id,
            "uom_id": uom.id,
            "eplus_serial": eplus_serial,
        }
        if location is not None:
            vals["location"] = location
        return self.env["ab_product"].create(vals)

    def _create_smart_header(self):
        source = self._create_store_or_skip({
            "name": "Smart Copy Source",
            "code": "SMART-COPY-SRC",
            "eplus_serial": 8101,
            "allow_sale": True,
        })
        destination = self._create_store_or_skip({
            "name": "Smart Copy Destination",
            "code": "SMART-COPY-DST",
            "eplus_serial": 8102,
            "allow_sale": True,
        })
        user = self.env["ab_costcenter"].create({
            "name": "Smart Transfer User",
            "code": "SMARTUSR",
            "eplus_serial": 9101,
        })
        return self.env["ab_transfer_header"].create({
            "from_store_id": source.id,
            "to_store_id": destination.id,
            "user_id": user.id,
        })

    def _create_smart_header_for_source(
            self,
            source_header,
            destination_code,
            destination_serial,
    ):
        destination = self._create_store_or_skip({
            "name": destination_code,
            "code": destination_code,
            "eplus_serial": destination_serial,
            "allow_sale": True,
        })
        return self.env["ab_transfer_header"].create({
            "from_store_id": source_header.from_store_id.id,
            "to_store_id": destination.id,
            "user_id": source_header.user_id.id,
        })

    def _create_smart_header_from_existing_records_or_skip(self):
        Header = self.env["ab_transfer_header"]
        Store = self.env["ab_store"].sudo()
        source_domain = [("allow_sale", "=", True)]
        allowed_store_ids = Header._get_allowed_source_store_ids()
        if allowed_store_ids:
            source_domain.append(("id", "in", allowed_store_ids))
        source = Store.search(source_domain, limit=1)
        if not source:
            self.skipTest("No allowed source store is available for smart archive tests.")

        destination = Store.search([
            ("id", "!=", source.id),
            ("allow_sale", "=", True),
        ], limit=1)
        if not destination:
            self.skipTest("No destination store is available for smart archive tests.")

        user = self.env["ab_costcenter"].sudo().search([], limit=1)
        if not user:
            self.skipTest("No costcenter is available for smart archive tests.")

        return Header.create({
            "from_store_id": source.id,
            "to_store_id": destination.id,
            "user_id": user.id,
        })

    def _create_smart_security_user(self, login, group_xmlids):
        group_ids = [self.env.ref("base.group_user").id]
        group_ids.extend(self.env.ref(xmlid).id for xmlid in group_xmlids)
        return self.env["res.users"].sudo().with_context(no_reset_password=True).create({
            "name": login.replace("_", " ").title(),
            "login": login,
            "email": "%s@example.com" % login,
            "group_ids": [(6, 0, group_ids)],
        })

    def _create_smart_wizard_for_security(self, user=None):
        header = self._create_smart_header_from_existing_records_or_skip()
        Wizard = self.env["ab_transfer_smart_wizard"]
        if user:
            Wizard = Wizard.with_user(user)
        return Wizard.create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "company_id": header.company_id.id,
        })

    def _get_existing_smart_products_or_skip(self, count):
        products = self.env["ab_product"].sudo().search([
            ("uom_id", "!=", False),
        ], limit=count)
        if len(products) < count:
            self.skipTest("Not enough existing products are available for smart transfer tests.")
        return products

    def _get_existing_smart_product_with_serial_or_skip(self):
        product = self.env["ab_product"].sudo().search([
            ("uom_id", "!=", False),
            ("eplus_serial", "not in", [False, 0]),
        ], limit=1)
        if not product:
            self.skipTest("No existing product with UOM and EPlus serial is available.")
        return product

    def _create_smart_line(self, header, product, uom, **extra_vals):
        extra_vals.pop("class_id", None)
        vals = {
            "header_id": header.id,
            "product_id": product.id,
            "qty": extra_vals.pop("qty", 5),
            "expiry_date": extra_vals.pop("expiry_date", fields.Date.today()),
            "uom_id": uom.id,
        }
        vals.update(extra_vals)
        return self.env["ab_transfer_smart_line"].create(vals)

    def _smart_source_row(self, source_id, qty, exp_date=None):
        return {
            "source_id": source_id,
            "qty": qty,
            "exp_date": exp_date or fields.Date.today(),
        }

    def _create_smart_archive_wizard(self, smart_stage=SMART_STAGE_PURCHASE_PREPARATION):
        header = self._create_smart_header_from_existing_records_or_skip()
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "state": "done",
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "company_id": header.company_id.id,
        })
        header.write({
            "smart_wizard_id": wizard.id,
            "smart_stage": smart_stage,
        })
        return wizard, header

    def _create_generated_header_for_archive_wizard(
            self,
            wizard,
            template_header,
            smart_stage=SMART_STAGE_PURCHASE_PREPARATION,
    ):
        return self.env["ab_transfer_header"].create({
            "from_store_id": template_header.from_store_id.id,
            "to_store_id": template_header.to_store_id.id,
            "user_id": template_header.user_id.id,
            "company_id": template_header.company_id.id,
            "smart_wizard_id": wizard.id,
            "smart_stage": smart_stage,
        })

    def test_weighted_method_is_default(self):
        defaults = self.env["ab_transfer_header"].default_get(["smart_stock_method"])

        self.assertEqual(defaults["smart_stock_method"], SMART_STOCK_METHOD_WEIGHTED)

    def test_smart_wizard_source_defaults_match_transfer_header(self):
        Wizard = self.env["ab_transfer_smart_wizard"]
        Header = self.env["ab_transfer_header"]

        wizard_defaults = Wizard.default_get(["from_store_id", "user_id", "company_id"])
        header_defaults = Header.default_get(["from_store_id", "user_id", "company_id"])

        self.assertEqual(
            Wizard._get_allowed_source_store_domain(),
            Header._get_allowed_source_store_domain(),
        )
        self.assertEqual(wizard_defaults.get("from_store_id"), header_defaults.get("from_store_id"))
        self.assertEqual(wizard_defaults.get("user_id"), header_defaults.get("user_id"))
        self.assertEqual(wizard_defaults.get("company_id"), header_defaults.get("company_id"))

    def test_smart_wizard_form_user_is_unconditionally_readonly(self):
        view_xml = (
            Path(__file__).resolve().parents[1]
            / "views"
            / "ab_transfer_smart_wizard_views.xml"
        ).read_text(encoding="utf-8")
        arch = etree.fromstring(view_xml.encode())
        user_fields = arch.xpath("//record[@id='ab_transfer_smart_wizard_view_form']//field[@name='user_id']")

        self.assertTrue(user_fields)
        self.assertTrue(all(field.get("readonly") == "1" for field in user_fields))

    def test_smart_wizard_form_makes_non_creator_fields_readonly(self):
        view_xml = (
            Path(__file__).resolve().parents[1]
            / "views"
            / "ab_transfer_smart_wizard_views.xml"
        ).read_text(encoding="utf-8")
        arch = etree.fromstring(view_xml.encode())
        owner_expression = "create_uid and create_uid != uid"

        self.assertTrue(
            arch.xpath(
                "//record[@id='ab_transfer_smart_wizard_view_form']"
                "//field[@name='create_uid'][@invisible='1']"
            )
        )
        for field_name in (
            "from_store_id",
            "to_stores_id",
            "smart_days",
            "smart_stock_method",
            "dropout_coverage",
            "items_per_header",
            "company_id",
            "notes",
            "smart_product_domain",
            "product_import_text",
            "product_line_ids",
            "fair_store_ids",
        ):
            fields = arch.xpath(
                "//record[@id='ab_transfer_smart_wizard_view_form']//field[@name=$name]",
                name=field_name,
            )
            self.assertTrue(fields, "Missing field %s in Smart Wizard form" % field_name)
            self.assertTrue(
                any(owner_expression in (field.get("readonly") or "") for field in fields),
                "Field %s does not include non-creator readonly expression" % field_name,
            )

        for button_name in (
            "action_archive",
            "action_refresh_smart_cache",
            "action_generate_transfers",
            "action_accept_sales_cache_warning_and_generate",
            "action_refresh_sales_cache_and_generate",
            "action_import_product_lines",
        ):
            buttons = arch.xpath(
                "//record[@id='ab_transfer_smart_wizard_view_form']//button[@name=$name]",
                name=button_name,
            )
            self.assertTrue(buttons, "Missing button %s in Smart Wizard form" % button_name)
            self.assertTrue(
                any(owner_expression in (button.get("invisible") or "") for button in buttons),
                "Button %s does not include non-creator invisible expression" % button_name,
            )

    def test_smart_wizard_copy_resets_user_to_duplicating_users_default_costcenter(self):
        owner_user = self._create_smart_security_user(
            "smart_copy_owner",
            ["ab_transfer_smart.group_transfer_smart_purchase"],
        )
        copy_user = self._create_smart_security_user(
            "smart_copy_user",
            ["ab_transfer_smart.group_transfer_smart_purchase"],
        )
        costcenters = self.env["ab_costcenter"].sudo().search([], limit=2)
        if len(costcenters) < 2:
            self.skipTest("At least two existing costcenters are needed for smart wizard copy tests.")
        original_costcenter, copy_costcenter = costcenters
        try:
            self.env["ab_hr_employee"].sudo().create({
                "name": "SMARTCOPYUSR Employee",
                "user_id": copy_user.id,
                "costcenter_id": copy_costcenter.id,
            })
        except ValidationError as error:
            if "Replication Database" in str(error):
                self.skipTest("Replica database blocks creating employee test records.")
            raise
        wizard = self._create_smart_wizard_for_security(owner_user)
        wizard.with_user(owner_user).write({"user_id": original_costcenter.id})

        copied_wizard = wizard.with_user(copy_user).copy(default={"user_id": original_costcenter.id})

        self.assertEqual(copied_wizard.user_id, copy_costcenter)

    def test_smart_wizard_items_per_header_defaults_to_40(self):
        defaults = self.env["ab_transfer_smart_wizard"].default_get(["items_per_header"])

        self.assertEqual(defaults["items_per_header"], 40)

    def test_smart_wizard_items_per_header_must_be_positive(self):
        wizard = self.env["ab_transfer_smart_wizard"].new({
            "items_per_header": 0,
        })

        with self.assertRaisesRegex(ValidationError, "at least 1"):
            wizard._check_items_per_header()

    def test_purchase_user_can_create_and_write_own_draft_smart_wizard(self):
        purchase_user = self._create_smart_security_user(
            "smart_purchase_owner",
            ["ab_transfer_smart.group_transfer_smart_purchase"],
        )

        wizard = self._create_smart_wizard_for_security(purchase_user)
        wizard.with_user(purchase_user).write({"notes": "Owner update"})

        self.assertEqual(wizard.state, "draft")
        self.assertEqual(wizard.notes, "Owner update")
        self.assertEqual(wizard.create_uid, purchase_user)

    def test_purchase_user_can_read_but_not_write_other_users_draft_smart_wizard(self):
        owner_user = self._create_smart_security_user(
            "smart_purchase_other_owner",
            ["ab_transfer_smart.group_transfer_smart_purchase"],
        )
        purchase_user = self._create_smart_security_user(
            "smart_purchase_reader",
            ["ab_transfer_smart.group_transfer_smart_purchase"],
        )
        wizard = self._create_smart_wizard_for_security(owner_user)

        self.assertEqual(wizard.state, "draft")
        self.assertEqual(
            wizard.with_user(purchase_user).read(["notes", "state"])[0]["id"],
            wizard.id,
        )
        with self.assertRaises(AccessError):
            wizard.with_user(purchase_user).write({"notes": "Blocked update"})

        purchase_user_wizard = self._create_smart_wizard_for_security(purchase_user)
        purchase_user_wizard.with_user(purchase_user).write({"notes": "Own draft update"})

        self.assertEqual(purchase_user_wizard.state, "draft")
        self.assertEqual(purchase_user_wizard.notes, "Own draft update")
        self.assertEqual(purchase_user_wizard.create_uid, purchase_user)

    def test_purchase_user_cannot_edit_other_users_draft_smart_wizard_product_lines(self):
        owner_user = self._create_smart_security_user(
            "smart_product_line_owner",
            ["ab_transfer_smart.group_transfer_smart_purchase"],
        )
        purchase_user = self._create_smart_security_user(
            "smart_product_line_reader",
            ["ab_transfer_smart.group_transfer_smart_purchase"],
        )
        owner_product, purchase_product = self._get_existing_smart_products_or_skip(2)
        owner_wizard = self._create_smart_wizard_for_security(owner_user)
        owner_line = self.env["ab_transfer_smart_product_line"].with_user(owner_user).create({
            "wizard_id": owner_wizard.id,
            "product_id": owner_product.id,
            "qty": 2,
        })

        self.assertEqual(
            owner_line.with_user(purchase_user).read(["qty"])[0]["id"],
            owner_line.id,
        )
        with self.assertRaises(AccessError):
            owner_line.with_user(purchase_user).write({"qty": 3})
        with self.assertRaises(AccessError):
            self.env["ab_transfer_smart_product_line"].with_user(purchase_user).create({
                "wizard_id": owner_wizard.id,
                "product_id": purchase_product.id,
                "qty": 1,
            })

        purchase_wizard = self._create_smart_wizard_for_security(purchase_user)
        purchase_line = self.env["ab_transfer_smart_product_line"].with_user(purchase_user).create({
            "wizard_id": purchase_wizard.id,
            "product_id": purchase_product.id,
            "qty": 1,
        })
        purchase_line.with_user(purchase_user).write({"qty": 4})

        self.assertEqual(purchase_line.qty, 4)

    def test_store_preparation_user_can_read_but_not_create_or_write_smart_wizards(self):
        store_user = self._create_smart_security_user(
            "smart_store_preparation_security",
            ["ab_transfer_smart.group_trnasfer_smart_store_preparation"],
        )
        wizard = self._create_smart_wizard_for_security()

        self.assertEqual(
            wizard.with_user(store_user).read(["notes"])[0]["id"],
            wizard.id,
        )
        with self.assertRaises(AccessError):
            self._create_smart_wizard_for_security(store_user)
        with self.assertRaises(AccessError):
            wizard.with_user(store_user).write({"notes": "Blocked update"})

    def test_store_revision_user_can_read_but_not_create_or_write_smart_wizards(self):
        revision_user = self._create_smart_security_user(
            "smart_store_revision_security",
            ["ab_transfer_smart.group_trnasfer_smart_store_revision"],
        )
        wizard = self._create_smart_wizard_for_security()

        self.assertEqual(
            wizard.with_user(revision_user).read(["notes"])[0]["id"],
            wizard.id,
        )
        with self.assertRaises(AccessError):
            self._create_smart_wizard_for_security(revision_user)
        with self.assertRaises(AccessError):
            wizard.with_user(revision_user).write({"notes": "Blocked update"})

    def test_system_user_has_full_smart_wizard_access(self):
        owner_user = self._create_smart_security_user(
            "smart_system_owner",
            ["ab_transfer_smart.group_transfer_smart_purchase"],
        )
        system_user = self._create_smart_security_user(
            "smart_system_access_user",
            ["base.group_system"],
        )
        wizard = self._create_smart_wizard_for_security(owner_user)

        wizard.with_user(system_user).write({"notes": "System update"})
        system_wizard = self._create_smart_wizard_for_security(system_user)
        wizard.with_user(system_user).unlink()

        self.assertEqual(system_wizard.create_uid, system_user)
        self.assertFalse(wizard.exists())

    def test_store_preparation_user_can_load_dashboard_payload_with_sudoed_reports(self):
        dashboard_user = self.env["res.users"].sudo().with_context(no_reset_password=True).create({
            "name": "Smart Dashboard User",
            "login": "smart_dashboard_user",
            "email": "smart_dashboard_user@example.com",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("ab_transfer_smart.group_trnasfer_smart_store_preparation").id,
            ])],
        })

        with self.assertRaises(AccessError):
            self.env["ab_transfer_receive_header"].with_user(dashboard_user).browse().check_access("read")

        payload = self.env["ab_transfer_header"].with_user(dashboard_user).get_transfer_dashboard_payload()

        self.assertIn("metrics", payload)
        self.assertIn("request_execution", payload)
        self.assertIn("pending_receives", [metric["key"] for metric in payload["metrics"]])
        smart_action = next(action for action in payload["quick_actions"] if action["key"] == "smart_transfer")
        self.assertEqual(smart_action["action"], "ab_transfer_smart.ab_transfer_smart_wizard_action")

    def test_calculate_smart_required_qty(self):
        header = self.env["ab_transfer_header"]

        required_qty = header._calculate_smart_required_qty(
            total_3_months_sales=90,
            branch_stock_qty=10,
            smart_days=60,
        )

        self.assertEqual(required_qty, 50)

    def test_normal_method_planned_qty_uses_90_day_average(self):
        header = self.env["ab_transfer_header"]

        planned_qty = header._calculate_smart_planned_qty(
            total_3_months_sales=900,
            smart_days=60,
            method=SMART_STOCK_METHOD_NORMAL,
        )

        self.assertEqual(planned_qty, 600)

    def test_weighted_method_planned_qty_uses_configured_month_weights(self):
        header = self.env["ab_transfer_header"]

        planned_qty = header._calculate_smart_planned_qty(
            total_3_months_sales=0,
            smart_days=60,
            method=SMART_STOCK_METHOD_WEIGHTED,
            last_month_sales=300,
            previous_month_sales=200,
            third_month_sales=100,
        )

        self.assertAlmostEqual(planned_qty, 460, places=2)

    def test_distributed_qty_uses_source_stock_ratio_when_total_need_exceeds_stock(self):
        header = self.env["ab_transfer_header"]

        distributed_qty = header._calculate_smart_distributed_qty(
            destination_required_qty=30,
            other_branches_required_qty=35,
            source_stock_qty=50,
        )

        self.assertAlmostEqual(distributed_qty, 23.076923, places=5)

    def test_distributed_qty_keeps_destination_need_when_source_covers_total_need(self):
        header = self.env["ab_transfer_header"]

        distributed_qty = header._calculate_smart_distributed_qty(
            destination_required_qty=30,
            other_branches_required_qty=35,
            source_stock_qty=65,
        )

        self.assertEqual(distributed_qty, 30)

    def test_integer_qty_truncates_fractional_distribution(self):
        header = self.env["ab_transfer_header"]

        distributed_qty = header._calculate_smart_distributed_qty(
            destination_required_qty=30,
            other_branches_required_qty=35,
            source_stock_qty=50,
        )

        self.assertEqual(header._calculate_smart_integer_qty(distributed_qty), 23)

    def test_integer_qty_uses_one_for_positive_distribution_below_one(self):
        header = self.env["ab_transfer_header"]

        distributed_qty = header._calculate_smart_distributed_qty(
            destination_required_qty=1,
            other_branches_required_qty=100,
            source_stock_qty=50,
        )

        self.assertLess(distributed_qty, 1)
        self.assertEqual(header._calculate_smart_integer_qty(distributed_qty), 1)

    def test_automatic_qty_rounds_up_to_min_sale_purchase_qty_multiple(self):
        header = self.env["ab_transfer_header"]
        product = SimpleNamespace(min_sale_purchase_qty=24)

        expected_by_qty = {
            10: 24,
            24: 24,
            25: 48,
            30: 48,
            47: 48,
            48: 48,
            60: 72,
            70: 72,
            72: 72,
        }

        for qty, expected in expected_by_qty.items():
            with self.subTest(qty=qty):
                self.assertEqual(
                    header._round_smart_qty_to_min_sale_purchase_qty(product, qty),
                    expected,
                )

    def test_min_sale_purchase_qty_one_preserves_existing_integer_qty(self):
        header = self.env["ab_transfer_header"]
        product = SimpleNamespace(min_sale_purchase_qty=1)

        self.assertEqual(
            header._round_smart_qty_to_min_sale_purchase_qty(product, 30),
            30,
        )

    def test_distribution_ratio_recreates_integer_qty_from_source_stock(self):
        header = self.env["ab_transfer_header"]

        distribution_ratio = header._calculate_smart_distribution_ratio(
            qty=23,
            source_stock_qty=50,
        )

        self.assertAlmostEqual(distribution_ratio, 0.46, places=5)
        self.assertAlmostEqual(distribution_ratio * 50, 23, places=5)

    def test_destination_coverage_is_percentage_of_planned_qty(self):
        header = self.env["ab_transfer_header"]

        coverage = header._calculate_smart_destination_coverage(
            planned_qty=100,
            destination_stock_qty=80,
        )

        self.assertEqual(coverage, 80)

    def test_smart_line_planned_qty_uses_header_stock_method(self):
        header = self.env["ab_transfer_header"].new({
            "smart_days": 60,
            "smart_stock_method": SMART_STOCK_METHOD_NORMAL,
        })
        line = self.env["ab_transfer_smart_line"].new({
            "smart_month1_sales": 60,
            "smart_month2_sales": 45,
            "smart_month3_sales": 45,
        })

        planned_qty = header._calculate_smart_line_planned_qty(line)

        self.assertEqual(planned_qty, 100)

    def test_other_branch_store_sql_ids_fallback_uses_sale_stores(self):
        source = self._create_store_or_skip({
            "name": "Smart Source",
            "code": "SMART-SRC",
            "eplus_serial": 101,
            "allow_sale": True,
        })
        destination = self._create_store_or_skip({
            "name": "Smart Destination",
            "code": "SMART-DST",
            "eplus_serial": 102,
            "allow_sale": True,
        })
        other = self._create_store_or_skip({
            "name": "Smart Other",
            "code": "SMART-OTH",
            "eplus_serial": 103,
            "allow_sale": True,
        })
        not_for_sale = self._create_store_or_skip({
            "name": "Smart No Sale",
            "code": "SMART-NO-SALE",
            "eplus_serial": 104,
            "allow_sale": False,
        })
        header = self.env["ab_transfer_header"].new({
            "from_store_id": source.id,
            "to_store_id": destination.id,
        })

        store_sql_ids = header._get_smart_other_branch_store_sql_ids()

        self.assertIn(other.eplus_serial, store_sql_ids)
        self.assertNotIn(source.eplus_serial, store_sql_ids)
        self.assertNotIn(destination.eplus_serial, store_sql_ids)
        self.assertNotIn(not_for_sale.eplus_serial, store_sql_ids)

    def test_other_branch_store_sql_ids_excludes_destination_from_fair_stores(self):
        source = self._create_store_or_skip({
            "name": "Smart Fair Source",
            "code": "SMART-FAIR-SRC",
            "eplus_serial": 201,
        })
        destination = self._create_store_or_skip({
            "name": "Smart Fair Destination",
            "code": "SMART-FAIR-DST",
            "eplus_serial": 202,
        })
        other = self._create_store_or_skip({
            "name": "Smart Fair Other",
            "code": "SMART-FAIR-OTH",
            "eplus_serial": 203,
        })
        header = self.env["ab_transfer_header"].new({
            "from_store_id": source.id,
            "to_store_id": destination.id,
            "fair_store_ids": [(6, 0, (destination | other).ids)],
        })

        store_sql_ids = header._get_smart_other_branch_store_sql_ids()

        self.assertEqual(store_sql_ids, [other.eplus_serial])

    def test_select_smart_source_row_prefers_row_covering_required_qty(self):
        header = self.env["ab_transfer_header"]

        selected = header._select_smart_source_row(
            [
                {"source_id": 1, "qty": 10},
                {"source_id": 2, "qty": 30},
            ],
            required_qty=20,
        )

        self.assertEqual(selected["source_id"], 2)

    def test_smart_row_indexes_use_eplus_product_serial(self):
        header = self.env["ab_transfer_header"]
        row = (1234, "P001", "Product", 20, 10, 1, 2, 3, 90)

        self.assertEqual(header._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL), 1234)
        self.assertEqual(header._smart_row_float(row, SMART_ROW_BRANCH_STOCK_QTY), 10)
        self.assertEqual(header._smart_row_float(row, SMART_ROW_LAST_MONTH_SALES), 1)
        self.assertEqual(header._smart_row_float(row, SMART_ROW_PREVIOUS_MONTH_SALES), 2)
        self.assertEqual(header._smart_row_float(row, SMART_ROW_THIRD_MONTH_SALES), 3)
        self.assertEqual(header._smart_row_float(row, SMART_ROW_TOTAL_3_MONTHS_SALES), 90)

    def test_smart_rows_sort_helper_orders_by_product_location(self):
        header = self.env["ab_transfer_header"]
        product_b = SimpleNamespace(
            location="B-01",
            display_name="Product B",
            name="Product B",
        )
        product_a = SimpleNamespace(
            location="A-01",
            display_name="Product A",
            name="Product A",
        )
        product_c = SimpleNamespace(
            location="A-01",
            display_name="Product C",
            name="Product C",
        )

        rows = header._sort_smart_rows_by_product_location(
            [
                (99402, "P002", "Product B", 8102, 0, 90, 0, 0, 90),
                (99403, "P003", "Product C", 8102, 0, 90, 0, 0, 90),
                (99401, "P001", "Product A", 8102, 0, 90, 0, 0, 90),
            ],
            {
                99401: product_a,
                99402: product_b,
                99403: product_c,
            },
        )

        self.assertEqual([row[SMART_ROW_PRODUCT_SERIAL] for row in rows], [99401, 99403, 99402])

    def _get_report_template_xml(self, template_id):
        report_path = (
            Path(__file__).resolve().parents[1]
            / "report"
            / "ab_transfer_line_reports.xml"
        )
        report_tree = etree.parse(str(report_path))
        template = report_tree.xpath("//template[@id='%s']" % template_id)[0]
        return etree.tostring(template, encoding="unicode")

    def test_smart_lines_report_uses_requested_smart_fields_and_landscape_layout(self):
        report_xml = self._get_report_template_xml("report_ab_transfer_smart_lines")
        report_action = self.env.ref(
            "ab_transfer_smart.action_report_ab_transfer_smart_lines"
        )

        self.assertIn("o.get_smart_lines_for_report()", report_xml)
        self.assertNotIn("o.get_transfer_lines_for_report()", report_xml)
        self.assertNotIn("o.eplus_serial", report_xml)
        self.assertIn("ab-smart-lines-report", report_xml)
        for header in (
            "Code",
            "Product",
            "Qty",
            "UoM",
            "Exc.",
            "Stock",
        ):
            self.assertIn(">%s<" % header, report_xml)
        for removed_header in (
            "Source Type",
            "Create Day",
            "Location",
            "Expiry Date",
            "UOM",
            "Exclusion Reason",
            "Source Stock",
            "Expected Stock",
            "Destination Stock",
            "Total Need",
            "Over Need",
        ):
            self.assertNotIn(">%s<" % removed_header, report_xml)
        for field_name in (
            "line.product_id.code",
            "line.product_id.name",
            "line.qty",
            "line.exclusion_reason",
            "line.smart_source_stock_qty",
        ):
            self.assertIn(field_name, report_xml)
        for removed_field_name in (
            "line.source_type",
            "line.create_day",
            "line.smart_product_location",
            "line.expiry_date",
            "line.smart_expected_source_stock_qty",
            "line.smart_destination_stock_qty",
            "line.smart_total_need",
            "line.smart_over_need_qty",
        ):
            self.assertNotIn(removed_field_name, report_xml)
        self.assertEqual(report_xml.count("Transfer Date"), 1)
        self.assertEqual(report_xml.count("Printing Date"), 1)
        self.assertEqual(report_xml.count("get_smart_report_transfer_date_text()"), 1)
        self.assertEqual(report_xml.count("get_smart_report_printing_date_text()"), 1)
        self.assertNotIn("get_smart_report_line_chunks", report_xml)
        self.assertNotIn("line_chunk", report_xml)
        self.assertEqual(report_action.paperformat_id.orientation, "Portrait")

    def test_sent_lines_report_uses_transfer_line_fields_and_landscape_layout(self):
        report_xml = self._get_report_template_xml("report_ab_transfer_lines")
        sent_action = self.env.ref("ab_transfer_smart.action_report_ab_transfer_lines")
        smart_action = self.env.ref("ab_transfer_smart.action_report_ab_transfer_smart_lines")

        self.assertIn("o.get_smart_report_sorted_lines(o.line_ids)", report_xml)
        self.assertNotIn("o.get_transfer_lines_for_report()", report_xml)
        self.assertNotIn("o.get_smart_lines_for_report()", report_xml)
        self.assertNotIn("o.get_smart_report_eplus_serial_text()", report_xml)
        self.assertIn('t-field="o.eplus_serial"', report_xml)
        self.assertIn("B-Connect Transfer No.", report_xml)
        self.assertIn("ab-smart-lines-report", report_xml)
        for header in (
            "Code",
            "Product",
            "Qty",
            "UoM",
            "Stock",
            "Expected",
        ):
            self.assertIn(">%s<" % header, report_xml)
        self.assertNotIn("line.exclusion_reason", report_xml)
        for field_name in (
            "line.product_id.code",
            "line.product_id.name",
            "line.qty",
            "line.smart_source_stock_qty",
            "line.smart_expected_source_stock_qty",
        ):
            self.assertIn(field_name, report_xml)
        for removed_header in (
            "Location",
            "Quantity",
            "Over Need",
            "Expiry Date",
            "UOM",
            "Exc.",
            "Sell Price",
            "Cost",
            "Purchase Price",
        ):
            self.assertNotIn(">%s<" % removed_header, report_xml)
        self.assertNotIn("line.smart_product_location", report_xml)
        self.assertNotIn("line.smart_over_need_qty", report_xml)
        self.assertNotIn("line.expiry_date", report_xml)
        self.assertNotIn("line.sell_price", report_xml)
        self.assertNotIn("line.cost", report_xml)
        self.assertNotIn("line.purchase_price", report_xml)
        self.assertEqual(report_xml.count("Transfer Date"), 1)
        self.assertEqual(report_xml.count("Printing Date"), 1)
        self.assertEqual(report_xml.count("get_smart_report_transfer_date_text()"), 1)
        self.assertEqual(report_xml.count("get_smart_report_printing_date_text()"), 1)
        self.assertNotIn("get_smart_report_line_chunks", report_xml)
        self.assertNotIn("line_chunk", report_xml)
        self.assertNotEqual(sent_action.paperformat_id, smart_action.paperformat_id)
        self.assertEqual(sent_action.paperformat_id.orientation, "Portrait")
        self.assertEqual(smart_action.paperformat_id.orientation, "Portrait")

    def test_smart_submit_flow_syncs_eplus_serial_from_sent_transfer(self):
        smart_header_path = (
            Path(__file__).resolve().parents[1]
            / "models"
            / "ab_transfer_header.py"
        )
        smart_header_source = smart_header_path.read_text(encoding="utf-8")

        self.assertIn("eplus_serial = fields.Integer", smart_header_source)
        self.assertIn("_sync_smart_eplus_serial_from_sent_transfer()", smart_header_source)
        self.assertIn("_write_smart_eplus_serial_after_submit(eplus_serial)", smart_header_source)
        self.assertIn('models.Model.write(self.sudo(), {"eplus_serial": eplus_serial})', smart_header_source)
        self.assertIn("SELECT TOP (1) stnh_id", smart_header_source)

    def test_pdf_report_helpers_return_their_exact_line_models(self):
        header = self._create_smart_header_from_existing_records_or_skip()

        self.assertEqual(
            header.get_transfer_lines_for_report()._name,
            "ab_transfer_line",
        )
        self.assertEqual(
            header.get_smart_lines_for_report()._name,
            "ab_transfer_smart_line",
        )

    def test_print_buttons_use_independent_pdf_report_actions(self):
        header = self._create_smart_header_from_existing_records_or_skip()

        smart_result = header.action_print_smart_transfer_lines()
        transfer_result = header.action_print_transfer_lines()

        self.assertEqual(smart_result["report_type"], "qweb-pdf")
        self.assertEqual(
            smart_result["report_name"],
            "ab_transfer_smart.report_ab_transfer_smart_lines",
        )
        self.assertEqual(transfer_result["report_type"], "qweb-pdf")
        self.assertEqual(
            transfer_result["report_name"],
            "ab_transfer_smart.report_ab_transfer_lines",
        )

    def test_report_buttons_keep_smart_print_available_in_all_stages(self):
        view_path = (
            Path(__file__).resolve().parents[1]
            / "views"
            / "ab_transfer_header_views.xml"
        )
        view_tree = etree.parse(str(view_path))
        smart_button = view_tree.xpath(
            "//button[@name='action_print_smart_transfer_lines']"
        )[0]
        transfer_button = view_tree.xpath(
            "//button[@name='action_print_transfer_lines']"
        )[0]
        self.assertIsNone(smart_button.get("invisible"))
        self.assertEqual(
            transfer_button.get("invisible"),
            "not is_submitted",
        )
        self.assertFalse(
            view_tree.xpath("//button[@name='action_export_smart_transfer_excel']")
        )

    def test_smart_transfer_xlsx_report_has_exact_columns(self):
        report_model = self.env[
            "report.ab_transfer_smart.smart_transfer_wizard_xlsx"
        ]
        report_action = self.env.ref(
            "ab_transfer_smart.action_report_ab_transfer_smart_wizard_xlsx"
        )

        self.assertEqual(report_action.model, "ab_transfer_smart_wizard")
        self.assertEqual(report_action.report_type, "xlsx")
        self.assertEqual(
            report_model._HEADERS,
            (
                "code",
                "product name",
                "company",
                "purchase unit",
                "sell_price",
                "purchase_price",
                "source stock",
                "destination stock",
                "Sales 3 month",
                "moving weighted avg",
                "need",
            ),
        )

    def test_smart_transfer_xlsx_report_renders_expected_headers(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "company_id": header.company_id.id,
        })
        report_action = self.env.ref(
            "ab_transfer_smart.action_report_ab_transfer_smart_wizard_xlsx"
        )
        row = {
            "code": "P001",
            "product_name": "Product A",
            "company": SMART_EXPORT_COMPANY_NAME,
            "purchase_unit": 3.0,
            "sell_price": 14.0,
            "purchase_price": 9.0,
            "source_stock": 50.0,
            "destination_stock": 8.0,
            "sales_3_month": 60.0,
            "moving_weighted_avg": 23.0,
            "need": 7.0,
        }

        probe = SimpleNamespace(to_store_id=header.to_store_id)
        probe.with_context = lambda **kwargs: probe
        probe._get_smart_transfer_excel_rows = lambda **kwargs: [row]
        with patch.object(
                type(wizard),
                "_validate_smart_export_values",
                return_value=None,
        ), patch.object(
                type(wizard),
                "_get_smart_export_probe_headers",
                return_value=[probe],
        ):
            content, file_type = self.env["ir.actions.report"]._render_xlsx(
                report_action.report_name,
                wizard.ids,
                data={"allow_incomplete_sales_cache": False},
            )

        self.assertEqual(file_type, "xlsx")
        with zipfile.ZipFile(io.BytesIO(content)) as workbook:
            shared_strings = workbook.read("xl/sharedStrings.xml").decode("utf-8")
        for label in self.env[
                "report.ab_transfer_smart.smart_transfer_wizard_xlsx"
        ]._get_translated_headers():
            self.assertIn(str(label), shared_strings)
        self.assertIn(SMART_EXPORT_COMPANY_NAME, shared_strings)
        self.assertIn("Product A", shared_strings)

    def test_pre_submit_sent_lines_report_renders_without_eplus_serial_field(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        header.smart_stage = SMART_STAGE_PRE_SUBMIT

        self.assertEqual(header.get_smart_report_eplus_serial_text(), "")
        html = self.env["ir.actions.report"]._render_qweb_html(
            "ab_transfer_smart.report_ab_transfer_lines",
            header.ids,
        )[0]

        self.assertTrue(html)

    def test_smart_transfer_wizard_xlsx_creates_unique_sheet_per_destination(self):
        report_model = self.env[
            "report.ab_transfer_smart.smart_transfer_wizard_xlsx"
        ]
        store_1 = SimpleNamespace(
            code="STORE-ONE",
            display_name="A destination name long enough to collide after truncation",
        )
        store_2 = SimpleNamespace(
            code="STORE-ONE",
            display_name="A destination name long enough to collide after truncation",
        )
        row = {
            "code": "P001",
            "product_name": "Product A",
            "company": SMART_EXPORT_COMPANY_NAME,
            "purchase_unit": 2.0,
            "sell_price": 12.0,
            "purchase_price": 9.0,
            "source_stock": 20.0,
            "destination_stock": 4.0,
            "sales_3_month": 30.0,
            "moving_weighted_avg": 11.0,
            "need": 6.0,
        }

        def make_probe(store, rows):
            probe = SimpleNamespace(to_store_id=store)
            probe.with_context = lambda **kwargs: probe
            probe._get_smart_transfer_excel_rows = lambda **kwargs: rows
            return probe

        probes = [make_probe(store_1, [row]), make_probe(store_2, [])]
        wizard = SimpleNamespace(
            _validate_smart_export_values=lambda: None,
            _get_smart_export_probe_headers=lambda: probes,
        )
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        report_model.generate_xlsx_report(
            workbook,
            {"allow_incomplete_sales_cache": False},
            [wizard],
        )
        workbook.close()

        with zipfile.ZipFile(io.BytesIO(output.getvalue())) as archive:
            workbook_xml = etree.fromstring(archive.read("xl/workbook.xml"))
            shared_strings = archive.read("xl/sharedStrings.xml").decode("utf-8")
        sheet_names = workbook_xml.xpath(
            "//*[local-name()='sheet']/@name"
        )
        self.assertEqual(len(sheet_names), 2)
        self.assertEqual(len({name.casefold() for name in sheet_names}), 2)
        self.assertTrue(all(len(name) <= 31 for name in sheet_names))
        self.assertIn(SMART_EXPORT_COMPANY_NAME, shared_strings)

    def test_smart_lines_report_is_bound_to_transfer_list_multi_print(self):
        report_action = self.env.ref("ab_transfer_smart.action_report_ab_transfer_smart_lines")

        self.assertEqual(report_action.binding_model_id.model, "ab_transfer_header")
        self.assertEqual(report_action.binding_type, "report")
        self.assertEqual(report_action.binding_view_types, "list")
        self.assertTrue(report_action.multi)

    def test_smart_line_views_do_not_show_class_id(self):
        view_xml = (
            Path(__file__).resolve().parents[1]
            / "views"
            / "ab_transfer_header_views.xml"
        ).read_text(encoding="utf-8")

        self.assertNotIn('name="class_id"', view_xml)
        self.assertIn('name="smart_expected_source_stock_qty"', view_xml)
        self.assertIn('name="smart_over_need_qty"', view_xml)
        self.assertIn('name="smart_qty_exceeds_expected_stock"', view_xml)
        expected_decoration = (
            'decoration-danger="smart_stage == \'purchase_preparation\' and '
            '(smart_qty_exceeds_over_need or smart_qty_exceeds_expected_stock)"'
        )
        self.assertIn(
            expected_decoration,
            view_xml,
        )
        self.assertEqual(view_xml.count(expected_decoration), 3)
        self.assertNotIn(
            'decoration-danger="smart_qty_exceeds_over_need or smart_qty_exceeds_expected_stock"',
            view_xml,
        )

    def test_header_view_keeps_smart_stage_buttons(self):
        view_xml = (
            Path(__file__).resolve().parents[1]
            / "views"
            / "ab_transfer_header_views.xml"
        ).read_text(encoding="utf-8")

        self.assertIn('name="action_smart_to_store_preparation"', view_xml)
        self.assertIn('name="action_smart_to_store_revision"', view_xml)
        self.assertIn('name="action_smart_pre_submit"', view_xml)
        self.assertIn('name="action_smart_back_to_purchase_preparation"', view_xml)
        self.assertIn('name="action_smart_back_to_store_preparation"', view_xml)
        self.assertIn('name="action_smart_back_to_store_revision"', view_xml)
        self.assertIn("group_trnasfer_smart_store_manager", view_xml)

    def test_smart_wizard_form_has_archive_button(self):
        view_xml = (
            Path(__file__).resolve().parents[1]
            / "views"
            / "ab_transfer_smart_wizard_views.xml"
        ).read_text(encoding="utf-8")

        self.assertIn('name="action_archive"', view_xml)
        self.assertIn("Archive this wizard and all generated transfers?", view_xml)
        self.assertIn('title="Archived"', view_xml)
        self.assertIn('bg_color="text-bg-danger"', view_xml)
        self.assertIn('invisible="active"', view_xml)

    def test_purchase_can_archive_wizard_and_generated_purchase_preparation_transfers(self):
        wizard, header = self._create_smart_archive_wizard()
        extra_header = self._create_generated_header_for_archive_wizard(wizard, header)

        action = wizard.action_archive()

        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["next"]["tag"], "soft_reload")
        self.assertFalse(wizard.with_context(active_test=False).active)
        self.assertFalse(any((header | extra_header).with_context(active_test=False).mapped("active")))
        self.assertFalse(self.env["ab_transfer_smart_wizard"].search([("id", "=", wizard.id)]))
        self.assertFalse(self.env["ab_transfer_header"].search([("id", "=", header.id)]))
        self.assertFalse(self.env["ab_transfer_header"].search([("id", "=", extra_header.id)]))
        self.assertEqual(
            self.env["ab_transfer_smart_wizard"].with_context(active_test=False).search([("id", "=", wizard.id)]),
            wizard,
        )
        archived_headers = self.env["ab_transfer_header"].with_context(active_test=False).search([
            ("id", "in", (header | extra_header).ids),
        ])
        self.assertEqual(set(archived_headers.ids), set((header | extra_header).ids))

    def test_archive_wizard_blocks_if_generated_transfer_not_purchase_preparation(self):
        wizard, header = self._create_smart_archive_wizard(
            smart_stage=SMART_STAGE_STORE_PREPARATION,
        )
        extra_header = self._create_generated_header_for_archive_wizard(wizard, header)

        with self.assertRaisesRegex(UserError, "Purchase Preparation"):
            wizard.action_archive()

        self.assertTrue(wizard.active)
        self.assertTrue(all((header | extra_header).mapped("active")))

    def test_apply_smart_transfer_rows_creates_smart_line_not_transfer_line(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-STAGE-P1", 99011, uom)
        header.target_product_ids = [(6, 0, product.ids)]

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={99011: 50},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={},
        ), patch.object(
                type(header),
                "_prepare_smart_line_vals",
                return_value={
                    "qty": 7,
                    "expiry_date": fields.Date.today(),
                    "uom_id": uom.id,
                    "smart_source_stock_qty": 50,
                },
        ):
            result = header._apply_smart_transfer_rows([
                (99011, "P001", "Product", 8102, 0, 90, 0, 0, 90),
            ])

        self.assertEqual(result["created"], 1)
        self.assertEqual(len(header.smart_line_ids), 1)
        self.assertFalse(header.line_ids)
        self.assertEqual(header.smart_line_ids.product_id, product)
        self.assertFalse(header.smart_line_ids.class_id)

    def test_smart_transfer_preview_matches_apply_without_persisting_preview(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        uom = product.uom_id
        product_serial = int(product.eplus_serial)
        header.target_product_ids = [(6, 0, product.ids)]
        destination_rows = [
            (product_serial, "P501", "Preview Product", 8102, 0, 90, 0, 0, 90),
        ]
        prepared_vals = {
            "qty": 7,
            "expiry_date": fields.Date.today(),
            "uom_id": uom.id,
            "smart_source_stock_qty": 50,
            "smart_destination_stock_qty": 0,
            "smart_month1_sales": 90,
            "smart_month2_sales": 0,
            "smart_month3_sales": 0,
        }

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={product_serial: 50},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={},
        ), patch.object(
                type(header),
                "_prepare_smart_line_vals",
                return_value=prepared_vals,
        ):
            preview_rows, preview_result = header._prepare_smart_transfer_preview_rows(
                destination_rows
            )

            self.assertFalse(header.smart_line_ids)
            self.assertFalse(header.line_ids)
            self.assertEqual(preview_result["created"], 0)
            self.assertEqual(preview_rows[0]["line_vals"]["qty"], 7)

            apply_result = header._apply_smart_transfer_rows(destination_rows)

        self.assertEqual(apply_result["created"], 1)
        self.assertEqual(header.smart_line_ids.qty, preview_rows[0]["line_vals"]["qty"])

    def test_target_product_with_zero_destination_need_gets_default_smart_line_qty(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        target_product = self._create_smart_product("SMART-ZERO-NEED-TARGET", 99014, uom)
        domain_product = self._create_smart_product("SMART-ZERO-NEED-DOMAIN", 99015, uom)
        header.write({
            "target_product_ids": [(6, 0, target_product.ids)],
            "smart_product_domain": "[('id', '=', %s)]" % domain_product.id,
        })
        prepare_calls = []

        def prepare_line_vals(
                product,
                required_qty,
                source_stock_qty,
                destination_stock_qty,
                month1_sales,
                month2_sales,
                month3_sales,
                destination_required_qty,
                other_required_qty,
                total_required_qty,
                other_branches_context=None,
        ):
            prepare_calls.append({
                "product": product,
                "required_qty": required_qty,
                "source_stock_qty": source_stock_qty,
                "destination_stock_qty": destination_stock_qty,
                "month_sales": month1_sales + month2_sales + month3_sales,
                "destination_required_qty": destination_required_qty,
                "other_required_qty": other_required_qty,
                "total_required_qty": total_required_qty,
                "other_branches_context": other_branches_context,
            })
            return {
                "qty": required_qty,
                "expiry_date": fields.Date.today(),
                "uom_id": uom.id,
                "smart_source_stock_qty": source_stock_qty,
                "smart_destination_stock_qty": destination_stock_qty,
                "smart_month1_sales": month1_sales,
                "smart_month2_sales": month2_sales,
                "smart_month3_sales": month3_sales,
                "smart_need_destination_store": destination_required_qty,
                "smart_need_other_store": other_required_qty,
                "smart_total_need": total_required_qty,
            }

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={99014: 20, 99015: 20},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={},
        ), patch.object(
                type(header),
                "_prepare_smart_line_vals",
                side_effect=prepare_line_vals,
        ):
            result = header._apply_smart_transfer_rows([
                (99014, "P014", "Target", 8102, 100, 10, 0, 0, 10),
                (99015, "P015", "Domain", 8102, 0, 0, 0, 0, 0),
            ])

        self.assertEqual(result["created"], 1)
        self.assertEqual(len(header.smart_line_ids), 1)
        self.assertEqual(header.smart_line_ids.product_id, target_product)
        self.assertEqual(header.smart_line_ids.qty, 1)
        self.assertEqual(header.smart_line_ids.smart_source_stock_qty, 20)
        self.assertEqual(header.smart_line_ids.smart_destination_stock_qty, 100)
        self.assertEqual(header.smart_line_ids.smart_month1_sales, 10)
        self.assertEqual(len(prepare_calls), 1)
        self.assertEqual(prepare_calls[0]["product"], target_product)
        self.assertEqual(prepare_calls[0]["required_qty"], 1)
        self.assertEqual(prepare_calls[0]["destination_required_qty"], 1)
        self.assertEqual(prepare_calls[0]["total_required_qty"], 1)
        self.assertEqual(prepare_calls[0]["month_sales"], 10)

    def test_wizard_import_product_lines_from_excel_text(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product_1 = self._create_smart_product("SMART-IMPORT-1", 99018, uom)
        product_2 = self._create_smart_product("SMART-IMPORT-2", 99019, uom)
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "product_import_text": "%s\t5\n%s,7\n%s\t3" % (
                product_1.code,
                product_2.code,
                product_1.code,
            ),
        })

        first_confirmation_action = wizard.action_import_product_lines()
        self.assertEqual(
            first_confirmation_action["res_model"],
            "ab.transfer.smart.duplicate.import.confirmation",
        )
        first_confirmation = self.env[first_confirmation_action["res_model"]].browse(
            first_confirmation_action["res_id"]
        )
        self.assertEqual(first_confirmation.step, "detect")

        first_confirmation.action_cancel()
        self.assertFalse(wizard.product_line_ids)
        self.assertTrue(wizard.product_import_text)

        second_confirmation_action = first_confirmation.action_continue_to_sum_confirmation()
        self.assertEqual(second_confirmation_action["res_id"], first_confirmation.id)
        self.assertEqual(first_confirmation.step, "sum")

        first_confirmation.action_cancel()
        self.assertFalse(wizard.product_line_ids)
        self.assertTrue(wizard.product_import_text)

        first_confirmation.action_confirm_import()

        qty_by_product = {
            line.product_id.id: line.qty
            for line in wizard.product_line_ids
        }
        self.assertEqual(qty_by_product[product_1.id], 8)
        self.assertEqual(qty_by_product[product_2.id], 7)
        self.assertFalse(wizard.product_import_text)

    def test_wizard_product_lines_reject_duplicate_manual_product(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-DUPLICATE-LINE", 99023, uom)
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "product_line_ids": [(0, 0, {
                "product_id": product.id,
                "qty": 5,
            })],
        })

        with self.assertRaises(ValidationError):
            wizard.write({
                "product_line_ids": [(0, 0, {
                    "product_id": product.id,
                    "qty": 3,
                })],
            })

    def test_smart_product_line_requested_qty_sets_transfer_qty_without_changing_need(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        product_serial = int(product.eplus_serial)
        header.write({
            "smart_days": 30,
            "smart_stock_method": SMART_STOCK_METHOD_NORMAL,
        })
        header.smart_product_line_ids = [(0, 0, {
            "product_id": product.id,
            "qty": 30,
        })]

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={product_serial: 10},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={product_serial: {"required_qty": 5}},
        ), patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[self._smart_source_row(701, 10)],
        ):
            result = header._apply_smart_transfer_rows([
                (product_serial, "P020", "Requested", 8102, 10, 30, 30, 30, 90),
            ])

        self.assertEqual(result["created"], 1)
        line = header.smart_line_ids
        self.assertEqual(line.qty, 30)
        self.assertEqual(line.smart_original_qty, 8)
        self.assertEqual(line.smart_need_destination_store, 20)
        self.assertEqual(line.smart_need_other_store, 5)
        self.assertEqual(line.smart_total_need, 25)
        self.assertTrue(line.smart_qty_exceeds_over_need)

    def test_smart_product_line_creates_requested_qty_without_source_stock_or_need(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        product_serial = int(product.eplus_serial)
        header.write({
            "smart_days": 30,
            "smart_stock_method": SMART_STOCK_METHOD_NORMAL,
        })
        header.smart_product_line_ids = [(0, 0, {
            "product_id": product.id,
            "qty": 6,
        })]

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={product_serial: 0},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={},
        ), patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[],
        ):
            result = header._apply_smart_transfer_rows([
                (product_serial, "P021", "Manual", 8102, 100, 0, 0, 0, 0),
            ])

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["no_stock"], 0)
        line = header.smart_line_ids
        self.assertEqual(line.qty, 6)
        self.assertEqual(line.smart_original_qty, 0)
        self.assertEqual(line.smart_source_stock_qty, 0)
        self.assertEqual(line.smart_need_destination_store, 0)
        self.assertEqual(line.smart_total_need, 0)
        self.assertTrue(line.smart_qty_exceeds_over_need)

    def test_smart_product_line_source_stock_filter_keeps_requested_product_without_stock(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        product_serial = int(product.eplus_serial)
        header.smart_product_line_ids = [(0, 0, {
            "product_id": product.id,
            "qty": 6,
        })]

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={},
        ):
            serials = header._get_smart_target_product_serials_with_source_stock()

        self.assertIn(product_serial, serials)

    def test_target_product_still_requires_source_stock_filter(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        target_product = self._create_smart_product("SMART-NO-STOCK-TARGET", 99016, uom)
        header.target_product_ids = [(6, 0, target_product.ids)]

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={},
        ):
            serials = header._get_smart_target_product_serials_with_source_stock()

        self.assertNotIn(99016, serials)

    def test_zero_source_stock_products_are_centralized_without_sorting(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product_b = self._create_smart_product("SMART-ZERO-B", 990161, uom)
        product_a = self._create_smart_product("SMART-ZERO-A", 990162, uom)
        in_stock_product = self._create_smart_product("SMART-IN-STOCK", 990163, uom)
        header.target_product_ids = [(6, 0, (product_b | product_a | in_stock_product).ids)]

        zero_stock_products = header._get_smart_zero_source_stock_products({
            "products_by_serial": {
                990161: product_b,
                990162: product_a,
                990163: in_stock_product,
            },
            "source_stock_by_serial": {
                990161: 0.0,
                990162: -1.0,
                990163: 5.0,
            },
        })

        self.assertEqual(zero_stock_products.ids, [product_b.id, product_a.id])

    def test_domain_zero_source_stock_products_do_not_open_warning(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        domain_product = self._create_smart_product("SMART-DOMAIN-ZERO", 990166, uom)

        zero_stock_products = header._get_smart_zero_source_stock_products({
            "products_by_serial": {
                990166: domain_product,
            },
            "source_stock_by_serial": {
                990166: 0.0,
            },
        })

        self.assertFalse(zero_stock_products)

    def test_continue_ignored_products_are_removed_before_source_stock_query(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        ignored_product = self._create_smart_product(
            "SMART-IGNORE-ZERO",
            990164,
            uom,
        )
        available_product = self._create_smart_product(
            "SMART-KEEP-STOCK",
            990165,
            uom,
        )
        header.target_product_ids = [
            (6, 0, (ignored_product | available_product).ids),
        ]
        captured_serials = []

        def source_stock(products_by_serial):
            captured_serials.append(set(products_by_serial))
            return {990165: 9.0}

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                side_effect=source_stock,
        ):
            context = header.with_context(
                smart_ignored_zero_source_product_ids=ignored_product.ids
            )._get_smart_candidate_source_stock_context()

        self.assertEqual(captured_serials, [{990165}])
        self.assertEqual(set(context["products_by_serial"]), {990165})
        self.assertEqual(context["source_stock_by_serial"], {990165: 9.0})

    def test_continue_ignored_products_are_excluded_from_candidate_domain(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        ignored_product, available_product = (
            self._get_existing_smart_products_or_skip(2)
        )
        header.smart_product_domain = repr([
            ("id", "in", (ignored_product | available_product).ids),
        ])

        candidates = header.with_context(
            smart_ignored_zero_source_product_ids=ignored_product.ids
        )._get_smart_candidate_products()

        self.assertEqual(candidates, available_product)

    def test_continue_all_ignored_products_skips_source_stock_query(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        header.smart_product_line_ids = [(0, 0, {
            "product_id": product.id,
            "qty": 5,
        })]

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
        ) as source_stock:
            context = header.with_context(
                smart_ignored_zero_source_product_ids=product.ids
            )._get_smart_candidate_source_stock_context()

        source_stock.assert_not_called()
        self.assertEqual(context, {
            "products_by_serial": {},
            "source_stock_by_serial": {},
        })

    def test_header_calculation_opens_zero_stock_warning_before_fetching_rows(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        product_serial = int(product.eplus_serial)
        header.target_product_ids = [(6, 0, product.ids)]
        source_stock_context = {
            "products_by_serial": {product_serial: product},
            "source_stock_by_serial": {product_serial: 0.0},
        }

        with patch.object(
                type(header),
                "_ensure_smart_destination_cache",
                return_value=None,
        ), patch.object(
                type(header),
                "_validate_smart_transfer_header",
                return_value=None,
        ), patch.object(
                type(header),
                "_get_smart_sales_cache_warning_action_if_needed",
                return_value=False,
        ), patch.object(
                type(header),
                "_get_smart_candidate_source_stock_context",
                return_value=source_stock_context,
        ), patch.object(
                type(header),
                "_fetch_destination_smart_rows",
        ) as fetch_rows:
            action = header.action_smart_transfer_calculation()

        fetch_rows.assert_not_called()
        self.assertEqual(
            action["res_model"],
            "ab_transfer_smart_zero_stock_warning",
        )
        warning = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(warning.source_store_id, header.from_store_id)
        self.assertEqual(warning.zero_product_ids, product.ids)
        self.assertEqual(warning.zero_product_count, 1)
        self.assertEqual(warning.header_id, header)
        self.assertFalse(warning.smart_wizard_id)

    def test_header_calculation_skips_domain_zero_stock_warning(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        product_serial = int(product.eplus_serial)
        source_stock_context = {
            "products_by_serial": {product_serial: product},
            "source_stock_by_serial": {product_serial: 0.0},
        }

        with patch.object(
                type(header),
                "_ensure_smart_destination_cache",
                return_value=None,
        ), patch.object(
                type(header),
                "_validate_smart_transfer_header",
                return_value=None,
        ), patch.object(
                type(header),
                "_get_smart_sales_cache_warning_action_if_needed",
                return_value=False,
        ), patch.object(
                type(header),
                "_get_smart_candidate_source_stock_context",
                return_value=source_stock_context,
        ), patch.object(
                type(header),
                "_fetch_destination_smart_rows",
                return_value=[],
        ) as fetch_rows, patch.object(
                type(header),
                "_apply_smart_transfer_rows",
                return_value={
                    "created": 0,
                    "updated": 0,
                    "dropout_excluded": 0,
                    "missing": 0,
                    "no_stock": 0,
                },
        ):
            action = header.action_smart_transfer_calculation()

        fetch_rows.assert_called_once_with(source_stock_context=source_stock_context)
        self.assertEqual(action["tag"], "display_notification")

    def test_header_zero_stock_continue_skips_repeated_warning(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        product_serial = int(product.eplus_serial)
        header.target_product_ids = [(6, 0, product.ids)]
        source_stock_context = {
            "products_by_serial": {product_serial: product},
            "source_stock_by_serial": {product_serial: 0.0},
        }
        warning_action = self.env[
            "ab_transfer_smart_zero_stock_warning"
        ]._open_warning(
            header.from_store_id,
            product,
            header=header,
        )
        warning = self.env[warning_action["res_model"]].browse(
            warning_action["res_id"]
        )

        def resumed_source_context(resumed_header):
            self.assertEqual(resumed_header, header)
            self.assertEqual(
                resumed_header.env.context.get(
                    "smart_ignored_zero_source_product_ids"
                ),
                product.ids,
            )
            return source_stock_context

        with patch.object(
                type(header),
                "_ensure_smart_destination_cache",
                return_value=None,
        ), patch.object(
                type(header),
                "_validate_smart_transfer_header",
                return_value=None,
        ), patch.object(
                type(header),
                "_get_smart_sales_cache_warning_action_if_needed",
                return_value=False,
        ), patch.object(
                type(header),
                "_get_smart_candidate_source_stock_context",
                autospec=True,
                side_effect=resumed_source_context,
        ), patch.object(
                type(header),
                "_fetch_destination_smart_rows",
                return_value=[],
        ) as fetch_rows, patch.object(
                type(header),
                "_apply_smart_transfer_rows",
                return_value={
                    "created": 0,
                    "updated": 0,
                    "dropout_excluded": 0,
                    "missing": 0,
                    "no_stock": 0,
                },
        ):
            action = warning.action_continue_anyway()

        fetch_rows.assert_called_once_with(
            source_stock_context=source_stock_context
        )
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "warning")

    def test_zero_source_stock_warning_stores_only_ids_and_opens_list_on_demand(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        products = self._get_existing_smart_products_or_skip(11)

        action = self.env["ab_transfer_smart_zero_stock_warning"]._open_warning(
            header.from_store_id,
            products,
            header=header,
        )
        warning = self.env[action["res_model"]].browse(action["res_id"])

        self.assertEqual(warning.zero_product_ids, products.ids)
        self.assertEqual(warning.zero_product_count, 11)
        self.assertNotIn("product_ids", warning._fields)
        self.assertNotIn("page_product_ids", warning._fields)

        warning_view = self.env.ref(
            "ab_transfer_smart.ab_transfer_smart_zero_stock_warning_view_form"
        )
        warning_arch = etree.fromstring(warning_view.arch_db)
        self.assertFalse(warning_arch.xpath("//field[@name='zero_product_ids']"))
        self.assertFalse(warning_arch.xpath("//field[@name='page_product_ids']"))
        self.assertTrue(
            warning_arch.xpath(
                "//button[@name='action_view_zero_stock_products']"
            )
        )

        products_action = warning.action_view_zero_stock_products()
        self.assertEqual(products_action["res_model"], "ab_product")
        self.assertEqual(products_action["view_mode"], "list")
        self.assertEqual(products_action["target"], "new")
        self.assertEqual(products_action["domain"], [("id", "in", products.ids)])
        self.assertFalse(products_action["context"]["create"])
        self.assertFalse(products_action["context"]["edit"])
        self.assertFalse(products_action["context"]["delete"])

    def test_wizard_generation_validation_opens_zero_stock_warning(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        product_serial = int(product.eplus_serial)
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "company_id": header.company_id.id,
            "target_product_ids": [(6, 0, product.ids)],
        })
        source_stock_context = {
            "products_by_serial": {product_serial: product},
            "source_stock_by_serial": {product_serial: 0.0},
        }

        with patch.object(
                type(header),
                "_validate_smart_transfer_header",
                return_value=None,
        ), patch.object(
                type(header),
                "_get_smart_candidate_source_stock_context",
                return_value=source_stock_context,
        ):
            action = wizard._get_calculation_validation_error_action()
            skipped_action = wizard.with_context(
                skip_smart_zero_source_stock_warning=True,
                smart_ignored_zero_source_product_ids=product.ids,
            )._get_calculation_validation_error_action()

        self.assertEqual(
            action["res_model"],
            "ab_transfer_smart_zero_stock_warning",
        )
        warning = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(warning.zero_product_ids, product.ids)
        self.assertEqual(warning.zero_product_count, 1)
        self.assertEqual(warning.smart_wizard_id, wizard)
        self.assertFalse(warning.header_id)

        self.assertFalse(skipped_action)
        self.assertTrue(
            wizard.with_context(
                skip_smart_zero_source_stock_warning=True,
                smart_ignored_zero_source_product_ids=product.ids,
            )._get_calculation_context()["skip_smart_zero_source_stock_warning"]
        )
        self.assertEqual(
            wizard.with_context(
                smart_ignored_zero_source_product_ids=product.ids,
            )._get_calculation_context()[
                "smart_ignored_zero_source_product_ids"
            ],
            product.ids,
        )

    def test_wizard_generation_validation_skips_domain_zero_stock_warning(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        product_serial = int(product.eplus_serial)
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "company_id": header.company_id.id,
            "smart_product_domain": repr([("id", "=", product.id)]),
        })
        source_stock_context = {
            "products_by_serial": {product_serial: product},
            "source_stock_by_serial": {product_serial: 0.0},
        }

        with patch.object(
                type(header),
                "_validate_smart_transfer_header",
                return_value=None,
        ), patch.object(
                type(header),
                "_get_smart_candidate_source_stock_context",
                return_value=source_stock_context,
        ):
            action = wizard._get_calculation_validation_error_action()

        self.assertFalse(action)

    def test_wizard_zero_stock_continue_resumes_generation_with_skip_context(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "company_id": header.company_id.id,
            "target_product_ids": [(6, 0, product.ids)],
        })
        warning_action = self.env[
            "ab_transfer_smart_zero_stock_warning"
        ]._open_warning(
            header.from_store_id,
            product,
            smart_wizard=wizard,
        )
        warning = self.env[warning_action["res_model"]].browse(
            warning_action["res_id"]
        )

        def resume_generation(resumed_wizard):
            self.assertEqual(resumed_wizard, wizard)
            self.assertTrue(
                resumed_wizard.env.context.get(
                    "skip_smart_zero_source_stock_warning"
                )
            )
            self.assertEqual(
                resumed_wizard.env.context.get(
                    "smart_ignored_zero_source_product_ids"
                ),
                product.ids,
            )
            return {"resumed": True}

        with patch.object(
                type(wizard),
                "action_generate_transfers",
                autospec=True,
                side_effect=resume_generation,
        ):
            action = warning.action_continue_anyway()

        self.assertEqual(action, {"resumed": True})

    def test_target_product_with_no_source_stock_does_not_create_smart_line(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        target_product = self._create_smart_product("SMART-ZERO-STOCK-TARGET", 99017, uom)
        header.target_product_ids = [(6, 0, target_product.ids)]

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={99017: 0},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={},
        ), patch.object(
                type(header),
                "_prepare_smart_line_vals",
                return_value={},
        ):
            result = header._apply_smart_transfer_rows([
                (99017, "P017", "Target", 8102, 0, 0, 0, 0, 0),
            ])

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["no_stock"], 1)
        self.assertFalse(header.smart_line_ids)

    def test_apply_smart_transfer_rows_orders_smart_lines_by_product_location(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product_b = self._create_smart_product("SMART-LOC-B", 99202, uom, location="B-01")
        product_a = self._create_smart_product("SMART-LOC-A", 99201, uom, location="A-01")
        header.target_product_ids = [(6, 0, (product_b | product_a).ids)]

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={99201: 50, 99202: 50},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={},
        ), patch.object(
                type(header),
                "_prepare_smart_line_vals",
                return_value={
                    "qty": 5,
                    "expiry_date": fields.Date.today(),
                    "uom_id": uom.id,
                    "smart_source_stock_qty": 50,
                },
        ):
            result = header._apply_smart_transfer_rows([
                (99202, "P002", "Product B", 8102, 0, 90, 0, 0, 90),
                (99201, "P001", "Product A", 8102, 0, 90, 0, 0, 90),
            ])

        self.assertEqual(result["created"], 2)
        self.assertEqual(header.smart_line_ids.mapped("smart_product_location"), ["A-01", "B-01"])

    def test_apply_smart_transfer_rows_marks_dropout_coverage_lines_excluded(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-DROPOUT-P1", 99012, uom)
        header.write({
            "smart_stock_method": SMART_STOCK_METHOD_NORMAL,
            "smart_dropout_coverage": 75,
            "target_product_ids": [(6, 0, product.ids)],
        })

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={99012: 50},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={},
        ), patch.object(
                type(header),
                "_prepare_smart_line_vals",
                return_value={
                    "qty": 20,
                    "expiry_date": fields.Date.today(),
                    "uom_id": uom.id,
                    "smart_source_stock_qty": 50,
                },
        ):
            result = header._apply_smart_transfer_rows([
                (99012, "P002", "Product", 8102, 80, 0, 0, 0, 150),
            ])

        self.assertEqual(result["dropout_excluded"], 1)
        self.assertEqual(header.smart_line_ids.exclusion_reason, "dropout_coverage")

    def test_prepare_smart_line_vals_uses_total_source_stock_without_class_id(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-TOTAL-SOURCE", 99013, uom)

        with patch.object(
                type(header),
                "_get_source_inventory_rows",
                side_effect=AssertionError("Planning must not read source batches."),
        ):
            vals = header._prepare_smart_line_vals(
                product,
                required_qty=8,
                source_stock_qty=10,
                destination_stock_qty=0,
                month1_sales=30,
                month2_sales=30,
                month3_sales=30,
                destination_required_qty=8,
                other_required_qty=0,
                total_required_qty=8,
            )

        self.assertNotIn("class_id", vals)
        self.assertNotIn("expiry_date", vals)
        self.assertEqual(vals["qty"], 8)
        self.assertEqual(vals["smart_source_stock_qty"], 10)

    def test_smart_line_planning_create_does_not_require_expiry_or_live_inventory(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-TOTAL-LINE", 990131, uom)

        with patch.object(type(header), "_get_sql_connection") as sql_connection:
            line = self.env["ab_transfer_smart_line"].create({
                "header_id": header.id,
                "product_id": product.id,
                "qty": 5,
                "uom_id": uom.id,
            })

        sql_connection.assert_not_called()
        self.assertFalse(line.class_id)
        self.assertFalse(line.expiry_date)
        self.assertEqual(line.inventory_json, {"data": []})

    def test_source_opening_stock_cache_keeps_history_and_positive_rows_only(self):
        store = self._create_store_or_skip({
            "name": "Smart Source Cache Store",
            "code": "SMART-SRC-CACHE",
            "eplus_serial": 8321,
            "allow_sale": True,
        })
        SourceCache = self.env["ab_transfer_smart_source_stock_cache"].sudo()
        today = fields.Date.context_today(SourceCache)
        old_day = today - timedelta(days=1)
        old_line = SourceCache.create({
            "store_id": store.id,
            "product_eplus_serial": 990170,
            "stock_qty": 3,
            "cache_date": old_day,
        })

        with patch.object(
                type(SourceCache),
                "_fetch_store_stock_rows",
                return_value={990171: 8, 990172: 0, 990173: -2},
        ):
            created_count = SourceCache.refresh_store_cache(store, force=False)

        today_lines = SourceCache.search([
            ("store_id", "=", store.id),
            ("cache_date", "=", today),
        ])
        self.assertEqual(created_count, 1)
        self.assertEqual(today_lines.mapped("product_eplus_serial"), [990171])
        self.assertEqual(today_lines.stock_qty, 8)
        self.assertTrue(old_line.exists())

        with patch.object(
                type(SourceCache),
                "_fetch_store_stock_rows",
                return_value={990174: 11},
        ):
            force_count = SourceCache.refresh_store_cache(store, force=True)

        today_lines = SourceCache.search([
            ("store_id", "=", store.id),
            ("cache_date", "=", today),
        ])
        self.assertEqual(force_count, 1)
        self.assertEqual(today_lines.mapped("product_eplus_serial"), [990174])
        self.assertTrue(old_line.exists())

        with patch.object(
                type(SourceCache),
                "_fetch_store_stock_rows",
                side_effect=UserError("source unavailable"),
        ):
            with self.assertRaises(UserError):
                SourceCache.refresh_store_cache(store, force=True)

        self.assertTrue(old_line.exists())
        self.assertEqual(today_lines.exists().mapped("product_eplus_serial"), [990174])

    def test_source_opening_stock_cache_rechecks_after_refresh_lock(self):
        store = self._create_store_or_skip({
            "name": "Smart Source Cache Lock Store",
            "code": "SMART-SRC-CACHE-LOCK",
            "eplus_serial": 8322,
            "allow_sale": True,
        })
        SourceCache = self.env["ab_transfer_smart_source_stock_cache"].sudo()

        with patch.object(
                type(SourceCache),
                "_has_today_cache",
                side_effect=[False, True],
        ) as has_cache, patch.object(
                type(SourceCache),
                "_lock_source_stock_cache_refresh",
        ) as refresh_lock, patch.object(
                type(SourceCache),
                "_fetch_store_stock_rows",
                side_effect=AssertionError("cache was filled by another worker"),
        ) as fetch_rows:
            created_count = SourceCache.refresh_store_cache(store, force=False)

        self.assertEqual(created_count, 0)
        self.assertEqual(has_cache.call_count, 2)
        refresh_lock.assert_called_once()
        fetch_rows.assert_not_called()

    def test_smart_source_inventory_row_keeps_transfer_price_semantics(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        sql_row = (
            741,
            int(product.eplus_serial),
            int(header.from_store_id.eplus_serial),
            10.0,
            240.0,
            10.0,
            3.0,
            0.5,
            fields.Date.today(),
            3,
            2,
            24,
        )

        inventory_row = header._prepare_smart_source_inventory_row(
            sql_row,
            product,
        )

        self.assertEqual(inventory_row["source_id"], 741)
        self.assertEqual(inventory_row["qty"], 10)
        self.assertEqual(inventory_row["qty_in_small_unit"], 240)
        self.assertEqual(inventory_row["price"], 240)
        self.assertEqual(inventory_row["cost"], 72)
        self.assertEqual(inventory_row["sell_tax"], 12)
        self.assertEqual(inventory_row["pharm_price"], 72)

    def test_source_inventory_batch_reads_all_products_in_one_query(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        product_serial = int(product.eplus_serial)
        sql_row = (
            744,
            product_serial,
            int(header.from_store_id.eplus_serial),
            15.0,
            12.0,
            12.0,
            9.0,
            1.0,
            fields.Date.today(),
            1,
            1,
            1,
        )
        cursor = MagicMock()
        cursor.fetchall.return_value = [sql_row]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        connection_context = MagicMock()
        connection_context.__enter__.return_value = connection

        with patch.object(
                type(header),
                "_get_sql_connection",
                return_value=connection_context,
        ):
            rows_by_product = (
                header._get_smart_source_inventory_rows_by_product({
                    product_serial: product,
                })
            )

        cursor.execute.assert_called_once()
        self.assertEqual(len(rows_by_product[product.id]), 1)
        self.assertEqual(rows_by_product[product.id][0]["source_id"], 744)
        self.assertEqual(rows_by_product[product.id][0]["qty"], 12)

    def test_smart_line_prefetched_inventory_avoids_external_recompute(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        inventory_payload = {
            "data": [{
                **self._smart_source_row(743, 12),
                "exp_date": str(fields.Date.today()),
                "price": 15.0,
                "cost": 9.0,
                "sell_tax": 1.0,
                "pharm_price": 9.0,
            }],
        }

        with patch.object(
                type(header),
                "_get_sql_connection",
        ) as sql_connection:
            line = self.env["ab_transfer_smart_line"].with_context(
                smart_prefetched_source_inventory_json_by_product={
                    product.id: inventory_payload,
                }
            ).create({
                "header_id": header.id,
                "product_id": product.id,
                "qty": 5,
                "expiry_date": fields.Date.today(),
                "uom_id": product.uom_id.id,
            })

        sql_connection.assert_not_called()
        self.assertEqual(line.inventory_json, inventory_payload)
        self.assertEqual(line.sell_price, 15)
        self.assertEqual(line.cost, 9)
        self.assertEqual(line.purchase_price, 9)

        chunk_header = self.env["ab_transfer_header"].create({
            "from_store_id": header.from_store_id.id,
            "to_store_id": header.to_store_id.id,
            "user_id": header.user_id.id,
        })
        with patch.object(
                type(header),
                "_get_sql_connection",
        ) as move_sql_connection:
            line.with_context(
                smart_prefetched_source_inventory_json_by_product={
                    product.id: inventory_payload,
                }
            ).write({"header_id": chunk_header.id})

        move_sql_connection.assert_not_called()
        self.assertEqual(line.header_id, chunk_header)
        self.assertEqual(line.inventory_json, inventory_payload)

    def test_prepare_automatic_smart_qty_rounds_without_changing_need_context(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        uom = self._create_smart_uom()
        product = SimpleNamespace(
            id=99031,
            display_name="SMART-MULTIPLE-AUTO",
            uom_id=uom,
            min_sale_purchase_qty=24,
        )

        with patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[self._smart_source_row(731, 100)],
        ):
            vals = header._prepare_smart_line_vals(
                product,
                required_qty=30,
                source_stock_qty=100,
                destination_stock_qty=5,
                month1_sales=30,
                month2_sales=20,
                month3_sales=10,
                destination_required_qty=30,
                other_required_qty=20,
                total_required_qty=50,
            )

        self.assertEqual(vals["qty"], 48)
        self.assertEqual(vals["smart_qty_before_int"], 30)
        self.assertEqual(vals["smart_source_stock_qty"], 100)
        self.assertEqual(vals["smart_destination_stock_qty"], 5)
        self.assertEqual(vals["smart_month1_sales"], 30)
        self.assertEqual(vals["smart_month2_sales"], 20)
        self.assertEqual(vals["smart_month3_sales"], 10)
        self.assertEqual(vals["smart_need_destination_store"], 30)
        self.assertEqual(vals["smart_need_other_store"], 20)
        self.assertEqual(vals["smart_total_need"], 50)

    def test_prepare_automatic_multiple_can_exceed_source_stock(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        uom = self._create_smart_uom()
        product = SimpleNamespace(
            id=99032,
            display_name="SMART-MULTIPLE-STOCK",
            uom_id=uom,
            min_sale_purchase_qty=24,
        )

        with patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[self._smart_source_row(732, 10)],
        ):
            vals = header._prepare_smart_line_vals(
                product,
                required_qty=10,
                source_stock_qty=10,
                destination_stock_qty=0,
                month1_sales=10,
                month2_sales=10,
                month3_sales=10,
                destination_required_qty=10,
                other_required_qty=0,
                total_required_qty=10,
            )

        self.assertEqual(vals["smart_qty_before_int"], 10)
        self.assertEqual(vals["smart_source_stock_qty"], 10)
        self.assertEqual(vals["qty"], 24)

    def test_prepare_manual_qty_is_not_rounded_to_product_multiple(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        uom = self._create_smart_uom()
        product = SimpleNamespace(
            id=99033,
            display_name="SMART-MULTIPLE-MANUAL",
            uom_id=uom,
            min_sale_purchase_qty=24,
        )

        with patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[self._smart_source_row(733, 10)],
        ):
            vals = header._prepare_smart_line_vals(
                product,
                required_qty=10,
                source_stock_qty=10,
                destination_stock_qty=4,
                month1_sales=10,
                month2_sales=10,
                month3_sales=10,
                destination_required_qty=10,
                other_required_qty=5,
                total_required_qty=15,
                manual_qty=25,
            )

        self.assertEqual(vals["qty"], 25)
        self.assertEqual(vals["smart_qty_before_int"], 10)
        self.assertEqual(vals["smart_need_destination_store"], 10)
        self.assertEqual(vals["smart_need_other_store"], 5)
        self.assertEqual(vals["smart_total_need"], 15)

    def test_expected_source_stock_subtracts_active_smart_reservations(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-EXPECTED-STOCK", 99018, uom)
        reference_line = self._create_smart_line(
            header,
            product,
            uom,
            qty=6,
            smart_source_stock_qty=50,
        )

        active_preparation = self._create_smart_header_for_source(header, "SMART-EXP-PREP", 8301)
        self._create_smart_line(active_preparation, product, uom, qty=4)
        active_preparation.write({"smart_stage": SMART_STAGE_STORE_PREPARATION})

        active_revision = self._create_smart_header_for_source(header, "SMART-EXP-REV", 8302)
        self._create_smart_line(active_revision, product, uom, qty=3)
        active_revision.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        active_pre_submit = self._create_smart_header_for_source(header, "SMART-EXP-PRE-SUB", 8303)
        self._create_smart_line(active_pre_submit, product, uom, qty=2)
        active_pre_submit.write({"smart_stage": SMART_STAGE_PRE_SUBMIT})

        active_submit = self._create_smart_header_for_source(header, "SMART-EXP-SUB-STAGE", 8307)
        self._create_smart_line(active_submit, product, uom, qty=5)
        active_submit.write({"smart_stage": SMART_STAGE_SUBMIT})

        purchase_preparation = self._create_smart_header_for_source(header, "SMART-EXP-PUR", 8304)
        self._create_smart_line(purchase_preparation, product, uom, qty=7)

        submitted = self._create_smart_header_for_source(header, "SMART-EXP-SUB", 8305)
        self._create_smart_line(submitted, product, uom, qty=11)
        submitted.write({
            "smart_stage": SMART_STAGE_SUBMIT,
            "is_submitted": True,
        })

        excluded = self._create_smart_header_for_source(header, "SMART-EXP-EXC", 8306)
        self._create_smart_line(excluded, product, uom, qty=13, exclusion_reason="expired")
        excluded.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        reserved_qty = self.env["ab_transfer_header"]._read_smart_active_reserved_qty_by_product_store(
            [product.id],
            [header.from_store_id.id],
        )

        self.assertEqual(reserved_qty[(product.id, header.from_store_id.id)], 25)
        self.assertEqual(reference_line.smart_expected_source_stock_qty, 25)

    def test_expected_source_stock_ignores_yesterday_smart_reservations(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-EXPECTED-YESTERDAY", 99019, uom)
        reference_line = self._create_smart_line(
            header,
            product,
            uom,
            qty=6,
            smart_source_stock_qty=50,
        )
        yesterday = fields.Date.context_today(header) - timedelta(days=1)

        for index, stage in enumerate(
                (
                    SMART_STAGE_STORE_PREPARATION,
                    SMART_STAGE_STORE_REVISION,
                    SMART_STAGE_PRE_SUBMIT,
                    SMART_STAGE_SUBMIT,
                ),
                start=1,
        ):
            yesterday_header = self._create_smart_header_for_source(
                header,
                "SMART-EXP-YEST-%s" % index,
                8310 + index,
            )
            yesterday_line = self._create_smart_line(yesterday_header, product, uom, qty=index)
            yesterday_line.write({"create_day": yesterday})
            yesterday_header.write({"smart_stage": stage})

        reserved_qty = self.env["ab_transfer_header"]._read_smart_active_reserved_qty_by_product_store(
            [product.id],
            [header.from_store_id.id],
        )

        self.assertNotIn((product.id, header.from_store_id.id), reserved_qty)
        self.assertEqual(reference_line.smart_expected_source_stock_qty, 50)

    def test_smart_line_duplicate_stage_transition_blocks_same_source_day(self):
        header = self._create_smart_header()
        duplicate_header = self.env["ab_transfer_header"].create({
            "from_store_id": header.from_store_id.id,
            "to_store_id": header.to_store_id.id,
            "user_id": header.user_id.id,
        })
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-DUP-STAGE", 99181, uom)
        self._create_smart_line(header, product, uom, qty=10)
        self._create_smart_line(duplicate_header, product, uom, qty=5)

        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})
        with self.assertRaisesRegex(ValidationError, "Duplicated transfer products found"):
            duplicate_header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        duplicate_header.invalidate_recordset(["smart_stage"])
        self.assertEqual(duplicate_header.smart_stage, SMART_STAGE_PURCHASE_PREPARATION)

    def test_smart_line_duplicate_constraint_skips_module_schema_check_context(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-DUP-UPGRADE", 99186, uom)
        line = self._create_smart_line(header, product, uom, qty=10)

        with patch.object(
                type(line),
                "_check_duplicate_transfer_lines",
                side_effect=AssertionError("Duplicate helper should not run during schema checks."),
        ):
            line.with_context(models_to_check=True)._constrains_duplicate_transfer_lines()
            line.with_context(module="ab_transfer_smart")._constrains_duplicate_transfer_lines()

    def test_smart_line_duplicate_allows_different_source_type(self):
        header = self._create_smart_header()
        duplicate_header = self.env["ab_transfer_header"].create({
            "from_store_id": header.from_store_id.id,
            "to_store_id": header.to_store_id.id,
            "user_id": header.user_id.id,
        })
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-DUP-SOURCE", 99182, uom)
        self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            source_type=SMART_LINE_SOURCE_DOMAIN,
        )
        self._create_smart_line(
            duplicate_header,
            product,
            uom,
            qty=5,
            source_type=SMART_LINE_SOURCE_WIZARD,
        )

        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})
        duplicate_header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        self.assertEqual(duplicate_header.smart_stage, SMART_STAGE_STORE_REVISION)

    def test_smart_line_duplicate_ignores_exclusion_reason(self):
        header = self._create_smart_header()
        duplicate_header = self.env["ab_transfer_header"].create({
            "from_store_id": header.from_store_id.id,
            "to_store_id": header.to_store_id.id,
            "user_id": header.user_id.id,
        })
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-DUP-EXCLUDED", 99183, uom)
        excluded_line = self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            exclusion_reason="expired",
        )
        self._create_smart_line(duplicate_header, product, uom, qty=5)
        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})
        duplicate_header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        with self.assertRaisesRegex(ValidationError, "Duplicated transfer products found"):
            excluded_line.write({"exclusion_reason": False})

        excluded_line.invalidate_recordset(["exclusion_reason"])
        self.assertEqual(excluded_line.exclusion_reason, "expired")

    def test_apply_smart_transfer_rows_sets_line_source_type(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        explicit_product = self._create_smart_product("SMART-SOURCE-WIZARD", 99184, uom)
        domain_product = self._create_smart_product("SMART-SOURCE-DOMAIN", 99185, uom)
        header.write({
            "smart_stock_method": SMART_STOCK_METHOD_NORMAL,
            "smart_product_line_ids": [(0, 0, {
                "product_id": explicit_product.id,
                "qty": 6,
            })],
            "target_product_ids": [(6, 0, domain_product.ids)],
        })

        with patch.object(
                type(header),
                "_get_smart_source_opening_stock_by_product_serial",
                return_value={99184: 20, 99185: 20},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={},
        ), patch.object(
                type(header),
                "_prepare_smart_line_vals",
                return_value={
                    "qty": 5,
                    "expiry_date": fields.Date.today(),
                    "uom_id": uom.id,
                    "smart_source_stock_qty": 20,
                },
        ):
            result = header._apply_smart_transfer_rows([
                (99184, "P184", "Explicit", 8102, 0, 90, 0, 0, 90),
                (99185, "P185", "Domain", 8102, 0, 90, 0, 0, 90),
            ])

        self.assertEqual(result["created"], 2)
        source_type_by_product = {
            line.product_id.id: line.source_type
            for line in header.smart_line_ids
        }
        self.assertEqual(source_type_by_product[explicit_product.id], SMART_LINE_SOURCE_WIZARD)
        self.assertEqual(source_type_by_product[domain_product.id], SMART_LINE_SOURCE_DOMAIN)

    def test_fetch_destination_smart_rows_reads_today_cache(self):
        header = self._create_smart_header()
        today = fields.Date.context_today(header)
        self.env["ab_transfer_smart_stock_cache"].create({
            "store_id": header.to_store_id.id,
            "product_eplus_serial": 99061,
            "stock_qty": 80,
            "cache_date": today,
        })
        self.env["ab_transfer_smart_sales_cache"].create({
            "store_id": header.to_store_id.id,
            "product_eplus_serial": 99061,
            "month1_sales": 30,
            "month2_sales": 20,
            "month3_sales": 10,
            "total_3_months_sales": 60,
            "cache_date": today,
        })

        with patch.object(
                type(header),
                "_get_smart_target_product_serials_with_source_stock",
                return_value=[99061, 99062],
        ), patch.object(
                type(header),
                "_ensure_smart_destination_cache",
                return_value=None,
        ):
            rows = header._fetch_destination_smart_rows()

        rows_by_serial = {row[SMART_ROW_PRODUCT_SERIAL]: row for row in rows}
        self.assertEqual(rows_by_serial[99061][SMART_ROW_BRANCH_STOCK_QTY], 80)
        self.assertEqual(rows_by_serial[99061][SMART_ROW_LAST_MONTH_SALES], 30)
        self.assertEqual(rows_by_serial[99061][SMART_ROW_PREVIOUS_MONTH_SALES], 20)
        self.assertEqual(rows_by_serial[99061][SMART_ROW_THIRD_MONTH_SALES], 10)
        self.assertEqual(rows_by_serial[99061][SMART_ROW_TOTAL_3_MONTHS_SALES], 60)
        self.assertEqual(rows_by_serial[99062][SMART_ROW_BRANCH_STOCK_QTY], 0)
        self.assertEqual(rows_by_serial[99062][SMART_ROW_TOTAL_3_MONTHS_SALES], 0)

    def test_readonly_destination_rows_match_today_cache_without_live_fetch(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        today = fields.Date.context_today(header)
        serial = 99511
        self.env["ab_transfer_smart_stock_cache"].create({
            "store_id": header.to_store_id.id,
            "product_eplus_serial": serial,
            "stock_qty": 12,
            "cache_date": today,
        })
        self.env["ab_transfer_smart_sales_cache"].create({
            "store_id": header.to_store_id.id,
            "product_eplus_serial": serial,
            "month1_sales": 30,
            "month2_sales": 20,
            "month3_sales": 10,
            "total_3_months_sales": 60,
            "cache_date": today,
        })
        StockCache = self.env["ab_transfer_smart_stock_cache"]
        SalesCache = self.env["ab_transfer_smart_sales_cache"]

        with patch.object(
                type(header),
                "_get_smart_target_product_serials_with_source_stock",
                return_value=[serial],
        ), patch.object(
                type(StockCache),
                "_fetch_store_stock_rows",
        ) as fetch_stock, patch.object(
                type(SalesCache),
                "_fetch_store_sales_rows",
        ) as fetch_sales:
            rows = header._fetch_destination_smart_rows_readonly()

        fetch_stock.assert_not_called()
        fetch_sales.assert_not_called()
        self.assertEqual(
            rows[0],
            (serial, "", "", header.to_store_id.eplus_serial, 12.0, 30.0, 20.0, 10.0, 60.0),
        )

    def test_readonly_destination_rows_use_live_selects_when_today_cache_is_absent(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        serial = 99512
        StockCache = self.env["ab_transfer_smart_stock_cache"]
        SalesCache = self.env["ab_transfer_smart_sales_cache"]

        with patch.object(
                type(header),
                "_get_smart_target_product_serials_with_source_stock",
                return_value=[serial],
        ), patch.object(
                type(StockCache),
                "search_count",
                return_value=0,
        ), patch.object(
                type(SalesCache),
                "search_count",
                return_value=0,
        ), patch.object(
                type(StockCache),
                "_fetch_store_stock_rows",
                return_value={serial: 9.0},
        ) as fetch_stock, patch.object(
                type(SalesCache),
                "_fetch_store_sales_rows",
                return_value={
                    serial: {
                        "month1_sales": 6.0,
                        "month2_sales": 5.0,
                        "month3_sales": 4.0,
                        "total_3_months_sales": 15.0,
                    },
                },
        ) as fetch_sales:
            rows = header._fetch_destination_smart_rows_readonly()

        fetch_stock.assert_called_once_with(header.to_store_id)
        fetch_sales.assert_called_once_with(header.to_store_id)
        self.assertEqual(
            rows[0],
            (serial, "", "", header.to_store_id.eplus_serial, 9.0, 6.0, 5.0, 4.0, 15.0),
        )

    def test_stock_cache_refresh_skips_zero_balance_rows(self):
        store = self._create_store_or_skip({
            "name": "Smart Nonzero Stock Cache Store",
            "code": "SMART-NONZERO-CACHE",
            "eplus_serial": 8302,
            "allow_sale": True,
        })
        StockCache = self.env["ab_transfer_smart_stock_cache"]

        with patch.object(
                type(StockCache),
                "_fetch_store_stock_rows",
                return_value={
                    99111: 10.0,
                    99112: 0.0,
                    99113: -2.0,
                },
        ):
            created_count = StockCache.refresh_store_cache(store, force=True)

        cached_stock = {
            row.product_eplus_serial: row.stock_qty
            for row in StockCache.search([("store_id", "=", store.id)])
        }
        self.assertEqual(created_count, 2)
        self.assertEqual(cached_stock, {
            99111: 10.0,
            99113: -2.0,
        })

    def test_destination_stock_cache_fetch_uses_converted_uom_quantity(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        store = header.to_store_id
        StockCache = self.env["ab_transfer_smart_stock_cache"]
        cursor = MagicMock()
        cursor.fetchall.return_value = [(990181, 8303, 10.0)]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        connection_context = MagicMock()
        connection_context.__enter__.return_value = connection

        with patch.object(
                type(StockCache),
                "_get_store_sql_id",
                return_value=8303,
        ), patch.object(
                type(StockCache),
                "_get_store_server",
                return_value="127.0.0.1",
        ), patch.object(
                type(StockCache),
                "connect_eplus",
                return_value=connection_context,
        ):
            stock_rows = StockCache._fetch_store_stock_rows(store)

        query = cursor.execute.call_args[0][0]
        self.assertIn("INNER JOIN item_catalog ic ON ic.itm_id = main.itm_id", query)
        self.assertIn("/ CAST(ic.itm_unit1_unit3 AS decimal(18,4))", query)
        self.assertEqual(stock_rows, {990181: 10.0})

    def test_destination_required_qty_uses_converted_destination_stock(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        header.smart_days = 45
        header.smart_stock_method = SMART_STOCK_METHOD_NORMAL
        product = SimpleNamespace(eplus_serial=990182)
        row = (
            int(product.eplus_serial),
            "",
            "",
            int(header.to_store_id.eplus_serial),
            10.0,
            20.0,
            20.0,
            20.0,
            60.0,
        )

        context = header._get_smart_required_context_from_row(
            row,
            {int(product.eplus_serial): product},
        )

        self.assertEqual(context["planned_qty"], 30.0)
        self.assertEqual(context["destination_stock_qty"], 10.0)
        self.assertEqual(context["required_qty"], 20.0)

    def test_smart_cache_product_fields_resolve_from_eplus_serial(self):
        store = self._create_store_or_skip({
            "name": "Smart Product Cache Store",
            "code": "SMART-PROD-CACHE",
            "eplus_serial": 8301,
            "allow_sale": True,
        })
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-CACHE-PRODUCT", 99101, uom)
        today = fields.Date.context_today(self.env["ab_transfer_smart_stock_cache"])

        stock_cache = self.env["ab_transfer_smart_stock_cache"].create({
            "store_id": store.id,
            "product_eplus_serial": 99101,
            "stock_qty": 10,
            "cache_date": today,
        })
        sales_cache = self.env["ab_transfer_smart_sales_cache"].create({
            "store_id": store.id,
            "product_eplus_serial": 99101,
            "month1_sales": 3,
            "month2_sales": 2,
            "month3_sales": 1,
            "total_3_months_sales": 6,
            "cache_date": today,
        })
        source_cache = self.env["ab_transfer_smart_source_stock_cache"].create({
            "store_id": store.id,
            "product_eplus_serial": 99101,
            "stock_qty": 12,
            "cache_date": today,
        })
        missing_product_cache = self.env["ab_transfer_smart_stock_cache"].create({
            "store_id": store.id,
            "product_eplus_serial": 99102,
            "stock_qty": 5,
            "cache_date": today,
        })

        self.assertEqual(stock_cache.product_id, product)
        self.assertEqual(stock_cache.product_code, product.code)
        self.assertEqual(sales_cache.product_id, product)
        self.assertEqual(sales_cache.product_code, product.code)
        self.assertEqual(source_cache.product_id, product)
        self.assertEqual(source_cache.product_code, product.code)
        self.assertFalse(missing_product_cache.product_id)
        self.assertFalse(missing_product_cache.product_code)

    def test_header_refresh_destination_cache_forces_refresh(self):
        header = self._create_smart_header()
        StockCache = self.env["ab_transfer_smart_stock_cache"]

        with patch.object(
                type(StockCache),
                "refresh_stores_cache",
                return_value={"stores": 1, "stock_rows": 2, "sales_rows": 3},
        ) as refresh:
            action = header.action_smart_refresh_destination_cache()

        refresh.assert_called_once()
        self.assertEqual(refresh.call_args.kwargs["force"], True)
        self.assertEqual(refresh.call_args.args[0], header.to_store_id)
        self.assertEqual(action["params"]["type"], "success")

    def test_stage_buttons_return_soft_reload_notifications(self):
        header = self._create_smart_header()

        action = header.action_smart_to_store_preparation()
        self.assertEqual(header.smart_stage, SMART_STAGE_STORE_PREPARATION)
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["next"]["tag"], "soft_reload")

        action = header.action_smart_to_store_revision()
        self.assertEqual(header.smart_stage, SMART_STAGE_STORE_REVISION)
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["next"]["tag"], "soft_reload")

        with patch.object(
                type(header),
                "_copy_smart_lines_to_transfer_lines",
                return_value={"created": 0, "updated": 0, "excluded": 0},
        ):
            action = header.action_smart_pre_submit()

        self.assertEqual(header.smart_stage, SMART_STAGE_PRE_SUBMIT)
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["next"]["tag"], "soft_reload")

    def test_store_preparation_blocks_when_other_active_smart_transfer_reserved_stock(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-STORE-PREP-STOCK-BLOCK", 99109, uom)
        self._create_smart_line(header, product, uom, qty=8)

        other_header = self._create_smart_header_for_source(header, "SMART-STORE-PREP-OTHER", 8313)
        self._create_smart_line(other_header, product, uom, qty=5)
        other_header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
                return_value={99109: 10},
        ), self.assertRaisesRegex(UserError, "already reserved"):
            header.action_smart_to_store_preparation()

        self.assertEqual(header.smart_stage, SMART_STAGE_PURCHASE_PREPARATION)
        self.assertFalse(header.line_ids)

    def test_store_manager_can_move_smart_stage_backward_before_submit(self):
        self.env.user.write({
            "group_ids": [(4, self.env.ref("ab_transfer_smart.group_trnasfer_smart_store_manager").id)],
        })
        header = self._create_smart_header_from_existing_records_or_skip()

        header.write({"smart_stage": SMART_STAGE_STORE_PREPARATION})
        action = header.action_smart_back_to_purchase_preparation()
        self.assertEqual(header.smart_stage, SMART_STAGE_PURCHASE_PREPARATION)
        self.assertEqual(action["params"]["next"]["tag"], "soft_reload")

        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})
        action = header.action_smart_back_to_store_preparation()
        self.assertEqual(header.smart_stage, SMART_STAGE_STORE_PREPARATION)
        self.assertEqual(action["params"]["next"]["tag"], "soft_reload")

        header.write({"smart_stage": SMART_STAGE_PRE_SUBMIT})
        action = header.action_smart_back_to_store_revision()
        self.assertEqual(header.smart_stage, SMART_STAGE_STORE_REVISION)
        self.assertEqual(action["params"]["next"]["tag"], "soft_reload")

    def test_backward_stage_move_requires_store_manager_group(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        header.write({"smart_stage": SMART_STAGE_PRE_SUBMIT})

        with self.assertRaises(AccessError):
            header.action_smart_back_to_store_revision()

    def test_store_manager_can_unlink_transfer_lines_when_moving_back_to_revision(self):
        manager_user = self.env["res.users"].sudo().with_context(no_reset_password=True).create({
            "name": "Smart Store Manager",
            "login": "smart_store_manager",
            "email": "smart_store_manager@example.com",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("ab_transfer_smart.group_trnasfer_smart_store_manager").id,
            ])],
        })
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_products_or_skip(1)
        header.write({"smart_stage": SMART_STAGE_PRE_SUBMIT})
        self.env["ab_transfer_line"].create({
            "header_id": header.id,
            "product_id": product.id,
            "class_id": 981,
            "qty": 1,
            "expiry_date": fields.Date.today(),
            "uom_id": product.uom_id.id,
        })

        action = header.with_user(manager_user).action_smart_back_to_store_revision()

        self.assertEqual(action["params"]["next"]["tag"], "soft_reload")
        self.assertEqual(header.smart_stage, SMART_STAGE_STORE_REVISION)
        self.assertFalse(header.line_ids)

    def test_backward_stage_move_is_blocked_after_submit(self):
        self.env.user.write({
            "group_ids": [(4, self.env.ref("ab_transfer_smart.group_trnasfer_smart_store_manager").id)],
        })
        header = self._create_smart_header_from_existing_records_or_skip()
        header.write({
            "smart_stage": SMART_STAGE_PRE_SUBMIT,
            "is_submitted": True,
        })

        with self.assertRaisesRegex(UserError, "Submitted"):
            header.action_smart_back_to_store_revision()

        stage_submit_header = self._create_smart_header_from_existing_records_or_skip()
        stage_submit_header.write({
            "smart_stage": SMART_STAGE_SUBMIT,
        })
        with self.assertRaisesRegex(UserError, "Pre-Submit"):
            stage_submit_header.action_smart_back_to_store_revision()

    def test_header_calculation_returns_danger_after_cache_when_validation_fails(self):
        header = self.env["ab_transfer_header"].new({
            "smart_stage": SMART_STAGE_PURCHASE_PREPARATION,
        })
        calls = []

        def refresh_cache(force=False):
            calls.append("cache")
            return {"stores": 1, "stock_rows": 0, "sales_rows": 0}

        def validate_header():
            calls.append("validate")
            raise UserError("Source store is offline.")

        with patch.object(
                type(header),
                "_refresh_smart_destination_cache",
                side_effect=refresh_cache,
        ), patch.object(
                type(header),
                "_validate_smart_transfer_header",
                side_effect=validate_header,
        ):
            action = header.action_smart_transfer_calculation()

        self.assertEqual(calls, ["cache", "validate"])
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "danger")
        self.assertIn("Source store is offline.", action["params"]["message"])

    def test_wizard_refresh_smart_cache_refreshes_all_destinations(self):
        source = self._create_store_or_skip({
            "name": "Smart Wizard Cache Source",
            "code": "SMART-WCACHE-SRC",
            "eplus_serial": 8201,
            "allow_sale": True,
        })
        destination_1 = self._create_store_or_skip({
            "name": "Smart Wizard Cache Destination 1",
            "code": "SMART-WCACHE-D1",
            "eplus_serial": 8202,
            "allow_sale": True,
        })
        destination_2 = self._create_store_or_skip({
            "name": "Smart Wizard Cache Destination 2",
            "code": "SMART-WCACHE-D2",
            "eplus_serial": 8203,
            "allow_sale": True,
        })
        user = self.env["ab_costcenter"].create({
            "name": "Smart Wizard Cache User",
            "code": "SMARTWCACHEUSR",
            "eplus_serial": 9201,
        })
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": source.id,
            "to_stores_id": [(6, 0, (destination_1 | destination_2).ids)],
            "user_id": user.id,
        })
        StockCache = self.env["ab_transfer_smart_stock_cache"]

        with patch.object(
                type(StockCache),
                "refresh_stores_cache",
                return_value={"stores": 2, "stock_rows": 4, "sales_rows": 5},
        ) as refresh:
            action = wizard.action_refresh_smart_cache()

        refresh.assert_called_once()
        self.assertEqual(refresh.call_args.kwargs["force"], True)
        self.assertEqual(refresh.call_args.args[0], wizard.to_stores_id)
        self.assertEqual(action["params"]["type"], "success")

    def test_wizard_refresh_sales_cache_syncs_missing_days_and_resumes_generation(self):
        wizard = self.env["ab_transfer_smart_wizard"].new({
            "sales_cache_warning_message": "Missing sales cache days",
            "sales_cache_missing_days_count": 2,
        })
        missing_days = [
            fields.Date.today() - timedelta(days=2),
            fields.Date.today() - timedelta(days=1),
        ]
        generated_action = {"type": "ir.actions.act_window", "name": "Generated"}
        SalesPerDay = self.env["ab_sales_per_day"]

        with patch.object(
                type(wizard),
                "_validate_generation_values",
                return_value=None,
        ), patch.object(
                type(wizard),
                "_get_missing_sales_cache_dates_for_destinations",
                side_effect=[missing_days, []],
        ), patch.object(
                type(SalesPerDay),
                "cron_sync_next_sales_day",
                autospec=True,
                return_value=True,
        ) as sync_day, patch.object(
                type(wizard),
                "action_generate_transfers",
                return_value=generated_action,
        ) as generate:
            action = wizard.action_refresh_sales_cache_and_generate()

        self.assertEqual(sync_day.call_count, 2)
        for call, sale_date in zip(sync_day.call_args_list, missing_days):
            self.assertEqual(call.kwargs, {
                "start_date": sale_date,
                "end_date": sale_date,
                "force_resync": False,
            })
        generate.assert_called_once_with()
        self.assertEqual(action, generated_action)
        self.assertFalse(wizard.allow_incomplete_sales_cache)
        self.assertFalse(wizard.sales_cache_warning_message)
        self.assertEqual(wizard.sales_cache_missing_days_count, 0)
        self.assertFalse(wizard.sales_cache_warning_accepted_by)
        self.assertFalse(wizard.sales_cache_warning_accepted_at)

    def test_wizard_refresh_sales_cache_keeps_warning_when_days_remain(self):
        wizard = self.env["ab_transfer_smart_wizard"].new({
            "allow_incomplete_sales_cache": True,
            "sales_cache_warning_message": "Old warning",
            "sales_cache_missing_days_count": 2,
            "sales_cache_warning_accepted_by": self.env.user.id,
            "sales_cache_warning_accepted_at": fields.Datetime.now(),
        })
        missing_day = fields.Date.today() - timedelta(days=1)
        SalesPerDay = self.env["ab_sales_per_day"]
        warning_action = {"type": "ir.actions.act_window", "name": "Warning"}

        with patch.object(
                type(wizard),
                "_validate_generation_values",
                return_value=None,
        ), patch.object(
                type(wizard),
                "_get_missing_sales_cache_dates_for_destinations",
                side_effect=[[missing_day], [missing_day]],
        ), patch.object(
                type(SalesPerDay),
                "cron_sync_next_sales_day",
                autospec=True,
                return_value=False,
        ) as sync_day, patch.object(
                type(wizard),
                "_reopen_wizard_action",
                return_value=warning_action,
        ) as reopen, patch.object(
                type(wizard),
                "action_generate_transfers",
        ) as generate:
            action = wizard.action_refresh_sales_cache_and_generate()

        sync_day.assert_called_once()
        reopen.assert_called_once_with()
        generate.assert_not_called()
        self.assertEqual(action, warning_action)
        self.assertFalse(wizard.allow_incomplete_sales_cache)
        self.assertIn(fields.Date.to_string(missing_day), wizard.sales_cache_warning_message)
        self.assertIn("did not complete", wizard.sales_cache_warning_message)
        self.assertEqual(wizard.sales_cache_missing_days_count, 1)
        self.assertFalse(wizard.sales_cache_warning_accepted_by)
        self.assertFalse(wizard.sales_cache_warning_accepted_at)

    def test_wizard_refresh_sales_cache_resumes_without_resync_when_cache_is_ready(self):
        wizard = self.env["ab_transfer_smart_wizard"].new({
            "sales_cache_warning_message": "Old warning",
            "sales_cache_missing_days_count": 1,
        })
        generated_action = {"type": "ir.actions.act_window", "name": "Generated"}
        SalesPerDay = self.env["ab_sales_per_day"]

        with patch.object(
                type(wizard),
                "_validate_generation_values",
                return_value=None,
        ), patch.object(
                type(wizard),
                "_get_missing_sales_cache_dates_for_destinations",
                side_effect=[[], []],
        ), patch.object(
                type(SalesPerDay),
                "cron_sync_next_sales_day",
                autospec=True,
        ) as sync_day, patch.object(
                type(wizard),
                "action_generate_transfers",
                return_value=generated_action,
        ) as generate:
            action = wizard.action_refresh_sales_cache_and_generate()

        sync_day.assert_not_called()
        generate.assert_called_once_with()
        self.assertEqual(action, generated_action)
        self.assertFalse(wizard.sales_cache_warning_message)

    def test_wizard_view_places_refresh_sales_cache_resume_before_generated_transfers(self):
        view = self.env.ref("ab_transfer_smart.ab_transfer_smart_wizard_view_form")
        arch = etree.fromstring(view.arch_db.encode())
        header_buttons = arch.xpath("//form/header/button")
        button_names = [button.get("name") for button in header_buttons]

        refresh_index = button_names.index("action_refresh_sales_cache_and_generate")
        generated_index = button_names.index("action_open_generated_transfers")
        refresh_button = header_buttons[refresh_index]

        self.assertEqual(refresh_index + 1, generated_index)
        self.assertEqual(refresh_button.get("string"), "Refresh Sales Cache & Resume")
        self.assertIn("sales_cache_warning_message", refresh_button.get("invisible"))

    def test_wizard_generate_ensures_cache_before_warning_check(self):
        source = self._create_store_or_skip({
            "name": "Smart Wizard Ensure Source",
            "code": "SMART-WENS-SRC",
            "eplus_serial": 8401,
            "allow_sale": True,
        })
        destination = self._create_store_or_skip({
            "name": "Smart Wizard Ensure Destination",
            "code": "SMART-WENS-DST",
            "eplus_serial": 8402,
            "allow_sale": True,
        })
        user = self.env["ab_costcenter"].create({
            "name": "Smart Wizard Ensure User",
            "code": "SMARTWENSUSR",
            "eplus_serial": 9301,
        })
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": source.id,
            "to_stores_id": [(6, 0, destination.ids)],
            "user_id": user.id,
        })
        calls = []

        def ensure_cache():
            calls.append("cache")
            return {"stores": 1, "stock_rows": 0, "sales_rows": 0}

        def warning_action():
            calls.append("warning")
            return {"type": "ir.actions.act_window", "name": "Warning"}

        with patch.object(
                type(wizard),
                "_ensure_smart_destination_caches",
                side_effect=ensure_cache,
        ), patch.object(
                type(wizard),
                "_get_sales_cache_warning_action",
                side_effect=warning_action,
        ):
            action = wizard.action_generate_transfers()

        self.assertEqual(calls, ["cache", "warning"])
        self.assertEqual(action["name"], "Warning")

    def test_wizard_generate_returns_danger_after_cache_when_validation_fails(self):
        wizard = self.env["ab_transfer_smart_wizard"].new({})
        calls = []

        def validate_values():
            calls.append("validate_values")

        def ensure_cache():
            calls.append("cache")
            return {"stores": 1, "stock_rows": 0, "sales_rows": 0}

        def ensure_source_cache():
            calls.append("source_cache")
            return {"stores": 1, "stock_rows": 0}

        def warning_action():
            calls.append("warning")
            return False

        def validation_error_action():
            calls.append("calculation_validation")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "danger",
                    "message": "Source store is offline.",
                },
            }

        with patch.object(
                type(wizard),
                "_validate_generation_values",
                side_effect=validate_values,
        ), patch.object(
                type(wizard),
                "_ensure_smart_destination_caches",
                side_effect=ensure_cache,
        ), patch.object(
                type(wizard),
                "_get_sales_cache_warning_action",
                side_effect=warning_action,
        ), patch.object(
                type(wizard),
                "_ensure_smart_source_cache",
                side_effect=ensure_source_cache,
        ), patch.object(
                type(wizard),
                "_get_calculation_validation_error_action",
                side_effect=validation_error_action,
        ):
            action = wizard.action_generate_transfers()

        self.assertEqual(calls, [
            "validate_values",
            "cache",
            "warning",
            "source_cache",
            "calculation_validation",
        ])
        self.assertEqual(action["params"]["type"], "danger")

    def test_smart_line_chunks_uses_items_per_header_size(self):
        Wizard = self.env["ab_transfer_smart_wizard"]

        chunks = list(Wizard._smart_line_chunks([1, 2, 3, 4, 5], 2))

        self.assertEqual(chunks, [[1, 2], [3, 4], [5]])

    def test_smart_location_line_chunks_split_by_location_before_size(self):
        lines = [
            SimpleNamespace(product_id=SimpleNamespace(location=location))
            for location in ["A-01", "A-01", "A-01", "B-01", "B-01"]
        ]

        chunks = list(self.env["ab_transfer_smart_wizard"]._smart_location_line_chunks(lines, 2))

        self.assertEqual(
            [[line.product_id.location for line in chunk] for chunk in chunks],
            [["A-01", "A-01"], ["A-01"], ["B-01", "B-01"]],
        )
        for chunk in chunks:
            self.assertEqual(len({line.product_id.location for line in chunk}), 1)

    def test_wizard_generate_splits_each_store_by_location_then_items_per_header(self):
        source = self._create_store_or_skip({
            "name": "Smart Split Source",
            "code": "SMART-SPLIT-SRC",
            "eplus_serial": 8501,
            "allow_sale": True,
        })
        destination_1 = self._create_store_or_skip({
            "name": "Smart Split Destination 1",
            "code": "SMART-SPLIT-D1",
            "eplus_serial": 8502,
            "allow_sale": True,
        })
        destination_2 = self._create_store_or_skip({
            "name": "Smart Split Destination 2",
            "code": "SMART-SPLIT-D2",
            "eplus_serial": 8503,
            "allow_sale": True,
        })
        user = self.env["ab_costcenter"].create({
            "name": "Smart Split User",
            "code": "SMARTSPLITUSR",
            "eplus_serial": 9501,
        })
        uom = self._create_smart_uom()
        products = self.env["ab_product"].browse()
        for index, location in enumerate(["A-01", "A-01", "A-01", "B-01", "B-01"], start=1):
            products |= self._create_smart_product(
                "SMART-SPLIT-%s" % index,
                99300 + index,
                uom,
                location=location,
            )
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": source.id,
            "to_stores_id": [(6, 0, (destination_1 | destination_2).ids)],
            "user_id": user.id,
            "items_per_header": 2,
        })
        Header = self.env["ab_transfer_header"]

        def fake_calculation(header):
            for product in products:
                self.env["ab_transfer_smart_line"].create({
                    "header_id": header.id,
                    "product_id": product.id,
                    "qty": 1,
                    "expiry_date": fields.Date.today(),
                    "uom_id": uom.id,
                })
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"type": "success"},
            }

        with patch.object(
                type(wizard),
                "_ensure_smart_destination_caches",
                return_value={"stores": 2, "stock_rows": 0, "sales_rows": 0},
        ), patch.object(
                type(wizard),
                "_get_sales_cache_warning_action",
                return_value=False,
        ), patch.object(
                type(wizard),
                "_ensure_smart_source_cache",
                return_value={"stores": 1, "stock_rows": 0},
        ), patch.object(
                type(wizard),
                "_get_calculation_validation_error_action",
                return_value=False,
        ), patch.object(
                type(Header),
                "action_smart_transfer_calculation",
                autospec=True,
                side_effect=fake_calculation,
        ):
            action = wizard.action_generate_transfers()

        self.assertEqual(action["res_model"], "ab_transfer_header")
        self.assertEqual(wizard.state, "done")
        self.assertEqual(len(wizard.generated_header_ids), 6)
        for destination in (destination_1, destination_2):
            headers = wizard.generated_header_ids.filtered(
                lambda header: header.to_store_id == destination
            ).sorted(key=lambda header: header.id)
            self.assertEqual(headers.mapped("smart_items_count"), [2, 2, 1])
            location_chunks = [
                header.smart_line_ids.mapped("smart_product_location")
                for header in headers
            ]
            self.assertEqual(
                location_chunks,
                [["A-01", "A-01"], ["A-01"], ["B-01", "B-01"]],
            )
            for locations in location_chunks:
                self.assertEqual(len(set(locations)), 1)

    def test_apply_dropout_button_updates_only_automatic_dropout_reasons(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        covered_product = self._create_smart_product("SMART-DROP-COVERED", 99051, uom)
        uncovered_product = self._create_smart_product("SMART-DROP-UNCOVERED", 99052, uom)
        manual_product = self._create_smart_product("SMART-DROP-MANUAL", 99053, uom)
        header.write({
            "smart_stock_method": SMART_STOCK_METHOD_NORMAL,
            "smart_days": 60,
            "smart_dropout_coverage": 75,
        })

        covered_line = self._create_smart_line(
            header,
            covered_product,
            uom,
            smart_destination_stock_qty=80,
            smart_month1_sales=60,
            smart_month2_sales=45,
            smart_month3_sales=45,
        )
        uncovered_line = self._create_smart_line(
            header,
            uncovered_product,
            uom,
            exclusion_reason="dropout_coverage",
            smart_destination_stock_qty=20,
            smart_month1_sales=60,
            smart_month2_sales=45,
            smart_month3_sales=45,
        )
        manual_line = self._create_smart_line(
            header,
            manual_product,
            uom,
            exclusion_reason="expired",
            smart_destination_stock_qty=80,
            smart_month1_sales=60,
            smart_month2_sales=45,
            smart_month3_sales=45,
        )

        header.action_smart_apply_dropout_coverage()

        self.assertEqual(covered_line.exclusion_reason, "dropout_coverage")
        self.assertFalse(uncovered_line.exclusion_reason)
        self.assertEqual(manual_line.exclusion_reason, "expired")

    def test_purchase_can_decrease_smart_line_qty_to_zero(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-QTY-DECREASE", 99101, uom)
        line = self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            smart_source_stock_qty=30,
            smart_total_need=25,
        )

        line.write({"qty": 0})

        self.assertEqual(line.qty, 0)

    def test_purchase_can_increase_smart_line_qty_within_source_surplus(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-QTY-INCREASE", 99102, uom)
        line = self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            smart_source_stock_qty=50,
            smart_total_need=42,
        )

        line.write({"qty": 18})

        self.assertEqual(line.qty, 18)

    def test_purchase_can_increase_smart_line_qty_above_source_surplus_before_store_preparation(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_products_or_skip(1)[0]
        uom = product.uom_id
        line = self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            smart_source_stock_qty=50,
            smart_total_need=42,
        )

        line.write({"qty": 19})

        self.assertEqual(line.qty, 19)
        self.assertEqual(line.smart_over_need_qty, 8)
        self.assertTrue(line.smart_qty_exceeds_over_need)

    def test_smart_line_qty_increase_uses_original_qty_after_decrease(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_products_or_skip(1)[0]
        uom = product.uom_id
        line = self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            smart_source_stock_qty=50,
            smart_total_need=42,
        )

        line.write({"qty": 1})
        line.write({"qty": 18})
        self.assertFalse(line.smart_qty_exceeds_over_need)

        line.write({"qty": 19})
        self.assertTrue(line.smart_qty_exceeds_over_need)

        with self.assertRaisesRegex(ValidationError, "allowed over for these lines"):
            header.action_smart_to_store_preparation()
        self.assertEqual(header.smart_stage, SMART_STAGE_PURCHASE_PREPARATION)

    def test_store_preparation_blocks_smart_line_qty_above_source_surplus(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_products_or_skip(1)[0]
        uom = product.uom_id
        self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            smart_source_stock_qty=50,
            smart_total_need=42,
        ).write({"qty": 19})

        with self.assertRaisesRegex(ValidationError, "allowed_over_qty"):
            header.action_smart_to_store_preparation()
        self.assertEqual(header.smart_stage, SMART_STAGE_PURCHASE_PREPARATION)

    def test_smart_qty_allowed_over_message_lists_all_non_excluded_lines(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_products_or_skip(1)[0]
        uom = product.uom_id
        line_1 = self._create_smart_line(
            header,
            product,
            uom,
            qty=6,
            smart_original_qty=0,
            smart_source_stock_qty=0,
            smart_total_need=0,
        )
        line_2 = self._create_smart_line(
            header,
            product,
            uom,
            qty=8,
            smart_original_qty=0,
            smart_source_stock_qty=0,
            smart_total_need=0,
        )
        excluded_line = self._create_smart_line(
            header,
            product,
            uom,
            qty=9,
            smart_original_qty=0,
            smart_source_stock_qty=0,
            smart_total_need=0,
            exclusion_reason="expired",
        )

        with self.assertRaises(ValidationError) as error:
            (line_1 | line_2 | excluded_line)._check_smart_qty_allowed_over()

        message = str(error.exception)
        self.assertIn("Smart transfer quantity cannot exceed the allowed over", message)
        self.assertIn("code | name | qty | allowed_over_qty", message)
        self.assertIn("6.000", message)
        self.assertIn("8.000", message)
        self.assertNotIn("9.000", message)

    def test_smart_line_expected_stock_shortage_highlight_ignores_excluded_lines(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_products_or_skip(1)[0]
        uom = product.uom_id
        line = self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            smart_source_stock_qty=5,
        )

        self.assertTrue(line.smart_qty_exceeds_expected_stock)

        line.write({"exclusion_reason": "expired"})

        self.assertFalse(line.smart_qty_exceeds_expected_stock)

    def test_smart_line_qty_cannot_be_negative(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-QTY-NEGATIVE", 99105, uom)
        line = self._create_smart_line(header, product, uom, qty=10)

        with self.assertRaisesRegex(ValidationError, "cannot be negative"):
            line.write({"qty": -1})

    def test_smart_line_qty_can_only_be_edited_in_purchase_preparation(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-QTY-STAGE", 99106, uom)
        line = self._create_smart_line(header, product, uom, qty=10)
        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        with self.assertRaisesRegex(ValidationError, "purchase preparation"):
            line.write({"qty": 0})

    def test_pre_submit_blocks_when_other_active_smart_transfer_reserved_stock(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-PRE-SUB-STOCK-BLOCK", 99107, uom)
        self._create_smart_line(header, product, uom, qty=8)
        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        other_header = self._create_smart_header_for_source(header, "SMART-PRE-SUB-OTHER", 8311)
        self._create_smart_line(other_header, product, uom, qty=5)
        other_header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
                return_value={99107: 10},
        ), self.assertRaisesRegex(UserError, "already reserved"):
            header.action_smart_pre_submit()

        self.assertEqual(header.smart_stage, SMART_STAGE_STORE_REVISION)
        self.assertFalse(header.line_ids)

    def test_pre_submit_stock_validation_ignores_current_header_reservation(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-PRE-SUB-STOCK-CURRENT", 99108, uom)
        self._create_smart_line(header, product, uom, qty=8, smart_source_stock_qty=10)
        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        other_header = self._create_smart_header_for_source(header, "SMART-PRE-SUB-SMALL", 8312)
        self._create_smart_line(other_header, product, uom, qty=2)
        other_header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
                return_value={99108: 10},
        ), patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[self._smart_source_row(901, 10)],
        ):
            header.action_smart_pre_submit()

        self.assertEqual(header.smart_stage, SMART_STAGE_PRE_SUBMIT)
        self.assertEqual(header.line_ids.qty, 8)
        self.assertEqual(header.line_ids.class_id, 901)

    def test_pre_submit_copies_only_non_excluded_smart_lines(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        included_product = self._create_smart_product("SMART-INCLUDED", 99021, uom)
        excluded_product = self._create_smart_product("SMART-EXCLUDED", 99022, uom)
        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        self._create_smart_line(
            header,
            included_product,
            uom,
            qty=8,
            smart_source_stock_qty=20,
        )
        self._create_smart_line(
            header,
            excluded_product,
            uom,
            qty=9,
            exclusion_reason="expired",
        )

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
                return_value={99021: 20},
        ), patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[self._smart_source_row(601, 20)],
        ):
            header.action_smart_pre_submit()

        self.assertEqual(header.smart_stage, SMART_STAGE_PRE_SUBMIT)
        self.assertEqual(len(header.line_ids), 1)
        self.assertEqual(header.line_ids.product_id, included_product)
        self.assertEqual(header.line_ids.qty, 8)
        self.assertEqual(header.line_ids.class_id, 601)
        self.assertEqual(header.line_ids.smart_source_stock_qty, 20)
        self.assertEqual(header.get_transfer_lines_for_report(), header.line_ids)
        self.assertEqual(header.get_smart_lines_for_report(), header.smart_line_ids)
        self.assertEqual(len(header.get_smart_lines_for_report()), 2)

    def test_pre_submit_recreates_existing_transfer_line_for_product(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_products_or_skip(1)
        uom = product.uom_id
        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})
        old_line = self.env["ab_transfer_line"].create({
            "header_id": header.id,
            "product_id": product.id,
            "class_id": 701,
            "qty": 1,
            "expiry_date": fields.Date.today(),
            "uom_id": uom.id,
        })
        self._create_smart_line(
            header,
            product,
            uom,
            qty=6,
        )
        product_serial = header._get_smart_product_serial(product)
        if not product_serial:
            self.skipTest("Existing product has no EPlus serial for smart stock validation.")

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
                return_value={product_serial: 20},
        ), patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[self._smart_source_row(702, 20)],
        ):
            header.action_smart_pre_submit()

        self.assertEqual(len(header.line_ids), 1)
        self.assertEqual(header.line_ids.class_id, 702)
        self.assertEqual(header.line_ids.qty, 6)
        self.assertFalse(old_line.exists())

    def test_pre_submit_rebuilds_transfer_lines_after_backward_revision_exclusion(self):
        self.env.user.write({
            "group_ids": [(4, self.env.ref("ab_transfer_smart.group_trnasfer_smart_store_manager").id)],
        })
        header = self._create_smart_header_from_existing_records_or_skip()
        included_product, excluded_product = self._get_existing_smart_products_or_skip(2)
        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})
        included_line = self._create_smart_line(
            header,
            included_product,
            included_product.uom_id,
            qty=3,
        )
        excluded_line = self._create_smart_line(
            header,
            excluded_product,
            excluded_product.uom_id,
            qty=4,
        )
        included_serial = header._get_smart_product_serial(included_product)
        excluded_serial = header._get_smart_product_serial(excluded_product)
        if not included_serial or not excluded_serial:
            self.skipTest("Existing products have no EPlus serial for smart stock validation.")
        source_stock_by_serial = {
            included_serial: 20,
            excluded_serial: 20,
        }

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
                return_value=source_stock_by_serial,
        ), patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[self._smart_source_row(901, 20)],
        ):
            header.action_smart_pre_submit()
            self.assertEqual(
                set(header.line_ids.mapped("product_id").ids),
                set((included_product | excluded_product).ids),
            )

            header.action_smart_back_to_store_revision()
            self.assertEqual(header.smart_stage, SMART_STAGE_STORE_REVISION)
            self.assertFalse(header.line_ids)

            excluded_line.write({"exclusion_reason": "expired"})
            header.action_smart_pre_submit()

        self.assertEqual(header.smart_stage, SMART_STAGE_PRE_SUBMIT)
        self.assertEqual(len(header.line_ids), 1)
        self.assertEqual(header.line_ids.product_id, included_product)
        self.assertEqual(header.line_ids.qty, included_line.qty)

    def test_pre_submit_splits_transfer_lines_by_source_class(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-SPLIT-CLASS", 99032, uom)
        header.write({"smart_stage": SMART_STAGE_STORE_REVISION})
        self._create_smart_line(
            header,
            product,
            uom,
            qty=9,
            smart_source_stock_qty=12,
        )

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
                return_value={99032: 12},
        ), patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[
                    self._smart_source_row(801, 4),
                    self._smart_source_row(802, 8),
                ],
        ):
            header.action_smart_pre_submit()

        lines = header.line_ids.sorted(key=lambda line: line.class_id)
        self.assertEqual(lines.mapped("class_id"), [801, 802])
        self.assertEqual(lines.mapped("qty"), [4, 5])

    def test_other_branch_context_uses_cached_sales_and_calculates_need_per_store(self):
        source = self._create_store_or_skip({
            "name": "Smart Cache Source",
            "code": "SMART-CACHE-SRC",
            "eplus_serial": 301,
            "allow_sale": True,
        })
        destination = self._create_store_or_skip({
            "name": "Smart Cache Destination",
            "code": "SMART-CACHE-DST",
            "eplus_serial": 302,
            "allow_sale": True,
        })
        other_1 = self._create_store_or_skip({
            "name": "Smart Cache Other 1",
            "code": "SMART-CACHE-OTH1",
            "eplus_serial": 303,
            "allow_sale": True,
        })
        other_2 = self._create_store_or_skip({
            "name": "Smart Cache Other 2",
            "code": "SMART-CACHE-OTH2",
            "eplus_serial": 304,
            "allow_sale": True,
        })
        today = fields.Date.context_today(self.env["ab_transfer_header"])
        yesterday = today - timedelta(days=1)
        for offset in range(1, 91):
            self.env["ab_sales_per_day_sync_state"].create({
                "sale_date": today - timedelta(days=offset),
                "state": "done",
            })
        self.env["ab_sales_per_day"].create([
            {
                "store_id": other_1.id,
                "product_eplus_serial": 9901,
                "sale_date": yesterday,
                "sales_qty": 90,
            },
            {
                "store_id": other_2.id,
                "product_eplus_serial": 9901,
                "sale_date": yesterday,
                "sales_qty": 90,
            },
        ])
        self.env["ab_sales_inventory"].create([
            {
                "store_id": other_1.id,
                "product_eplus_serial": 9901,
                "balance": 10,
            },
            {
                "store_id": other_2.id,
                "product_eplus_serial": 9901,
                "balance": 35,
            },
        ])
        header = self.env["ab_transfer_header"].new({
            "from_store_id": source.id,
            "to_store_id": destination.id,
            "smart_days": 30,
            "smart_stock_method": SMART_STOCK_METHOD_NORMAL,
            "fair_store_ids": [(6, 0, (other_1 | other_2).ids)],
        })

        context = header._get_smart_other_branches_context_by_serial({
            9901: self.env["ab_product"].browse(),
        })

        self.assertAlmostEqual(context[9901]["stock_qty"], 45)
        self.assertAlmostEqual(context[9901]["month1_sales"], 180)
        self.assertAlmostEqual(context[9901]["required_qty"], 20)

    def test_other_branch_context_requires_completed_sales_cache(self):
        source = self._create_store_or_skip({
            "name": "Smart Missing Cache Source",
            "code": "SMART-MISS-SRC",
            "eplus_serial": 401,
            "allow_sale": True,
        })
        destination = self._create_store_or_skip({
            "name": "Smart Missing Cache Destination",
            "code": "SMART-MISS-DST",
            "eplus_serial": 402,
            "allow_sale": True,
        })
        other = self._create_store_or_skip({
            "name": "Smart Missing Cache Other",
            "code": "SMART-MISS-OTH",
            "eplus_serial": 403,
            "allow_sale": True,
        })
        header = self.env["ab_transfer_header"].new({
            "from_store_id": source.id,
            "to_store_id": destination.id,
            "smart_days": 30,
            "smart_stock_method": SMART_STOCK_METHOD_NORMAL,
            "fair_store_ids": [(6, 0, other.ids)],
        })

        with self.assertRaises(UserError):
            header._get_smart_other_branches_context_by_serial({
                9902: self.env["ab_product"].browse(),
            })

    def test_other_branch_context_can_skip_sales_cache_after_warning_acceptance(self):
        source = self._create_store_or_skip({
            "name": "Smart Accepted Cache Source",
            "code": "SMART-ACCEPT-SRC",
            "eplus_serial": 411,
            "allow_sale": True,
        })
        destination = self._create_store_or_skip({
            "name": "Smart Accepted Cache Destination",
            "code": "SMART-ACCEPT-DST",
            "eplus_serial": 412,
            "allow_sale": True,
        })
        other = self._create_store_or_skip({
            "name": "Smart Accepted Cache Other",
            "code": "SMART-ACCEPT-OTH",
            "eplus_serial": 413,
            "allow_sale": True,
        })
        header = self.env["ab_transfer_header"].new({
            "from_store_id": source.id,
            "to_store_id": destination.id,
            "smart_days": 30,
            "smart_stock_method": SMART_STOCK_METHOD_NORMAL,
            "fair_store_ids": [(6, 0, other.ids)],
        })

        context = header.with_context(
            skip_smart_sales_cache_coverage=True
        )._get_smart_other_branches_context_by_serial({
            9903: self.env["ab_product"].browse(),
        })

        self.assertIn(9903, context)

    def test_smart_calculation_returns_local_warning_for_missing_cache(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-WARNING-P1", 99041, uom)
        header.target_product_ids = [(6, 0, product.ids)]
        missing_day = fields.Date.today() - timedelta(days=1)
        calls = []
        wizard_count_before = self.env["ab_transfer_smart_wizard"].search_count([])

        def refresh_cache(force=False):
            calls.append("cache")
            return {"stores": 1, "stock_rows": 0, "sales_rows": 0}

        def missing_sales_dates():
            calls.append("warning")
            return [missing_day]

        with patch.object(
                type(header),
                "_validate_smart_source_connection",
                return_value=None,
        ), patch.object(
                type(header),
                "_refresh_smart_destination_cache",
                side_effect=refresh_cache,
        ), patch.object(
                type(header),
                "_get_smart_other_branch_store_sql_ids",
                return_value=[999],
        ), patch.object(
                type(header),
                "_get_smart_missing_sales_cache_dates",
                side_effect=missing_sales_dates,
        ):
            action = header.action_smart_transfer_calculation()

        self.assertEqual(calls, ["cache", "warning"])
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "warning")
        self.assertIn(fields.Date.to_string(missing_day), action["params"]["message"])
        self.assertEqual(
            self.env["ab_transfer_smart_wizard"].search_count([]),
            wizard_count_before,
        )

    def test_readonly_missing_sales_cache_check_never_creates_sync_states(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        SalesPerDay = self.env["ab_sales_per_day"]

        with patch.object(
                type(SalesPerDay),
                "_ensure_sync_states",
        ) as ensure_sync_states:
            missing_dates = header._get_smart_missing_sales_cache_dates_readonly()

        ensure_sync_states.assert_not_called()
        self.assertIsInstance(missing_dates, list)

    def test_excel_preview_maps_prices_need_and_dropout_without_persistence(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        product = self._get_existing_smart_product_with_serial_or_skip()
        uom = product.uom_id
        product_serial = int(product.eplus_serial)
        missing_day = fields.Date.context_today(header) - timedelta(days=1)
        header.target_product_ids = [(6, 0, product.ids)]
        preview_line_vals = {
            "qty": 7,
            "expiry_date": fields.Date.today(),
            "uom_id": uom.id,
            "source_type": SMART_LINE_SOURCE_DOMAIN,
            "exclusion_reason": "dropout_coverage",
            "smart_source_stock_qty": 50,
            "smart_destination_stock_qty": 8,
            "smart_month1_sales": 30,
            "smart_month2_sales": 20,
            "smart_month3_sales": 10,
        }
        protected_models = (
            "ab_transfer_header",
            "ab_transfer_smart_line",
            "ab_transfer_line",
            "ab_transfer_smart_wizard",
            "ab_transfer_smart_stock_cache",
            "ab_transfer_smart_sales_cache",
            "ab_sales_per_day_sync_state",
        )
        counts_before = {
            model_name: self.env[model_name].with_context(active_test=False).search_count([])
            for model_name in protected_models
        }

        with patch.object(
                type(header),
                "_validate_smart_transfer_header",
                return_value=None,
        ), patch.object(
                type(header),
                "_get_smart_other_branch_store_sql_ids",
                return_value=[999],
        ), patch.object(
                type(header),
                "_get_smart_missing_sales_cache_dates_readonly",
                return_value=[missing_day],
        ), patch.object(
                type(header),
                "_fetch_destination_smart_rows_readonly",
                return_value=[
                    (
                        product_serial,
                        "",
                        "",
                        header.to_store_id.eplus_serial,
                        8,
                        30,
                        20,
                        10,
                        60,
                    ),
                ],
        ), patch.object(
                type(header),
                "_prepare_smart_transfer_preview_rows",
                return_value=([{
                    "product": product,
                    "line_vals": preview_line_vals,
                    "dropout_excluded": True,
                }], {
                    "created": 0,
                    "updated": 0,
                    "dropout_excluded": 1,
                    "missing": 0,
                    "no_stock": 0,
                }),
        ), patch.object(
                type(header),
                "_get_source_inventory_rows",
                return_value=[{
                    "price": 14,
                    "pharm_price": 9,
                }],
        ):
            rows = header._get_smart_transfer_excel_rows(
                allow_incomplete_sales_cache=True
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], {
            "code": product.code,
            "product_name": product.name,
            "company": SMART_EXPORT_COMPANY_NAME,
            "purchase_unit": float(product.min_sale_purchase_qty or 0.0),
            "sell_price": 14.0,
            "purchase_price": 9.0,
            "source_stock": 50.0,
            "destination_stock": 8.0,
            "sales_3_month": 60.0,
            "moving_weighted_avg": 23.0,
            "need": 7.0,
        })
        counts_after = {
            model_name: self.env[model_name].with_context(active_test=False).search_count([])
            for model_name in protected_models
        }
        self.assertEqual(counts_after, counts_before)

    def test_wizard_excel_export_action_is_readonly_and_uses_wizard_report(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "company_id": header.company_id.id,
        })
        Header = self.env["ab_transfer_header"]
        StockCache = self.env["ab_transfer_smart_stock_cache"]
        SalesPerDay = self.env["ab_sales_per_day"]

        with patch.object(
                type(wizard),
                "_validate_smart_export_values",
                return_value=None,
        ), patch.object(
                type(wizard),
                "_get_smart_export_missing_sales_cache_dates_readonly",
                return_value=[],
        ), patch.object(type(wizard), "write") as wizard_write, patch.object(
                type(Header),
                "create",
        ) as header_create, patch.object(
                type(StockCache),
                "refresh_stores_cache",
        ) as refresh_cache, patch.object(
                type(SalesPerDay),
                "_ensure_sync_states",
        ) as ensure_sync_states:
            action = wizard.action_export_excel()

        wizard_write.assert_not_called()
        header_create.assert_not_called()
        refresh_cache.assert_not_called()
        ensure_sync_states.assert_not_called()
        self.assertEqual(action["report_type"], "xlsx")
        self.assertEqual(
            action["report_name"],
            "ab_transfer_smart.smart_transfer_wizard_xlsx",
        )

    def test_wizard_excel_export_warning_is_readonly(self):
        header = self._create_smart_header_from_existing_records_or_skip()
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "company_id": header.company_id.id,
        })
        missing_day = fields.Date.context_today(wizard) - timedelta(days=1)

        with patch.object(
                type(wizard),
                "_validate_smart_export_values",
                return_value=None,
        ), patch.object(
                type(wizard),
                "_get_smart_export_missing_sales_cache_dates_readonly",
                return_value=[missing_day],
        ), patch.object(type(wizard), "write") as wizard_write:
            action = wizard.action_export_excel()

        wizard_write.assert_not_called()
        warning_view = self.env.ref(
            "ab_transfer_smart.ab_transfer_smart_wizard_export_warning_view_form"
        )
        self.assertEqual(action["res_model"], "ab_transfer_smart_wizard")
        self.assertEqual(action["res_id"], wizard.id)
        self.assertEqual(action["views"], [(warning_view.id, "form")])
        self.assertEqual(action["target"], "new")

    def test_wizard_view_has_draft_excel_export_button(self):
        view = self.env.ref("ab_transfer_smart.ab_transfer_smart_wizard_view_form")
        arch = etree.fromstring(view.arch_db.encode())
        export_button = arch.xpath("//button[@name='action_export_excel']")[0]

        self.assertEqual(export_button.get("string"), "Export Smart Transfer Excel")
        self.assertEqual(export_button.get("invisible"), "state != 'draft'")

        warning_view = self.env.ref(
            "ab_transfer_smart.ab_transfer_smart_wizard_export_warning_view_form"
        )
        default_view_id = self.env["ir.ui.view"].default_view(
            "ab_transfer_smart_wizard", "form"
        )
        self.assertGreater(warning_view.priority, view.priority)
        self.assertEqual(default_view_id, view.id)
