from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSelfInventory(TransactionCase):
    def setUp(self):
        super().setUp()
        self.group_user = self.env.ref('base.group_user')
        self.group_public = self.env.ref('base.group_public')
        self.group_requester = self.env.ref('ab_self_inventory.group_ab_self_inventory_requester')
        self.group_receiver = self.env.ref('ab_self_inventory.group_ab_self_inventory_receiver')

        self.requester = self.env.ref('base.user_admin').sudo()
        self.receiver = self.env.ref('base.public_user').sudo()
        self.requester.write({'group_ids': [(4, self.group_requester.id)]})
        self.receiver.write({
            'group_ids': [
                (3, self.group_public.id),
                (4, self.group_user.id),
                (4, self.group_receiver.id),
            ],
        })

        self.branch = self.env['ab_store'].sudo().create({
            'name': 'Test Branch',
            'code': 'SITB',
            'store_type': 'branch',
            'eplus_serial': 9001,
        })
        self.other_branch = self.env['ab_store'].sudo().create({
            'name': 'Other Test Branch',
            'code': 'SOIB',
            'store_type': 'branch',
            'eplus_serial': 9002,
        })
        self.env['ab_hr_department'].sudo().create({
            'name': 'Self Inventory Branch Department',
            'store_id': self.branch.id,
            'user_id': self.receiver.id,
        })
        self.env['ab_hr_department'].sudo().create({
            'name': 'Other Self Inventory Branch Department',
            'store_id': self.other_branch.id,
            'user_id': self.requester.id,
        })

        card = self.env['ab_product_card'].sudo().create({'name': 'Self Inventory Product Card'})
        self.product = self.env['ab_product'].sudo().create({
            'product_card_id': card.id,
            'code': 'SIP001',
            'eplus_serial': 7001,
        })
        second_card = self.env['ab_product_card'].sudo().create({'name': 'Second Self Inventory Product Card'})
        self.second_product = self.env['ab_product'].sudo().create({
            'product_card_id': second_card.id,
            'code': 'SIP002',
            'eplus_serial': 7002,
        })

    def test_submit_request_creates_independent_process(self):
        request = self.env['ab_self_inventory_request'].with_user(self.requester).create({
            'branch_id': self.branch.id,
            'note': 'Count slow moving items.',
            'line_ids': [(0, 0, {
                'selected': True,
                'product_id': self.product.id,
                'eplus_item_id': self.product.eplus_serial,
                'eplus_item_code': self.product.code,
                'system_qty': 12.0,
                'matched_by': 'eplus_serial',
            })],
        })

        request.action_submit_request()

        self.assertEqual(request.state, 'submitted')
        self.assertTrue(request.process_id)
        self.assertEqual(request.process_id.request_id, request)
        self.assertEqual(request.process_id.branch_id, self.branch)
        self.assertEqual(request.process_id.line_ids.product_id, self.product)
        self.assertEqual(request.process_id.line_ids.system_qty, 12.0)

        process_line = request.process_id.line_ids
        process_line.with_user(self.receiver).write({
            'actual_qty_set': True,
            'actual_qty': 10.0,
            'explanation': 'Two units short.',
        })
        request.process_id.with_user(self.receiver).action_submit_process()

        self.assertEqual(request.process_id.state, 'submitted')
        self.assertEqual(process_line.difference_qty, -2.0)
        self.assertEqual(process_line.shortage_qty, 2.0)
        self.assertEqual(process_line.extra_qty, 0.0)

    def test_receiver_only_sees_own_branch_processes(self):
        Process = self.env['ab_self_inventory_process'].sudo()
        branch_process = Process.create({
            'requester_id': self.requester.id,
            'branch_id': self.branch.id,
        })
        other_process = Process.create({
            'requester_id': self.requester.id,
            'branch_id': self.other_branch.id,
        })

        receiver_processes = self.env['ab_self_inventory_process'].with_user(self.receiver)
        self.assertEqual(receiver_processes.search_count([('id', '=', branch_process.id)]), 1)
        self.assertEqual(receiver_processes.search_count([('id', '=', other_process.id)]), 0)

    def test_bulk_select_and_delete_request_lines(self):
        request = self.env['ab_self_inventory_request'].with_user(self.requester).create({
            'branch_id': self.branch.id,
            'line_ids': [
                (0, 0, {
                    'selected': False,
                    'product_id': self.product.id,
                    'eplus_item_id': self.product.eplus_serial,
                    'eplus_item_code': self.product.code,
                    'system_qty': 12.0,
                    'matched_by': 'eplus_serial',
                }),
                (0, 0, {
                    'selected': True,
                    'product_id': self.second_product.id,
                    'eplus_item_id': self.second_product.eplus_serial,
                    'eplus_item_code': self.second_product.code,
                    'system_qty': 7.0,
                    'matched_by': 'eplus_serial',
                }),
            ],
        })

        request.action_select_all_lines()
        self.assertEqual(request.selected_line_count, 2)

        request.action_unselect_all_lines()
        self.assertEqual(request.selected_line_count, 0)

        request.line_ids.filtered(lambda line: line.product_id == self.product).selected = True
        request.action_delete_unselected_lines()
        self.assertEqual(request.line_ids.product_id, self.product)

        request.action_delete_selected_lines()
        self.assertFalse(request.line_ids)

    def test_receiver_cannot_change_or_delete_received_products(self):
        request = self.env['ab_self_inventory_request'].with_user(self.requester).create({
            'branch_id': self.branch.id,
            'line_ids': [(0, 0, {
                'selected': True,
                'product_id': self.product.id,
                'eplus_item_id': self.product.eplus_serial,
                'eplus_item_code': self.product.code,
                'system_qty': 12.0,
                'matched_by': 'eplus_serial',
            })],
        })
        request.action_submit_request()
        process_line = request.process_id.line_ids.with_user(self.receiver)

        with self.assertRaises(ValidationError):
            process_line.write({'product_id': self.second_product.id})

        with self.assertRaises(ValidationError):
            process_line.write({'system_qty': 9.0})

        with self.assertRaises(ValidationError):
            process_line.unlink()

        process_line.write({
            'actual_qty_set': True,
            'actual_qty': 11.0,
            'explanation': 'One unit short.',
        })
        self.assertEqual(process_line.actual_qty, 11.0)

    def test_available_products_are_limited_to_branch_stock(self):
        process = self.env['ab_self_inventory_process'].sudo().create({
            'requester_id': self.requester.id,
            'branch_id': self.branch.id,
        })

        with patch.object(
            type(process),
            '_fetch_branch_stock_product_rows',
            return_value=[
                {'itm_id': self.product.eplus_serial, 'itm_code': self.product.code},
            ],
        ):
            self.assertEqual(process.available_product_ids, self.product)

    def test_manually_added_line_uses_branch_stock_qty(self):
        process = self.env['ab_self_inventory_process'].sudo().create({
            'requester_id': self.requester.id,
            'branch_id': self.branch.id,
        })
        Process = type(process)

        with patch.object(Process, '_get_branch_product_stock_qty', return_value=5.0):
            line = self.env['ab_self_inventory_process_line'].with_user(self.receiver).create({
                'process_id': process.id,
                'product_id': self.product.id,
            })
        self.assertEqual(line.system_qty, 5.0)

        with patch.object(Process, '_get_branch_product_stock_qty', return_value=None):
            with self.assertRaises(ValidationError):
                self.env['ab_self_inventory_process_line'].with_user(self.receiver).create({
                    'process_id': process.id,
                    'product_id': self.second_product.id,
                })
