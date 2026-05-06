import base64

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestAbQualityAssurance(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Users = self.env["res.users"].sudo().with_context(no_reset_password=True)
        self.Employees = self.env["ab_hr_employee"].sudo()
        self.Departments = self.env["ab_hr_department"].sudo()
        self.Sections = self.env["ab_quality_assurance_section"]
        self.Standards = self.env["ab_quality_assurance_standard"]
        self.Visits = self.env["ab_quality_assurance_visit"]

        self.group_user = self.env.ref("base.group_user")
        self.ro_group = self.env.ref("ab_quality_assurance.group_ab_quality_assurance_ro")
        self.member_group = self.env.ref("ab_quality_assurance.group_ab_quality_assurance_user")
        self.admin_group = self.env.ref("ab_quality_assurance.group_ab_quality_assurance_manager")
        self.manager_group = self.env.ref("ab_quality_assurance.group_ab_quality_assurance_manager")

        self.member_user = self._create_user("QA Member", "qa_member_test", [self.member_group.id])
        self.admin_user = self._create_user("QA Admin", "qa_admin_test", [self.admin_group.id])
        self.quality_manager_user = self._create_user("QA Manager", "qa_manager_test", [])
        self.follow_up_user = self._create_user("Management Response", "qa_management_response_test", [self.ro_group.id])
        self.outsider_user = self._create_user("QA Outsider", "qa_outsider_test", [])

        self.member_employee = self._create_employee("QA Member Employee", self.member_user)
        self.admin_employee = self._create_employee("QA Admin Employee", self.admin_user)
        self.quality_manager_employee = self._create_employee("QA Manager Employee", self.quality_manager_user)
        self.follow_up_employee = self._create_employee("Management Response Employee", self.follow_up_user)
        self.outsider_employee = self._create_employee("QA Outsider Employee", self.outsider_user)

        self.quality_department = self.Departments.create(
            {
                "name": "ادارة الرقابة والجودة",
                "manager_id": self.quality_manager_employee.id,
            }
        )
        self.visited_department = self.Departments.create({"name": "فرع العمليات"})
        self.follow_up_department = self.Departments.create(
            {
                "name": "الادارة المعنية",
                "user_id": self.follow_up_user.id,
            }
        )
        self.non_branch_department = self.Departments.create({"name": "Operations"})

        self.member_employee.department_id = self.quality_department.id
        self.admin_employee.department_id = self.quality_department.id
        self.quality_manager_employee.department_id = self.quality_department.id
        self.follow_up_employee.department_id = self.follow_up_department.id
        self.outsider_employee.department_id = self.visited_department.id

        self.env["ab_quality_assurance.access"].sudo()._sync_quality_manager_group()

        self.section = self.Sections.with_user(self.quality_manager_user).create(
            {
                "name": "Cleanliness",
            }
        )
        self.second_section = self.Sections.with_user(self.quality_manager_user).create(
            {
                "name": "Documentation",
            }
        )

        self.standard = self.Standards.with_user(self.quality_manager_user).create(
            {
                "section_id": self.section.id,
                "title": "Temperature and storage",
                "max_score": 20,
            }
        )
        self.Standards.with_user(self.quality_manager_user).create(
            {
                "section_id": self.second_section.id,
                "title": "Document archive",
                "max_score": 30,
            }
        )

    def _create_user(self, name, login, extra_groups):
        return self.Users.create(
            {
                "name": name,
                "login": login,
                "email": f"{login}@example.com",
                "group_ids": [(6, 0, [self.group_user.id, *extra_groups])],
            }
        )

    def _create_employee(self, name, user):
        return self.Employees.create(
            {
                "name": name,
                "user_id": user.id,
            }
        )

    def test_quality_department_manager_group_is_synced(self):
        self.assertTrue(self.quality_manager_user.has_group("ab_quality_assurance.group_ab_quality_assurance_manager"))
        self.assertTrue(self.quality_manager_user.has_group("ab_quality_assurance.group_ab_quality_assurance_user"))

    def test_visit_creation_populates_department_standards(self):
        visit = self.Visits.with_user(self.member_user).create(
            {
                "department_id": self.visited_department.id,
            }
        )
        self.assertEqual(visit.employee_id, self.member_employee)
        self.assertEqual(len(visit.visit_section_ids), 2)
        self.assertSetEqual(
            set(visit.visit_section_ids.mapped("visit_line_ids.standard_id").ids),
            set(self.Standards.search([]).ids),
        )

    def test_visit_creation_hides_sections_without_active_standards(self):
        empty_section = self.Sections.with_user(self.quality_manager_user).create(
            {
                "name": "Empty Section",
            }
        )
        visit = self.Visits.with_user(self.member_user).create(
            {
                "department_id": self.visited_department.id,
            }
        )

        self.assertNotIn(empty_section, visit.visit_section_ids.mapped("section_id"))

    def test_score_cannot_exceed_standard_maximum(self):
        visit = self.Visits.with_user(self.member_user).create(
            {
                "department_id": self.visited_department.id,
            }
        )
        line = visit.visit_section_ids.mapped("visit_line_ids").filtered(
            lambda current_line: current_line.standard_id == self.standard
        )
        line.with_user(self.member_user).write({"score": 20})
        self.assertEqual(line.score, 20)
        self.assertEqual(line.percentage, 100)
        with self.assertRaises(ValidationError):
            line.with_user(self.member_user).write({"score": 21})

    def test_score_can_be_zero(self):
        visit = self.Visits.with_user(self.member_user).create(
            {
                "department_id": self.visited_department.id,
            }
        )
        line = visit.visit_section_ids.mapped("visit_line_ids").filtered(
            lambda current_line: current_line.standard_id == self.standard
        )
        line.with_user(self.member_user).write({"score": 0})
        self.assertEqual(line.score, 0)
        self.assertEqual(line.percentage, 0)

    def test_visit_line_note_and_attachment_download_action(self):
        visit = self.Visits.with_user(self.member_user).create(
            {
                "department_id": self.visited_department.id,
            }
        )
        line = visit.visit_section_ids.mapped("visit_line_ids").filtered(
            lambda current_line: current_line.standard_id == self.standard
        )

        with self.assertRaises(UserError):
            line.with_user(self.member_user).action_download_attachment()

        line.with_user(self.member_user).write(
            {
                "score": 12,
                "note": "Temperature record was incomplete.",
                "attachment": base64.b64encode(b"evidence"),
                "attachment_name": "temperature-evidence.txt",
            }
        )

        self.assertEqual(line.note, "Temperature record was incomplete.")
        self.assertTrue(line.has_attachment)
        action = line.with_user(self.member_user).action_download_attachment()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("/web/content/ab_quality_assurance_visit_line/", action["url"])
        self.assertIn("download=true", action["url"])

    def test_selected_follow_up_department_can_only_write_its_response(self):
        visit = self.Visits.with_user(self.member_user).create(
            {
                "department_id": self.visited_department.id,
            }
        )
        for line in visit.visit_section_ids.mapped("visit_line_ids"):
            line.with_user(self.member_user).write({"score": line.max_score})
        visit.with_user(self.member_user).action_submit_visit()

        visit.with_user(self.member_user).write(
            {
                "follow_up_ids": [
                    fields.Command.create({"department_id": self.follow_up_department.id}),
                ]
            }
        )
        follow_up = visit.follow_up_ids.filtered(lambda current: current.department_id == self.follow_up_department)

        with self.assertRaises(AccessError):
            follow_up.with_user(self.member_user).write({"response": "The visit creator cannot answer for management."})

        visit.with_user(self.follow_up_user).write(
            {
                "follow_up_ids": [
                    fields.Command.update(
                        follow_up.id,
                        {"response": "The management reviewed the visit and added its response."},
                    ),
                ]
            }
        )
        follow_up.invalidate_recordset(["response", "response_user_id", "response_date"])
        self.assertEqual(
            follow_up.response,
            "The management reviewed the visit and added its response.",
        )
        self.assertEqual(follow_up.response_user_id, self.follow_up_user)
        self.assertTrue(follow_up.response_date)

        with self.assertRaises(AccessError):
            visit.with_user(self.follow_up_user).write(
                {"notes": "Changing evaluation notes is not allowed."}
            )

        with self.assertRaises(AccessError):
            visit.with_user(self.follow_up_user).write(
                {
                    "follow_up_ids": [
                        fields.Command.create({"department_id": self.non_branch_department.id}),
                    ]
                }
            )

        first_line = visit.visit_section_ids.mapped("visit_line_ids").sorted("id")[0]
        with self.assertRaises(AccessError):
            first_line.with_user(self.follow_up_user).write({"score": 0})

    def test_submitted_visit_scores_are_locked(self):
        visit = self.Visits.with_user(self.member_user).create(
            {
                "department_id": self.visited_department.id,
            }
        )
        first_line = visit.visit_section_ids.mapped("visit_line_ids").sorted("id")[0]
        for line in visit.visit_section_ids.mapped("visit_line_ids"):
            line.with_user(self.member_user).write({"score": line.max_score})
        visit.with_user(self.member_user).action_submit_visit()

        self.assertEqual(visit.state, "submitted")
        with self.assertRaises(UserError):
            first_line.with_user(self.member_user).write({"score": 5})

    def test_member_cannot_manage_standards_but_quality_manager_can(self):
        with self.assertRaises(AccessError):
            self.Standards.with_user(self.member_user).create(
                {
                    "section_id": self.section.id,
                    "title": "Member attempt",
                    "max_score": 10,
                }
            )

        standard = self.Standards.with_user(self.quality_manager_user).create(
            {
                "section_id": self.section.id,
                "title": "Manager standard",
                "max_score": 10,
            }
        )
        self.assertTrue(bool(standard))

    def test_outsider_cannot_create_visit(self):
        with self.assertRaises(AccessError):
            self.Visits.with_user(self.outsider_user).create(
                {
                    "department_id": self.visited_department.id,
                }
            )

    def test_non_branch_department_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.Visits.with_user(self.member_user).create(
                {
                    "department_id": self.non_branch_department.id,
                }
            )
