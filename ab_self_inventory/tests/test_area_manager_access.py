from io import BytesIO
from unittest.mock import patch

import xlsxwriter
from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAreaManagerAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.area_group = cls.env.ref('ab_self_inventory.group_ab_self_inventory_area_manager_readonly')
        cls.reader = cls.env['res.users'].create({
            'name': 'Area reader', 'login': 'test_self_inventory_area_reader',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id, cls.area_group.id])],
        })
        cls.employee = cls.env['ab_hr_employee'].create({'name': 'Area employee', 'user_id': cls.reader.id})
        cls.areas = cls.env['ab_hr_region'].create([{'name': 'Area A'}, {'name': 'Area B'}])
        cls.branches = cls.env['ab_store'].create([
            {'name': 'Branch A', 'code': 'TEST-AREA-A', 'store_type': 'branch'},
            {'name': 'Branch B', 'code': 'TEST-AREA-B', 'store_type': 'branch'},
            {'name': 'Warehouse A', 'code': 'TEST-AREA-W', 'store_type': 'main'},
        ])
        cls.managed = cls.env['ab_hr_department'].create({
            'name': 'Managed area', 'manager_id': cls.employee.id,
            'workplace_region': cls.areas[0].id,
        })
        cls.departments = cls.env['ab_hr_department'].create([
            {'name': 'Department A', 'workplace_region': cls.areas[0].id, 'store_id': cls.branches[0].id},
            {'name': 'Department B', 'workplace_region': cls.areas[1].id, 'store_id': cls.branches[1].id},
            {'name': 'Warehouse', 'workplace_region': cls.areas[0].id, 'store_id': cls.branches[2].id},
        ])
        cls.product = cls.env['ab_product'].create({'code': 'TEST-AREA-P', 'product_card_id': cls.env['ab_product_card'].create({'name': 'Area product'}).id})
        cls.processes = cls.env['ab_self_inventory_process'].create([
            {'name': 'AREA-%s-%s' % (branch.id, state), 'branch_id': branch.id,
             'line_ids': [Command.create({'product_id': cls.product.id, 'requested': True, 'system_qty': 10})]}
            for branch in cls.branches for state in ('draft', 'in_progress', 'submitted', 'cancelled')
        ])
        for index, process in enumerate(cls.processes):
            process.state = ('draft', 'in_progress', 'submitted', 'cancelled')[index % 4]
        cls.allowed = cls.processes.filtered(lambda p: p.branch_id == cls.branches[0])
        cls.denied = cls.processes - cls.allowed

    def test_branch_isolation_all_states_and_direct_read(self):
        records = self.env['ab_self_inventory_process'].with_user(self.reader).search(fields.Domain('id', 'in', self.processes.ids))
        self.assertEqual(set(records.ids), set(self.allowed.ids))
        lines = self.env['ab_self_inventory_process_line'].with_user(self.reader).search(fields.Domain('process_id', 'in', self.processes.ids))
        self.assertEqual(set(lines.ids), set(self.allowed.line_ids.ids))
        self.allowed.with_user(self.reader).read(['name', 'branch_id', 'state'])
        for record in (self.denied[0], self.denied[0].line_ids):
            with self.assertRaises(AccessError):
                record.with_user(self.reader).read()

    def test_multiple_areas_after_cache_refresh(self):
        self.test_branch_isolation_all_states_and_direct_read()
        second = self.env['ab_hr_employee'].create({'name': 'Second linked employee', 'user_id': self.reader.id})
        other = self.env['ab_hr_department'].create({'name': 'Other managed area', 'manager_id': second.id, 'workplace_region': self.areas[1].id})
        # HR changes require an explicit cache refresh (or server restart).
        self.env.registry.clear_cache()
        self.assertEqual(set(self.reader._get_self_inventory_area_branch_ids()), set(self.branches[:2].ids))
        self.denied.filtered(lambda p: p.branch_id == self.branches[1]).with_user(self.reader).check_access('read')
        other.manager_id = False
        self.env.registry.clear_cache()
        self.test_branch_isolation_all_states_and_direct_read()
        self.departments[0].workplace_region = self.areas[1]
        self.env.registry.clear_cache()
        self.assertFalse(self.env['ab_self_inventory_process'].with_user(self.reader).search(fields.Domain('id', 'in', self.processes.ids)))

    def test_missing_mapping_denies_all(self):
        for field, value in [('workplace_region', False), ('manager_id', False)]:
            with self.env.cr.savepoint():
                previous = self.managed[field]
                self.managed[field] = value
                self.env.registry.clear_cache()
                self.assertFalse(self.env['ab_self_inventory_process'].with_user(self.reader).search([]))
                self.managed[field] = previous
        self.employee.user_id = False
        self.env.registry.clear_cache()
        self.assertFalse(self.env['ab_self_inventory_process'].with_user(self.reader).search([]))

    def test_read_only_acl_and_mutation_rpc(self):
        for model in ('ab_self_inventory_process', 'ab_self_inventory_process_line'):
            for operation in ('create', 'write', 'unlink'):
                with self.assertRaises(AccessError):
                    self.env[model].with_user(self.reader).check_access(operation)
        process = self.allowed.filtered(lambda p: p.state == 'draft').with_user(self.reader)
        for method in ('action_submit_process', 'action_cancel', 'action_reset_to_draft', 'action_sync_requested_product_quantities', 'action_open_import_wizard', 'action_open_manual_add_line_wizard'):
            with self.assertRaises(AccessError):
                getattr(process, method)()
        with self.assertRaises(AccessError):
            process.write({'branch_note': 'forbidden'})
        with self.assertRaises(AccessError):
            process.unlink()

    def test_menus_and_excluded_models(self):
        visible = self.env['ir.ui.menu'].with_user(self.reader)._visible_menu_ids()
        self.assertIn(self.env.ref('ab_self_inventory.menu_ab_self_inventory_process').id, visible)
        for menu in self.env['ir.ui.menu'].search(fields.Domain('parent_id', '=', self.env.ref('ab_self_inventory.menu_ab_self_inventory_root').id)):
            if menu != self.env.ref('ab_self_inventory.menu_ab_self_inventory_process'):
                self.assertNotIn(menu.id, visible)
        for model in ('ab_self_inventory_request', 'ab_self_inventory_request_batch'):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.reader).check_access('read')

    def test_standard_group_assignment(self):
        self.assertEqual(
            self.area_group.privilege_id,
            self.env.ref('ab_self_inventory.privilege_ab_self_inventory'),
        )
        self.assertEqual(
            self.area_group.privilege_id.category_id,
            self.env.ref('ab_self_inventory.module_category_ab_self_inventory'),
        )
        for role in ('readonly', 'requester', 'receiver'):
            group = self.env.ref('ab_self_inventory.group_ab_self_inventory_' + role)
            self.reader.group_ids = [Command.link(group.id)]
            self.assertIn(group, self.reader.all_group_ids)
            self.reader.group_ids = [Command.unlink(group.id)]
            group.write({'user_ids': [Command.link(self.reader.id)]})
            self.assertIn(group, self.reader.all_group_ids)
            group.write({'user_ids': [Command.unlink(self.reader.id)]})

    def test_manager_exception(self):
        self.reader.group_ids = [Command.link(self.env.ref('ab_self_inventory.group_ab_self_inventory_manager').id)]
        self.processes.with_user(self.reader).check_access('read')
        self.assertFalse(self.reader._is_self_inventory_area_reader())

    def test_administrator_exception(self):
        self.reader.group_ids = [Command.link(self.env.ref('base.group_system').id)]
        self.processes.with_user(self.reader).check_access('read')
        self.assertFalse(self.reader._is_self_inventory_area_reader())

    def test_saved_report_does_not_refresh_or_change_counts(self):
        process = self.allowed.with_user(self.reader)
        before = self.allowed.line_ids.read(['system_qty', 'count_snapshot_qty', 'actual_qty', 'is_counted', 'explanation'])
        with patch.object(type(process), '_refresh_system_stock_quantities', side_effect=AssertionError('Stock refresh forbidden')):
            process.action_export_saved_report()
            process.action_export_count_sheet()
            output = BytesIO()
            with xlsxwriter.Workbook(output, {'in_memory': True}) as workbook:
                self.env['report.ab_self_inventory.count_sheet_xlsx'].with_user(self.reader).generate_xlsx_report(workbook, {}, process)
            self.assertTrue(output.getvalue().startswith(b'PK'))
        self.assertEqual(before, self.allowed.line_ids.read(['system_qty', 'count_snapshot_qty', 'actual_qty', 'is_counted', 'explanation']))
        with self.assertRaises(AccessError):
            self.denied.with_user(self.reader).action_export_saved_report()

    def test_direct_crud_denied(self):
        process = self.allowed.filtered(lambda p: p.state == 'draft').with_user(self.reader)
        line = process.line_ids
        for record in (process, line):
            with self.assertRaises(AccessError):
                record.unlink()
        with self.assertRaises(AccessError):
            line.write({'actual_qty': 99})
        with self.assertRaises(AccessError):
            self.env['ab_self_inventory_process'].with_user(self.reader).create({'branch_id': self.branches[0].id})
        with self.assertRaises(AccessError):
            self.env['ab_self_inventory_process_line'].with_user(self.reader).create({'process_id': process.id, 'product_id': self.product.id})

    def test_standard_implied_group_assignment(self):
        wrapper = self.env['res.groups'].create({'name': 'Area wrapper', 'implied_ids': [Command.link(self.area_group.id)]})
        self.reader.group_ids = [Command.link(wrapper.id)]
        receiver = self.env.ref('ab_self_inventory.group_ab_self_inventory_receiver')
        wrapper.implied_ids = [Command.link(receiver.id)]
        self.assertIn(receiver, self.reader.all_group_ids)

    def test_area_views_and_grid_are_read_only(self):
        Process = self.env['ab_self_inventory_process'].with_user(self.reader)
        form = Process.get_view(self.env.ref('ab_self_inventory.view_ab_self_inventory_process_form').id, 'form')
        arch = etree.fromstring(form['arch'])
        self.assertFalse(arch.xpath("//field[@name='request_id']"))
        self.assertTrue(arch.xpath("//button[@name='action_export_saved_report']"))
        for action in ('action_submit_process', 'action_cancel', 'action_open_import_wizard', 'action_sync_requested_product_quantities', 'action_reset_to_draft'):
            self.assertFalse(arch.xpath("//button[@name='%s']" % action))
        active = self.allowed.filtered(lambda p: p.state == 'draft').with_user(self.reader)
        self.assertFalse(active.can_sync_requested_stock)
        self.assertFalse(active.can_refresh_system_stock)
        self.assertTrue(active.action_get_grid_rows()['rows'])
