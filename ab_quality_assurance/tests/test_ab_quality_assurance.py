import base64

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
        self.section_manager_user = self._create_user("Section Manager", "qa_section_manager_test", [])
        self.outsider_user = self._create_user("QA Outsider", "qa_outsider_test", [])

        self.member_employee = self._create_employee("QA Member Employee", self.member_user)
        self.admin_employee = self._create_employee("QA Admin Employee", self.admin_user)
        self.quality_manager_employee = self._create_employee("QA Manager Employee", self.quality_manager_user)
        self.section_manager_employee = self._create_employee("Section Manager Employee", self.section_manager_user)
        self.outsider_employee = self._create_employee("QA Outsider Employee", self.outsider_user)

        self.quality_department = self.Departments.create(
            {
                "name": "ادارة الرقابة والجودة",
                "manager_id": self.quality_manager_employee.id,
            }
        )
        self.visited_department = self.Departments.create({"name": "فرع العمليات"})
        self.section_department = self.Departments.create(
            {
                "name": "الادارة المعنية",
                "manager_id": self.section_manager_employee.id,
            }
        )
        self.non_branch_department = self.Departments.create({"name": "Operations"})

        self.member_employee.department_id = self.quality_department.id
        self.admin_employee.department_id = self.quality_department.id
        self.quality_manager_employee.department_id = self.quality_department.id
        self.section_manager_employee.department_id = self.section_department.id
        self.outsider_employee.department_id = self.visited_department.id

        self.env["ab_quality_assurance.access"].sudo()._sync_quality_manager_group()

        self.section = self.Sections.with_user(self.quality_manager_user).create(
            {
                "name": "Cleanliness",
                "department_id": self.section_department.id,
            }
        )
        self.second_section = self.Sections.with_user(self.quality_manager_user).create(
            {
                "name": "Documentation",
                "department_id": self.section_department.id,
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
        partner_vals = {
            "name": name,
            "email": f"{login}@example.com",
        }
        if "autopost_bills" in self.env["res.partner"]._fields:
            partner_vals["autopost_bills"] = "ask"
        partner = self.env["res.partner"].sudo().create(partner_vals)
        return self.Users.create(
            {
                "name": name,
                "login": login,
                "email": f"{login}@example.com",
                "partner_id": partner.id,
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

    def test_visit_submission_sets_performer_to_submitter_employee(self):
        visit = self.Visits.with_user(self.admin_user).create(
            {
                "department_id": self.visited_department.id,
                "employee_id": self.section_manager_employee.id,
            }
        )
        for line in visit.visit_section_ids.mapped("visit_line_ids"):
            line.with_user(self.admin_user).write({"score": line.max_score})

        visit.with_user(self.admin_user).action_submit_visit()

        self.assertEqual(visit.employee_id, self.admin_employee)

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

    def test_section_department_manager_can_reply_in_visit_chatter(self):
        visit = self.Visits.with_user(self.member_user).create(
            {
                "department_id": self.visited_department.id,
            }
        )
        for line in visit.visit_section_ids.mapped("visit_line_ids"):
            line.with_user(self.member_user).write({"score": line.max_score})
        visit.with_user(self.member_user).action_submit_visit()

        self.assertTrue(self.Visits.with_user(self.section_manager_user).search([("id", "=", visit.id)]))
        self.assertIn(self.section_manager_user.partner_id, visit.message_partner_ids)

        message = visit.with_user(self.section_manager_user).message_post(
            body="The section department manager reviewed the visit."
        )
        self.assertIn("section department manager reviewed", message.body)

        with self.assertRaises(AccessError):
            visit.with_user(self.section_manager_user).write(
                {"notes": "Changing evaluation notes is not allowed."}
            )

        first_line = visit.visit_section_ids.mapped("visit_line_ids").sorted("id")[0]
        with self.assertRaises(AccessError):
            first_line.with_user(self.section_manager_user).write({"score": 0})

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
