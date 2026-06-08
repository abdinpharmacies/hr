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

        branch_seed = (self.env['ab_store'].sudo().search([], order='id desc', limit=1).id or 0) + 1000000
        self.governorate_text = 'GovFilter%s' % branch_seed
        self.branch = self.env['ab_store'].sudo().create({
            'name': '%s فرع Test Branch' % self.governorate_text,
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
        self.same_governorate_branch = self.env['ab_store'].sudo().create({
            'name': '%s فرع Same Governorate Test Branch' % self.governorate_text,
            'code': 'SGIB',
            'store_type': 'branch',
            'eplus_serial': 9003,
        })
        self.same_governorate_non_branch_name = self.env['ab_store'].sudo().create({
            'name': '%s Warehouse Name Without Arabic Branch Word' % self.governorate_text,
            'code': 'SGNB',
            'store_type': 'branch',
            'eplus_serial': 9004,
        })
        self.env.cr.execute(
            "SELECT setval(pg_get_serial_sequence(%s, %s), COALESCE(MAX(id), 0) + 1, false) FROM ab_hr_department",
            ('ab_hr_department', 'id'),
        )
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

        product_seed = (self.env['ab_product'].sudo().search([], order='id desc', limit=1).id or 0) + 1000000
        card = self.env['ab_product_card'].sudo().create({'name': 'Self Inventory Product Card'})
        self.product = self.env['ab_product'].sudo().create({
            'product_card_id': card.id,
            'code': 'SIP%s' % product_seed,
            'eplus_serial': product_seed,
            'default_cost': 3.0,
        })
        second_card = self.env['ab_product_card'].sudo().create({'name': 'Second Self Inventory Product Card'})
        self.second_product = self.env['ab_product'].sudo().create({
            'product_card_id': second_card.id,
            'code': 'SIP%s' % (product_seed + 1),
            'eplus_serial': product_seed + 1,
            'default_cost': 4.0,
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
            'actual_qty': 10.0,
            'explanation': 'Two units short.',
        })
        request.process_id.with_user(self.receiver).action_submit_process()

        self.assertEqual(request.process_id.state, 'submitted')
        self.assertEqual(process_line.difference_qty, -2.0)
        self.assertEqual(process_line.shortage_qty, 6.0)
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

    def test_manually_added_line_can_be_deleted_in_draft(self):
        process = self.env['ab_self_inventory_process'].sudo().create({
            'requester_id': self.requester.id,
            'branch_id': self.branch.id,
        })
        with patch.object(type(process), '_get_branch_product_stock_qty', return_value=5.0):
            line = self.env['ab_self_inventory_process_line'].with_user(self.receiver).create({
                'process_id': process.id,
                'product_id': self.product.id,
            })
        line.unlink()
        self.assertFalse(line.exists())

    def test_receiver_cannot_add_duplicate_product(self):
        process = self.env['ab_self_inventory_process'].sudo().create({
            'requester_id': self.requester.id,
            'branch_id': self.branch.id,
        })
        with patch.object(type(process), '_get_branch_product_stock_qty', return_value=5.0):
            self.env['ab_self_inventory_process_line'].with_user(self.receiver).create({
                'process_id': process.id,
                'product_id': self.product.id,
            })
            with self.assertRaisesRegex(ValidationError, "already exists product"):
                self.env['ab_self_inventory_process_line'].with_user(self.receiver).create({
                    'process_id': process.id,
                    'product_id': self.product.id,
                })

    def test_available_products_exclude_existing_process_lines(self):
        process = self.env['ab_self_inventory_process'].sudo().create({
            'requester_id': self.requester.id,
            'branch_id': self.branch.id,
        })
        with patch.object(
            type(process),
            '_fetch_branch_stock_product_rows',
            return_value=[
                {'itm_id': self.product.eplus_serial, 'itm_code': self.product.code},
                {'itm_id': self.second_product.eplus_serial, 'itm_code': self.second_product.code},
            ],
        ):
            self.assertIn(self.product, process.available_product_ids)
            self.env['ab_self_inventory_process_line'].sudo().create({
                'process_id': process.id,
                'product_id': self.product.id,
                'system_qty': 5.0,
                'requested': True,
            })
            process.invalidate_recordset(['available_product_ids'])
            self.assertNotIn(self.product, process.available_product_ids)
            self.assertIn(self.second_product, process.available_product_ids)

    def test_fetch_branch_stock_requires_rows(self):
        request = self.env['ab_self_inventory_request'].with_user(self.requester).create({
            'branch_id': self.branch.id,
        })
        with patch.object(type(request), '_fetch_branch_stock_rows', return_value=[]):
            with self.assertRaises(ValidationError):
                request.action_fetch_branch_stock()

    def test_fetch_branch_stock_does_not_preselect_products(self):
        request = self.env['ab_self_inventory_request'].with_user(self.requester).create({
            'branch_id': self.branch.id,
        })
        with patch.object(type(request), '_fetch_branch_stock_rows', return_value=[{
            'itm_id': self.product.eplus_serial,
            'itm_code': self.product.code,
            'system_qty': 12.0,
            'extra_data': {},
        }]):
            request.action_fetch_branch_stock()

        self.assertEqual(len(request.line_ids), 1)
        self.assertFalse(request.line_ids.selected)
        self.assertEqual(request.selected_line_count, 0)

    def test_batch_fetches_grouped_branch_lines(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_ids': [(6, 0, [self.branch.id, self.other_branch.id])],
            'note': 'Count both branches.',
        })

        def fake_fetch(rec, branch):
            if branch == self.branch:
                return [{
                    'itm_id': self.product.eplus_serial,
                    'itm_code': self.product.code,
                    'system_qty': 12.0,
                    'extra_data': {},
                }]
            return [{
                'itm_id': self.second_product.eplus_serial,
                'itm_code': self.second_product.code,
                'system_qty': 7.0,
                'extra_data': {},
            }]

        with patch.object(type(batch), '_fetch_branch_stock_rows', fake_fetch):
            batch.action_fetch_branch_stocks()

        self.assertEqual(len(batch.line_ids), 2)
        self.assertEqual(set(batch.line_ids.mapped('branch_id').ids), {self.branch.id, self.other_branch.id})
        self.assertEqual(batch.selected_line_count, 0)
        self.assertFalse(any(batch.line_ids.mapped('selected')))
        self.assertEqual(
            batch.line_ids.filtered(lambda line: line.branch_id == self.branch).system_qty,
            12.0,
        )
        self.assertEqual(
            batch.line_ids.filtered(lambda line: line.branch_id == self.other_branch).system_qty,
            7.0,
        )

    def test_batch_adds_all_branches_matching_governorate_name(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_filter_mode': 'governorate_name',
            'branch_governorate_name': self.governorate_text,
            'branch_ids': [(6, 0, [self.other_branch.id])],
        })

        self.assertEqual(batch.governorate_branch_count, 2)
        action = batch.action_add_governorate_branches()

        self.assertIn(self.branch, batch.branch_ids)
        self.assertIn(self.same_governorate_branch, batch.branch_ids)
        self.assertIn(self.other_branch, batch.branch_ids)
        self.assertNotIn(self.same_governorate_non_branch_name, batch.branch_ids)
        self.assertEqual(action['params']['next']['tag'], 'reload')

    def test_batch_adds_branches_matching_branch_name(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_filter_mode': 'branch_name',
            'branch_ids': [(6, 0, [self.branch.id, self.same_governorate_non_branch_name.id])],
        })

        self.assertEqual(batch.governorate_branch_count, 2)
        self.assertEqual(set(batch.branch_ids.ids), {self.branch.id, self.same_governorate_non_branch_name.id})

    def test_batch_branch_name_mode_requires_selected_branches(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_filter_mode': 'branch_name',
        })

        with self.assertRaisesRegex(ValidationError, "Select at least one branch"):
            batch.action_add_matching_branches()

    def test_submitted_batch_cannot_add_governorate_branches(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_governorate_name': self.governorate_text,
            'branch_ids': [(6, 0, [self.branch.id])],
            'state': 'submitted',
        })

        with self.assertRaises(ValidationError):
            batch.action_add_governorate_branches()

    def test_batch_bulk_select_and_delete_lines(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_ids': [(6, 0, [self.branch.id, self.other_branch.id])],
            'line_ids': [
                (0, 0, {
                    'branch_id': self.branch.id,
                    'selected': False,
                    'product_id': self.product.id,
                    'eplus_item_id': self.product.eplus_serial,
                    'eplus_item_code': self.product.code,
                    'system_qty': 12.0,
                    'matched_by': 'eplus_serial',
                }),
                (0, 0, {
                    'branch_id': self.other_branch.id,
                    'selected': True,
                    'product_id': self.second_product.id,
                    'eplus_item_id': self.second_product.eplus_serial,
                    'eplus_item_code': self.second_product.code,
                    'system_qty': 7.0,
                    'matched_by': 'eplus_serial',
                }),
            ],
        })

        batch.action_select_all_lines()
        self.assertEqual(batch.selected_line_count, 2)

        batch.action_unselect_all_lines()
        self.assertEqual(batch.selected_line_count, 0)

        batch.line_ids.filtered(lambda line: line.product_id == self.product).selected = True
        batch.action_delete_unselected_lines()
        self.assertEqual(batch.line_ids.product_id, self.product)

        batch.action_delete_selected_lines()
        self.assertFalse(batch.line_ids)

    def test_batch_line_list_bulk_buttons_use_context_batch(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_ids': [(6, 0, [self.branch.id])],
            'line_ids': [(0, 0, {
                'branch_id': self.branch.id,
                'selected': False,
                'product_id': self.product.id,
                'eplus_item_id': self.product.eplus_serial,
                'eplus_item_code': self.product.code,
                'system_qty': 12.0,
                'matched_by': 'eplus_serial',
            })],
        })

        action = self.env['ab_self_inventory_request_batch_line'].with_user(self.requester).with_context(
            default_batch_id=batch.id
        ).action_select_all_lines()

        self.assertTrue(batch.line_ids.selected)
        self.assertEqual(action['tag'], 'reload')

    def test_batch_line_list_bulk_buttons_require_batch_context(self):
        with self.assertRaises(ValidationError):
            self.env['ab_self_inventory_request_batch_line'].with_user(self.requester).action_select_all_lines()

    def test_batch_submit_creates_one_request_and_process_per_branch(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_ids': [(6, 0, [self.branch.id, self.other_branch.id])],
            'note': 'Count both branches.',
            'line_ids': [
                (0, 0, {
                    'branch_id': self.branch.id,
                    'selected': True,
                    'product_id': self.product.id,
                    'eplus_item_id': self.product.eplus_serial,
                    'eplus_item_code': self.product.code,
                    'system_qty': 12.0,
                    'matched_by': 'eplus_serial',
                    'note': 'Branch one item.',
                }),
                (0, 0, {
                    'branch_id': self.other_branch.id,
                    'selected': True,
                    'product_id': self.second_product.id,
                    'eplus_item_id': self.second_product.eplus_serial,
                    'eplus_item_code': self.second_product.code,
                    'system_qty': 7.0,
                    'matched_by': 'eplus_serial',
                    'note': 'Branch two item.',
                }),
            ],
        })

        batch.action_submit_batch()

        self.assertEqual(batch.state, 'submitted')
        self.assertEqual(batch.request_count, 2)
        self.assertEqual(batch.process_count, 2)
        self.assertEqual(set(batch.request_ids.mapped('branch_id').ids), {self.branch.id, self.other_branch.id})
        for request in batch.request_ids:
            self.assertEqual(request.state, 'submitted')
            self.assertEqual(request.batch_id, batch)
            self.assertEqual(request.note, 'Count both branches.')
            self.assertTrue(request.process_id)
            self.assertEqual(request.process_id.branch_id, request.branch_id)
            self.assertEqual(request.process_id.line_ids.system_qty, request.line_ids.system_qty)
        self.assertTrue(all(line.request_id for line in batch.line_ids))

    def test_batch_add_product_codes_to_selected_branches(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_ids': [(6, 0, [self.branch.id, self.other_branch.id])],
            'product_codes_text': '%s, %s' % (self.product.code, self.second_product.code),
        })

        def fake_fetch(rec, branch):
            if branch == self.branch:
                return [{
                    'itm_id': self.product.eplus_serial,
                    'itm_code': self.product.code,
                    'system_qty': 12.0,
                    'extra_data': {},
                }]
            return [
                {
                    'itm_id': self.product.eplus_serial,
                    'itm_code': self.product.code,
                    'system_qty': 5.0,
                    'extra_data': {},
                },
                {
                    'itm_id': self.second_product.eplus_serial,
                    'itm_code': self.second_product.code,
                    'system_qty': 7.0,
                    'extra_data': {},
                },
            ]

        with patch.object(type(batch), '_fetch_branch_stock_rows', fake_fetch):
            action = batch.action_add_product_codes()

        self.assertEqual(len(batch.line_ids), 3)
        self.assertEqual(batch.selected_line_count, 3)
        self.assertEqual(batch.line_count, 3)
        self.assertTrue(all(batch.line_ids.mapped('selected')))
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'ab_inventory_bulk_code_results')
        params = action['params']
        self.assertEqual(params['branches_processed'], 2)
        self.assertEqual(params['products_added'], 3)
        self.assertEqual(params['products_missing'], 0)
        self.assertFalse(params['has_missing'])
        self.assertFalse(params['is_empty'])
        self.assertEqual(len(params['branch_results']), 2)
        self.assertEqual(len(params['all_missing_codes']), 0)
        self.assertEqual(
            batch.line_ids.filtered(lambda line: line.branch_id == self.branch).product_id,
            self.product,
        )
        other_branch_lines = batch.line_ids.filtered(lambda line: line.branch_id == self.other_branch)
        self.assertEqual(set(other_branch_lines.mapped('product_id').ids), {self.product.id, self.second_product.id})

    def test_batch_add_product_codes_does_not_duplicate_existing_lines(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_ids': [(6, 0, [self.branch.id])],
            'product_codes_text': self.product.code,
            'line_ids': [(0, 0, {
                'branch_id': self.branch.id,
                'selected': True,
                'product_id': self.product.id,
                'eplus_item_id': self.product.eplus_serial,
                'eplus_item_code': self.product.code,
                'system_qty': 12.0,
                'matched_by': 'eplus_serial',
            })],
        })

        with patch.object(type(batch), '_fetch_branch_stock_rows', return_value=[{
            'itm_id': self.product.eplus_serial,
            'itm_code': self.product.code,
            'system_qty': 12.0,
            'extra_data': {},
        }]):
            with self.assertRaises(ValidationError):
                batch.action_add_product_codes()

        self.assertEqual(len(batch.line_ids), 1)

    def test_batch_submit_requires_multiple_branches(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_ids': [(6, 0, [self.branch.id])],
            'line_ids': [(0, 0, {
                'branch_id': self.branch.id,
                'selected': True,
                'product_id': self.product.id,
                'eplus_item_id': self.product.eplus_serial,
                'eplus_item_code': self.product.code,
                'system_qty': 12.0,
                'matched_by': 'eplus_serial',
            })],
        })

        with self.assertRaisesRegex(ValidationError, "Requests view"):
            batch.action_submit_batch()

    def test_batch_lines_action_shows_all_lines(self):
        batch = self.env['ab_self_inventory_request_batch'].with_user(self.requester).create({
            'branch_ids': [(6, 0, [self.branch.id])],
            'line_ids': [
                (0, 0, {
                    'branch_id': self.branch.id,
                    'selected': True,
                    'product_id': self.product.id,
                    'eplus_item_id': self.product.eplus_serial,
                    'eplus_item_code': self.product.code,
                    'system_qty': 12.0,
                    'matched_by': 'eplus_serial',
                }),
                (0, 0, {
                    'branch_id': self.branch.id,
                    'selected': False,
                    'eplus_item_id': 999999,
                    'eplus_item_code': 'UNMATCHED999999',
                    'system_qty': 4.0,
                    'matched_by': 'none',
                }),
            ],
        })

        self.assertEqual(len(batch.line_ids), 2)
        self.assertEqual(batch.line_count, 2)
        self.assertEqual(len(batch.action_open_lines()['domain']), 1)
        self.assertEqual(batch.action_open_lines()['domain'][0], ('batch_id', '=', batch.id))
