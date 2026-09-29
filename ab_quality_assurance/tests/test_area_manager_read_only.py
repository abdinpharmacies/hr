from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user

from ..controllers import quality_visit_export


class TestAreaManagerReadOnly(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.area_group = 'ab_quality_assurance.group_ab_quality_assurance_area_manager_ro'
        cls.area_user = new_test_user(cls.env, login='qa_area_ro', groups=f'base.group_user,{cls.area_group}')
        cls.unlinked_user = new_test_user(cls.env, login='qa_area_unlinked', groups=f'base.group_user,{cls.area_group}')
        cls.manager = new_test_user(
            cls.env, login='qa_area_manager',
            groups='base.group_user,ab_quality_assurance.group_ab_quality_assurance_manager',
        )
        cls.env['ab_hr_employee'].create({'name': 'QA Inspector', 'user_id': cls.manager.id})
        cls.area_employee = cls.env['ab_hr_employee'].create({'name': 'Area Head', 'user_id': cls.area_user.id})
        direct = cls.env['ab_hr_employee'].create({'name': 'Direct Manager', 'parent_id': cls.area_employee.id})
        nested = cls.env['ab_hr_employee'].create({'name': 'Nested Manager', 'parent_id': direct.id})
        unrelated = cls.env['ab_hr_employee'].create({'name': 'Unrelated Manager'})
        cls.branches = cls.env['ab_hr_department'].create([
            {'name': f'فرع {name}', 'manager_id': employee.id}
            for name, employee in [('Area', cls.area_employee), ('Direct', direct), ('Nested', nested), ('Other', unrelated)]
        ])
        # Neither explicit department grants nor department ancestry may broaden the area role.
        cls.area_user.ab_department_ids = cls.branches[-1]
        cls.area_employee.department_id = cls.branches[-1]
        cls.section = cls.env['ab_quality_assurance_section'].create({'name': 'Area Security Section'})
        cls.standard = cls.env['ab_quality_assurance_standard'].create({
            'section_id': cls.section.id, 'title': 'Area Security Standard', 'max_score': 10,
        })
        cls.visits = cls.env['ab_quality_assurance_visit']
        for branch in cls.branches:
            for state in ('draft', 'submitted'):
                visit = cls.visits.with_user(cls.manager).create({'department_id': branch.id})
                if state == 'submitted':
                    visit.visit_section_ids.visit_line_ids.write({'score': 8})
                    visit.action_submit_visit()
                cls.visits |= visit.with_env(cls.env)
        cls.allowed = cls.visits.filtered(lambda visit: visit.department_id != cls.branches[-1])
        cls.denied = cls.visits - cls.allowed
        cls.draft = cls.allowed.filtered(lambda visit: visit.state == 'draft')[:1]
        cls.activity_type = cls.env.ref('mail.mail_activity_data_todo')

    def test_hierarchy_scope_and_no_department_rule_leak(self):
        self.assertFalse(self.area_user.has_group('ab_quality_assurance.group_ab_quality_assurance_ro'))
        for model, records, allowed in [
            ('ab_quality_assurance_visit', self.visits, self.allowed),
            ('ab_quality_assurance_visit_section', self.visits.visit_section_ids, self.allowed.visit_section_ids),
            ('ab_quality_assurance_visit_line', self.visits.visit_section_ids.visit_line_ids, self.allowed.visit_section_ids.visit_line_ids),
        ]:
            scoped = self.env[model].with_user(self.area_user)
            self.assertEqual(set(scoped.search(fields.Domain('id', 'in', records.ids)).ids), set(allowed.ids))
            self.assertFalse(self.env[model].with_user(self.unlinked_user).search([]))
            with self.assertRaises(AccessError):
                (records - allowed).with_user(self.area_user).read(['display_name'])
        self.standard.with_user(self.area_user).read(['title'])
        self.section.with_user(self.area_user).read(['name'])

    def test_dashboard_scope_and_aggregates(self):
        self.env.flush_all()
        dashboard = self.env['ab_quality_assurance_department_dashboard'].with_user(self.area_user)
        rows = dashboard.search([])
        self.assertEqual(set(rows.department_id.ids), set(self.branches[:-1].ids))
        self.assertEqual(sum(rows.mapped('visit_count')), 6)
        for row in rows:
            self.assertEqual((row.visit_count, row.draft_visit_count, row.submitted_visit_count), (2, 1, 1))
            self.assertEqual(row.avg_percentage, 80)
        self.assertEqual(dashboard._read_group([], [], ['visit_count:sum']), [(6,)])
        self.assertFalse(dashboard.with_user(self.unlinked_user).search([]))
        other = dashboard.sudo().search(fields.Domain('department_id', '=', self.branches[-1].id))
        with self.assertRaises(AccessError):
            other.with_user(self.area_user).read(['visit_count'])

    def test_reparenting_branch_manager_updates_scope(self):
        visits = self.visits.with_user(self.area_user)
        self.assertEqual(len(visits.search([])), 6)
        self.branches[1].manager_id.parent_id = self.branches[-1].manager_id
        self.assertEqual(set(visits.search([]).department_id.ids), {self.branches[0].id})

    def test_menu_visibility(self):
        menus = self.env['ir.ui.menu'].with_user(self.area_user)._visible_menu_ids()
        for name in ('visit', 'draft_visit', 'dashboard'):
            self.assertIn(self.env.ref(f'ab_quality_assurance.ab_quality_assurance_{name}_menu').id, menus)
        self.assertNotIn(self.env.ref('ab_quality_assurance.ab_quality_assurance_section_menu').id, menus)
        self.assertFalse(self.draft.with_user(self.area_user).can_use_chatter)

    def test_existing_read_only_role_keeps_department_access_and_chatter(self):
        user = new_test_user(
            self.env, login='qa_existing_ro',
            groups='base.group_user,ab_quality_assurance.group_ab_quality_assurance_ro',
        )
        user.ab_department_ids = self.branches[-1]
        visible = self.visits.with_user(user).search(fields.Domain('id', 'in', self.visits.ids))
        self.assertEqual(set(visible.ids), set(self.denied.ids))
        visit = visible.filtered(lambda item: item.state == 'draft')[:1]
        self.assertTrue(visit.can_use_chatter)
        self.assertTrue(visit.message_post(body='Existing RO behavior'))
        with self.assertRaises(AccessError):
            visit.write({'notes': 'blocked'})

    def test_existing_department_manager_keeps_chatter_and_response(self):
        user = new_test_user(
            self.env, login='qa_existing_department_manager',
            groups='base.group_user,ab_quality_assurance.group_ab_quality_assurance_department_manager',
        )
        employee = self.env['ab_hr_employee'].create({'name': 'Department Reviewer', 'user_id': user.id})
        self.branches[-1].manager_id = employee
        user.ab_department_ids = self.branches[-1]
        self.section.department_id = self.branches[-1]
        visit = self.denied.filtered(lambda item: item.state == 'submitted')[:1].with_user(user)
        self.assertTrue(visit.can_use_chatter)
        self.assertTrue(visit.message_post(body='Department review'))
        line = visit.visit_section_ids.visit_line_ids[:1]
        line.write({'department_response': 'Reviewed'})
        with self.assertRaises(AccessError):
            line.write({'score': 1})

    def test_report_and_export_scope(self):
        reports = self.env['ir.actions.report'].with_user(self.area_user)
        report_name = 'ab_quality_assurance.report_ab_quality_assurance_visit_document'
        for visit in self.allowed:
            html, _ = reports._render_qweb_html(report_name, visit.ids)
            self.assertIn(visit.name.encode(), html)
            self.assertEqual(visit.with_user(self.area_user).action_export_pdf()['type'], 'ir.actions.report')
        with self.assertRaises(AccessError):
            reports._render_qweb_html(report_name, self.denied.ids)
        request = SimpleNamespace(
            env=self.env(user=self.area_user), make_response=lambda data, headers: data,
        )
        with patch.object(quality_visit_export, 'request', request):
            controller = quality_visit_export.AbQualityAssuranceVisitExportController()
            for visit in self.allowed:
                self.assertTrue(controller.download_visit_xlsx(visit.id).get_data().startswith(b'PK'))
            for visit in self.denied:
                with self.assertRaises(AccessError):
                    controller.download_visit_xlsx(visit.id)

    def test_qa_records_cannot_be_mutated(self):
        self.env.flush_all()
        dashboard = self.env['ab_quality_assurance_department_dashboard'].search(
            fields.Domain('department_id', '=', self.draft.department_id.id), limit=1,
        )
        visit_section = self.draft.visit_section_ids[:1]
        line = visit_section.visit_line_ids[:1]
        cases = [
            (self.draft, {'department_id': self.draft.department_id.id}, {'notes': 'blocked'}),
            (visit_section, {'visit_id': self.draft.id, 'section_id': self.section.id}, {'sequence': 99}),
            (line, {'visit_section_id': visit_section.id, 'standard_id': self.standard.id}, {'score': 1}),
            (self.standard, {'section_id': self.section.id, 'title': 'blocked', 'max_score': 10}, {'title': 'blocked'}),
            (self.section, {'name': 'blocked'}, {'name': 'blocked'}),
            (dashboard, {'department_id': self.draft.department_id.id}, {'visit_count': 99}),
        ]
        for record, create_vals, write_vals in cases:
            record = record.with_user(self.area_user)
            for operation in ('create', 'write', 'unlink'):
                with self.subTest(model=record._name, operation=operation), self.assertRaises(AccessError), self.env.cr.savepoint():
                    if operation == 'create':
                        record.create(create_vals)
                    elif operation == 'write':
                        record.write(write_vals)
                    else:
                        record.unlink()
        with self.assertRaises(AccessError):
            self.draft.with_user(self.area_user).action_submit_visit()

    def test_chatter_followers_and_activities_are_read_only(self):
        visit = self.draft.with_user(self.area_user)
        activity = self.draft.activity_schedule(activity_type_id=self.activity_type.id, user_id=self.area_user.id)
        message = self.draft.message_post(body='Original QA note')
        self.draft.message_subscribe(partner_ids=self.area_user.partner_id.ids)
        follower = self.draft.message_follower_ids.filtered(lambda item: item.partner_id == self.area_user.partner_id)
        operations = [
            lambda: visit.message_post(body='blocked'),
            # The mail HTTP controller posts on a sudo recordset.
            lambda: visit.sudo().message_post(body='blocked via controller'),
            lambda: visit.message_subscribe(partner_ids=self.area_user.partner_id.ids),
            lambda: visit.message_unsubscribe(partner_ids=self.area_user.partner_id.ids),
            lambda: visit.activity_schedule(activity_type_id=self.activity_type.id, user_id=self.area_user.id),
            lambda: activity.with_user(self.area_user).write({'summary': 'blocked'}),
            lambda: activity.with_user(self.area_user).unlink(),
            lambda: activity.with_user(self.area_user).action_feedback(feedback='blocked'),
            lambda: follower.with_user(self.area_user).write({'subtype_ids': [fields.Command.clear()]}),
            lambda: follower.with_user(self.area_user).unlink(),
            lambda: message.with_user(self.area_user).write({'body': 'blocked'}),
            lambda: message.with_user(self.area_user).unlink(),
            lambda: message.with_user(self.area_user).sudo()._message_reaction(
                '👍', 'add', self.area_user.partner_id, self.env['mail.guest'],
            ),
            lambda: self.env['mail.message'].with_user(self.area_user).create({
                'model': visit._name, 'res_id': visit.id, 'body': 'blocked',
            }),
            lambda: self.env['mail.followers'].with_user(self.area_user).create({
                'res_model': visit._name, 'res_id': visit.id, 'partner_id': self.unlinked_user.partner_id.id,
            }),
            lambda: self.env['mail.activity'].with_user(self.area_user).with_context(
                default_res_model_id=self.env['ir.model']._get_id(visit._name), default_res_id=visit.id,
            ).create({'activity_type_id': self.activity_type.id, 'user_id': self.area_user.id}),
        ]
        for index, operation in enumerate(operations):
            with self.subTest(operation=index), self.assertRaises(AccessError), self.env.cr.savepoint():
                operation()
        self.assertTrue(activity.exists())
        # Mail on other models retains its original behavior for the same user.
        personal_activity = self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get_id('res.partner'),
            'res_id': self.area_user.partner_id.id, 'activity_type_id': self.activity_type.id,
            'user_id': self.area_user.id,
        })
        personal_activity = personal_activity.with_user(self.area_user)
        personal_activity.write({'summary': 'Allowed'})
        personal_activity.action_feedback(feedback='Done')

    def test_higher_privileges_override_area_role(self):
        for group in ('ab_quality_assurance.group_ab_quality_assurance_manager', 'base.group_system'):
            user = new_test_user(self.env, login=f'qa_override_{group}', groups=f'base.group_user,{self.area_group},{group}')
            self.assertTrue(self.denied.with_user(user).search(fields.Domain('id', 'in', self.denied.ids)))
            self.assertTrue(self.draft.with_user(user).can_use_chatter)
            self.draft.with_user(user).write({'notes': 'Manager update'})
            self.draft.with_user(user).message_post(body='Manager note')
            self.draft.with_user(user).message_subscribe(partner_ids=user.partner_id.ids)
            activity = self.draft.with_user(user).activity_schedule(activity_type_id=self.activity_type.id, user_id=user.id)
            activity.action_feedback(feedback='Manager done')
            self.env.flush_all()
            rows = self.env['ab_quality_assurance_department_dashboard'].with_user(user).search([])
            self.assertIn(self.branches[-1], rows.department_id)
