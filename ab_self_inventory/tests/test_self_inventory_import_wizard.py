import base64
import io
from unittest.mock import patch

import openpyxl

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


class FakeEplusCursor:
    description = [('itm_id',), ('itm_code',), ('system_qty',)]

    def __init__(self, rows, queries):
        self.rows = rows
        self.queries = queries

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params):
        self.queries.append((query, params))

    def fetchall(self):
        return self.rows


class FakeEplusConnection:
    def __init__(self, rows, queries):
        self.rows = rows
        self.queries = queries

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return FakeEplusCursor(self.rows, self.queries)


@tagged('post_install', '-at_install')
class TestSelfInventoryImportWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.receiver = cls.env['res.users'].search([]).filtered(
            lambda user: user.has_group('ab_self_inventory.group_ab_self_inventory_receiver')
            and not user.has_group('ab_self_inventory.group_ab_self_inventory_manager')
            and user.ab_self_inventory_branch_ids
        )[:1]
        if not cls.receiver:
            raise AssertionError('Replica tests require an existing receiver with an assigned branch.')

    def setUp(self):
        super().setUp()
        seed = self.env['ir.sequence'].sudo().next_by_code('ab_self_inventory_process') or '1'
        self.prefix = 'SIW%s' % str(seed).replace('/', '').replace(' ', '')
        self.branch = self.receiver.ab_self_inventory_branch_ids[:1]
        self.queries = []
        self.existing_product = self._create_product('OLD-%s' % self.prefix, 800001, default_cost=2.0)
        self.new_product = self._create_product('NEW-%s' % self.prefix, 800002, default_cost=3.0)
        self.process = self.env['ab_self_inventory_process'].sudo().create({
            'branch_id': self.branch.id,
            'state': 'in_progress',
            'line_ids': [(0, 0, {
                'product_id': self.existing_product.id,
                'eplus_item_id': self.existing_product.eplus_serial,
                'eplus_item_code': self.existing_product.code,
                'requested': True,
                'system_qty': 10.0,
                'count_snapshot_qty': 10.0,
                'count_snapshot_taken': True,
                'unit_cost': self.existing_product.default_cost,
            })],
        })

    def _create_product(self, code, eplus_serial, default_cost=1.0):
        card = self.env['ab_product_card'].sudo().create({'name': code})
        return self.env['ab_product'].sudo().create({
            'product_card_id': card.id,
            'code': code,
            'eplus_serial': eplus_serial,
            'default_cost': default_cost,
            'default_price': default_cost,
        })

    def _xlsx_file(self, rows, headers=None):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(headers or ['Product Code', 'Actual Qty'])
        for row in rows:
            sheet.append(row)
        buffer = io.BytesIO()
        workbook.save(buffer)
        return base64.b64encode(buffer.getvalue())

    def _import_file(self, rows, eplus_rows=None, headers=None):
        wizard = self.env['ab_self_inventory_import_wizard'].with_user(self.receiver).create({
            'process_id': self.process.id,
            'file': self._xlsx_file(rows, headers=headers),
            'filename': 'inventory.xlsx',
        })
        process_model = type(self.env['ab_self_inventory_process'])
        with patch.object(
            process_model,
            'connect_eplus',
            return_value=FakeEplusConnection(eplus_rows or [], self.queries),
        ):
            return wizard.action_import()

    def test_import_known_new_product_creates_required_counted_line(self):
        self._import_file(
            [[self.new_product.code, 4.0]],
            eplus_rows=[(self.new_product.eplus_serial, self.new_product.code, 7.0)],
        )

        new_line = self.process.line_ids.filtered(lambda line: line.product_id == self.new_product)
        self.assertEqual(len(new_line), 1)
        self.assertTrue(new_line.requested)
        self.assertTrue(new_line.is_counted)
        self.assertEqual(new_line.actual_qty, 4.0)
        self.assertEqual(new_line.system_qty, 7.0)
        self.assertEqual(new_line.count_snapshot_qty, 7.0)
        self.assertTrue(new_line.count_snapshot_taken)
        self.assertEqual(len(self.queries), 1)
        query, params = self.queries[0]
        self.assertIn('main.sto_id = ?', query)
        self.assertEqual(params[0], self.branch.eplus_serial)
        self.assertIn(self.new_product.eplus_serial, params[1:])
        self.assertNotIn(self.existing_product.eplus_serial, params[1:])

    def test_import_existing_and_new_products(self):
        self._import_file(
            [
                [self.existing_product.code, 11.0],
                [self.new_product.code, 5.0],
            ],
            eplus_rows=[(self.new_product.eplus_serial, self.new_product.code, 8.0)],
        )

        existing_line = self.process.line_ids.filtered(lambda line: line.product_id == self.existing_product)
        new_line = self.process.line_ids.filtered(lambda line: line.product_id == self.new_product)
        self.assertEqual(existing_line.actual_qty, 11.0)
        self.assertTrue(existing_line.is_counted)
        self.assertEqual(len(new_line), 1)
        self.assertEqual(new_line.actual_qty, 5.0)
        self.assertEqual(new_line.system_qty, 8.0)

    def test_new_product_can_match_by_eplus_item_id(self):
        self._import_file(
            [[self.new_product.eplus_serial, 6.0]],
            eplus_rows=[(self.new_product.eplus_serial, self.new_product.code, 9.0)],
            headers=['E-plus Item ID', 'Actual Qty'],
        )

        new_line = self.process.line_ids.filtered(lambda line: line.product_id == self.new_product)
        self.assertEqual(len(new_line), 1)
        self.assertEqual(new_line.system_qty, 9.0)
        self.assertEqual(new_line.actual_qty, 6.0)

    def test_unknown_product_code_rejects_import(self):
        with self.assertRaisesRegex(ValidationError, 'UNKNOWN-%s' % self.prefix):
            self._import_file([[self.existing_product.code, 11.0], ['UNKNOWN-%s' % self.prefix, 2.0]])

        existing_line = self.process.line_ids.filtered(lambda line: line.product_id == self.existing_product)
        self.assertFalse(existing_line.is_counted)
        self.assertFalse(self.process.line_ids.filtered(lambda line: line.product_id == self.new_product))

    def test_duplicate_product_code_rejects_import(self):
        with self.assertRaisesRegex(ValidationError, self.existing_product.code):
            self._import_file([[self.existing_product.code, 11.0], [self.existing_product.code, 12.0]])

        existing_line = self.process.line_ids.filtered(lambda line: line.product_id == self.existing_product)
        self.assertFalse(existing_line.is_counted)

    def test_new_product_without_actual_qty_blocks_submission(self):
        self._import_file([[self.existing_product.code, 10.0]])
        self._import_file(
            [[self.new_product.code, None]],
            eplus_rows=[(self.new_product.eplus_serial, self.new_product.code, 7.0)],
        )

        new_line = self.process.line_ids.filtered(lambda line: line.product_id == self.new_product)
        self.assertEqual(len(new_line), 1)
        self.assertTrue(new_line.requested)
        self.assertFalse(new_line.is_counted)
        with self.assertRaisesRegex(ValidationError, 'All requested products must be counted'):
            self.process.with_user(self.receiver).action_submit_process()

    def test_submission_allowed_after_all_required_products_counted(self):
        self._import_file(
            [
                [self.existing_product.code, 10.0],
                [self.new_product.code, 7.0],
            ],
            eplus_rows=[(self.new_product.eplus_serial, self.new_product.code, 7.0)],
        )

        self.process.with_user(self.receiver).action_submit_process()
        self.assertEqual(self.process.state, 'submitted')

    def test_existing_import_behavior_updates_current_lines(self):
        self._import_file([[self.existing_product.code, 12.0, 9.0]], headers=['Product Code', 'Actual Qty', 'Balance at Count'])

        existing_line = self.process.line_ids.filtered(lambda line: line.product_id == self.existing_product)
        self.assertEqual(len(self.process.line_ids), 1)
        self.assertEqual(existing_line.actual_qty, 12.0)
        self.assertEqual(existing_line.count_snapshot_qty, 9.0)
        self.assertTrue(existing_line.count_snapshot_taken)
        self.assertFalse(self.queries)

    def test_zero_actual_quantity_is_counted(self):
        self._import_file([[self.new_product.code, 0]])
        line = self.process.line_ids.filtered(lambda line: line.product_id == self.new_product)
        self.assertTrue(line.is_counted)
        self.assertEqual(line.actual_qty, 0)

    def test_duplicate_product_using_code_and_id_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, 'Duplicate product code'):
            self._import_file([[self.new_product.code, 1], [self.new_product.eplus_serial, 2]])
        self.assertEqual(len(self.process.line_ids), 1)

    def test_other_branch_import_is_rejected(self):
        other_branch = self.env['ab_store'].search([
            ('store_type', '=', 'branch'),
            ('id', 'not in', self.receiver.ab_self_inventory_branch_ids.ids),
        ], limit=1)
        self.assertTrue(other_branch)
        self.process.sudo().write({'branch_id': other_branch.id})
        with self.assertRaises(AccessError):
            self._import_file([[self.new_product.code, 1]])
        self.assertEqual(len(self.process.line_ids), 1)
        self.assertFalse(self.queries)

    def test_manual_add_line_remains_optional(self):
        wizard = self.env['ab_self_inventory_batch_add_line_wizard'].with_user(self.receiver).create({
            'process_id': self.process.id,
            'product_ids': [(6, 0, self.new_product.ids)],
        })
        wizard.action_add_lines()
        line = self.process.line_ids.filtered(lambda line: line.product_id == self.new_product)
        self.assertFalse(line.requested)
        self.assertFalse(line.is_counted)
        self.assertEqual(line.system_qty, 0)
