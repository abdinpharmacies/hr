# -*- coding: utf-8 -*-
import base64

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPayrollSeparation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        company = cls.env.company
        internal_group = cls.env.ref("base.group_user")
        payroll_group = cls.env.ref("ab_payroll.group_ab_hr_payroll_sheet_admin")
        cls.regular_user = Users.create(
            {
                "name": "Payroll Separation Regular User",
                "login": "ab_payroll_regular_test",
                "company_id": company.id,
                "company_ids": [Command.set([company.id])],
                "group_ids": [Command.set([internal_group.id])],
            }
        )
        cls.payroll_user = Users.create(
            {
                "name": "Payroll Separation Administrator",
                "login": "ab_payroll_admin_test",
                "company_id": company.id,
                "company_ids": [Command.set([company.id])],
                "group_ids": [Command.set([internal_group.id, payroll_group.id])],
            }
        )

    def test_payroll_model_and_employee_fields_are_preserved(self):
        Sheet = self.env["ab.hr.payroll.sheet"]
        Employee = self.env["ab_hr_employee"]

        self.assertEqual(Sheet._table, "ab_hr_payroll_sheet")
        self.assertEqual(Sheet._name, "ab.hr.payroll.sheet")
        for field_name in (
            "telegram_chat_id",
            "telegram_user_id",
            "telegram_username",
            "telegram_linked_at",
        ):
            self.assertIn(field_name, Employee._fields)

    def test_deterministic_filename_and_telegram_code_parsing(self):
        Sheet = self.env["ab.hr.payroll.sheet"]
        Employee = self.env["ab_hr_employee"]

        parsed = Sheet._parse_filename("Employee_Full_Name_1234_Department.pdf")
        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["employee_code"], "1234")
        self.assertEqual(parsed["extension"], "pdf")
        self.assertEqual(Employee._extract_telegram_employee_code("employee code 1234"), "1234")
        self.assertEqual(Employee._normalize_telegram_employee_code("12-34"), "1234")

    def test_unlink_archives_payroll_sheet(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "Unknown_Employee_987654_Department.pdf",
                "type": "binary",
                "datas": base64.b64encode(b"%PDF-1.4\n"),
            }
        )
        sheet = self.env["ab.hr.payroll.sheet"].create(
            {
                "payroll_period": "2026-07",
                "payroll_type": "preliminary",
                "attachment_id": attachment.id,
                "file_name": attachment.name,
            }
        )

        sheet.unlink()

        self.assertTrue(sheet.exists())
        self.assertFalse(sheet.active)
        self.assertEqual(sheet.state, "archived")
        self.assertEqual(attachment.res_model, "ab.hr.payroll.sheet")
        self.assertEqual(attachment.res_id, sheet.id)

    def test_payroll_access_is_group_scoped(self):
        Sheet = self.env["ab.hr.payroll.sheet"]

        self.assertFalse(Sheet.with_user(self.regular_user).has_access("read"))
        self.assertTrue(Sheet.with_user(self.payroll_user).has_access("read"))
        self.assertTrue(Sheet.with_user(self.payroll_user).has_access("create"))

    def test_menu_and_metadata_belong_to_ab_payroll(self):
        menu = self.env.ref("ab_payroll.menu_ab_hr_payroll_sheet")
        payroll_group = self.env.ref("ab_payroll.group_ab_hr_payroll_sheet_admin")
        hr_admin_group = self.env.ref("ab_hr.group_ab_hr_admin")

        self.assertEqual(menu.parent_id, self.env.ref("ab_hr.ab_hr_salaries_root"))
        self.assertIn(payroll_group, menu.group_ids)
        self.assertIn(payroll_group, hr_admin_group.all_implied_ids)
        self.assertTrue(self.env.ref("ab_payroll.action_ab_hr_payroll_sheet"))
        self.assertTrue(self.env.ref("ab_payroll.ir_cron_ab_hr_payroll_sheet_distribution"))
