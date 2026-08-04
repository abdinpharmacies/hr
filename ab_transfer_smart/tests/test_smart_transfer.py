# -*- coding: utf-8 -*-
import base64
import io
import zipfile

from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.ab_transfer_smart.models.ab_transfer_header import (
    SMART_STAGE_PURCHASE_PREPARATION,
    SMART_STAGE_PRE_SUBMIT,
    SMART_STAGE_SUBMIT,
    SMART_STAGE_STORE_PREPARATION,
    SMART_STAGE_STORE_REVISION,
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

    def _get_existing_smart_products_or_skip(self, count):
        products = self.env["ab_product"].sudo().search([
            ("uom_id", "!=", False),
        ], limit=count)
        if len(products) < count:
            self.skipTest("Not enough existing products are available for smart transfer tests.")
        return products

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

    def test_smart_wizard_items_per_header_defaults_to_40(self):
        defaults = self.env["ab_transfer_smart_wizard"].default_get(["items_per_header"])

        self.assertEqual(defaults["items_per_header"], 40)

    def test_smart_wizard_items_per_header_must_be_positive(self):
        wizard = self.env["ab_transfer_smart_wizard"].new({
            "items_per_header": 0,
        })

        with self.assertRaisesRegex(ValidationError, "at least 1"):
            wizard._check_items_per_header()

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

    def test_print_reports_use_sorted_lines_without_report_chunking(self):
        report_xml = (
            Path(__file__).resolve().parents[1]
            / "report"
            / "ab_transfer_line_reports.xml"
        ).read_text(encoding="utf-8")

        self.assertIn("get_smart_report_sorted_lines(o.smart_line_ids)", report_xml)
        self.assertIn("get_smart_report_sorted_lines(o.line_ids)", report_xml)
        self.assertEqual(report_xml.count("Transfer Date"), 2)
        self.assertEqual(report_xml.count("Printing Date"), 2)
        self.assertEqual(report_xml.count("get_smart_report_transfer_date_text()"), 2)
        self.assertEqual(report_xml.count("get_smart_report_printing_date_text()"), 2)
        self.assertIn("smart_expected_source_stock_qty", report_xml)
        self.assertNotIn("get_smart_report_line_chunks", report_xml)
        self.assertNotIn("line_chunk", report_xml)

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
                "_get_smart_source_stock_by_product_serial",
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
                "_get_smart_source_stock_by_product_serial",
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

        wizard.action_import_product_lines()

        qty_by_product = {
            line.product_id.id: line.qty
            for line in wizard.product_line_ids
        }
        self.assertEqual(qty_by_product[product_1.id], 8)
        self.assertEqual(qty_by_product[product_2.id], 7)
        self.assertFalse(wizard.product_import_text)

    def test_wizard_import_product_lines_from_xlsx_file(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product_1 = self._create_smart_product("SMART-XLSX-1", 99021, uom)
        product_2 = self._create_smart_product("SMART-XLSX-2", 99022, uom)
        xlsx_content = self._minimal_xlsx([
            [product_1.code, "3000"],
            [product_2.code, "1000"],
        ])
        wizard = self.env["ab_transfer_smart_wizard"].create({
            "from_store_id": header.from_store_id.id,
            "to_stores_id": [(6, 0, header.to_store_id.ids)],
            "user_id": header.user_id.id,
            "product_import_file": base64.b64encode(xlsx_content),
            "product_import_filename": "smart_products.xlsx",
        })

        wizard.action_import_product_file()

        qty_by_product = {
            line.product_id.id: line.qty
            for line in wizard.product_line_ids
        }
        self.assertEqual(qty_by_product[product_1.id], 3000)
        self.assertEqual(qty_by_product[product_2.id], 1000)
        self.assertFalse(wizard.product_import_file)
        self.assertFalse(wizard.product_import_filename)

    @staticmethod
    def _minimal_xlsx(rows):
        shared_strings = []
        shared_index = {}

        def shared(value):
            value = str(value)
            if value not in shared_index:
                shared_index[value] = len(shared_strings)
                shared_strings.append(value)
            return shared_index[value]

        sheet_rows = []
        for row_index, values in enumerate(rows, start=1):
            cells = []
            for col_name, value in zip(("A", "B"), values):
                cells.append(
                    '<c r="%s%s" t="s"><v>%s</v></c>'
                    % (col_name, row_index, shared(value))
                )
            sheet_rows.append('<row r="%s">%s</row>' % (row_index, "".join(cells)))

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as workbook:
            workbook.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                '</Types>',
            )
            workbook.writestr(
                "xl/workbook.xml",
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets>'
                '</workbook>',
            )
            workbook.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData>%s</sheetData></worksheet>' % "".join(sheet_rows),
            )
            workbook.writestr(
                "xl/sharedStrings.xml",
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="%s" uniqueCount="%s">%s</sst>'
                % (
                    len(shared_strings),
                    len(shared_strings),
                    "".join("<si><t>%s</t></si>" % value for value in shared_strings),
                ),
            )
        return buffer.getvalue()

    def test_smart_product_line_requested_qty_uses_fair_distribution(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-REQUESTED-FAIR", 99020, uom)
        header.smart_product_line_ids = [(0, 0, {
            "product_id": product.id,
            "qty": 30,
        })]
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
                "required_qty": required_qty,
                "source_stock_qty": source_stock_qty,
                "destination_required_qty": destination_required_qty,
                "other_required_qty": other_required_qty,
                "total_required_qty": total_required_qty,
            })
            return {
                "qty": required_qty,
                "expiry_date": fields.Date.today(),
                "uom_id": uom.id,
                "smart_source_stock_qty": source_stock_qty,
                "smart_need_destination_store": destination_required_qty,
                "smart_need_other_store": other_required_qty,
                "smart_total_need": total_required_qty,
            }

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
                return_value={99020: 30},
        ), patch.object(
                type(header),
                "_get_smart_other_branches_context_by_serial",
                return_value={99020: {"required_qty": 30}},
        ), patch.object(
                type(header),
                "_prepare_smart_line_vals",
                side_effect=prepare_line_vals,
        ):
            result = header._apply_smart_transfer_rows([
                (99020, "P020", "Requested", 8102, 100, 300, 300, 300, 900),
            ])

        self.assertEqual(result["created"], 1)
        self.assertEqual(prepare_calls[0]["destination_required_qty"], 30)
        self.assertEqual(prepare_calls[0]["other_required_qty"], 30)
        self.assertEqual(prepare_calls[0]["total_required_qty"], 60)
        self.assertEqual(prepare_calls[0]["required_qty"], 15)

    def test_target_product_still_requires_source_stock_filter(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        target_product = self._create_smart_product("SMART-NO-STOCK-TARGET", 99016, uom)
        header.target_product_ids = [(6, 0, target_product.ids)]

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
                return_value={},
        ):
            serials = header._get_smart_target_product_serials_with_source_stock()

        self.assertNotIn(99016, serials)

    def test_target_product_with_no_source_stock_does_not_create_smart_line(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        target_product = self._create_smart_product("SMART-ZERO-STOCK-TARGET", 99017, uom)
        header.target_product_ids = [(6, 0, target_product.ids)]

        with patch.object(
                type(header),
                "_get_smart_source_stock_by_product_serial",
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
                "_get_smart_source_stock_by_product_serial",
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
                "_get_smart_source_stock_by_product_serial",
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
                return_value=[
                    self._smart_source_row(701, 4),
                    self._smart_source_row(702, 6),
                ],
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
        self.assertEqual(vals["qty"], 8)
        self.assertEqual(vals["smart_source_stock_qty"], 10)

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

        purchase_preparation = self._create_smart_header_for_source(header, "SMART-EXP-PUR", 8304)
        self._create_smart_line(purchase_preparation, product, uom, qty=7)

        submitted = self._create_smart_header_for_source(header, "SMART-EXP-SUB", 8305)
        self._create_smart_line(submitted, product, uom, qty=11)
        submitted.write({
            "smart_stage": SMART_STAGE_STORE_REVISION,
            "is_submitted": True,
        })

        excluded = self._create_smart_header_for_source(header, "SMART-EXP-EXC", 8306)
        self._create_smart_line(excluded, product, uom, qty=13, exclusion_reason="expired")
        excluded.write({"smart_stage": SMART_STAGE_STORE_REVISION})

        reserved_qty = self.env["ab_transfer_header"]._read_smart_active_reserved_qty_by_product_store(
            [product.id],
            [header.from_store_id.id],
        )

        self.assertEqual(reserved_qty[(product.id, header.from_store_id.id)], 9)
        self.assertEqual(reference_line.smart_expected_source_stock_qty, 41)

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
        wizard = self.env["ab_transfer_smart_wizard"].new({
            "target_mode": "batch",
        })
        calls = []

        def validate_values():
            calls.append("validate_values")

        def ensure_cache():
            calls.append("cache")
            return {"stores": 1, "stock_rows": 0, "sales_rows": 0}

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
                "_get_calculation_validation_error_action",
                side_effect=validation_error_action,
        ):
            action = wizard.action_generate_transfers()

        self.assertEqual(calls, ["validate_values", "cache", "warning", "calculation_validation"])
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

    def test_purchase_cannot_increase_smart_line_qty_above_source_surplus(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-QTY-OVER", 99103, uom)
        line = self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            smart_source_stock_qty=50,
            smart_total_need=42,
        )

        with self.assertRaisesRegex(ValidationError, "cannot exceed 18.000"):
            line.write({"qty": 19})

    def test_smart_line_qty_increase_uses_original_qty_after_decrease(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-QTY-ORIGINAL", 99104, uom)
        line = self._create_smart_line(
            header,
            product,
            uom,
            qty=10,
            smart_source_stock_qty=50,
            smart_total_need=42,
        )

        line.write({"qty": 0})
        line.write({"qty": 18})

        with self.assertRaisesRegex(ValidationError, "cannot exceed 18.000"):
            line.write({"qty": 19})

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

    def test_smart_calculation_returns_persistent_warning_wizard_for_missing_cache(self):
        header = self._create_smart_header()
        uom = self._create_smart_uom()
        product = self._create_smart_product("SMART-WARNING-P1", 99041, uom)
        header.target_product_ids = [(6, 0, product.ids)]
        missing_day = fields.Date.today() - timedelta(days=1)
        calls = []

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

        wizard = self.env["ab_transfer_smart_wizard"].browse(action["res_id"])
        self.assertEqual(calls, ["cache", "warning"])
        self.assertEqual(action["res_model"], "ab_transfer_smart_wizard")
        self.assertEqual(wizard.target_mode, "single")
        self.assertEqual(wizard.source_header_id, header)
        self.assertIn(fields.Date.to_string(missing_day), wizard.sales_cache_warning_message)
