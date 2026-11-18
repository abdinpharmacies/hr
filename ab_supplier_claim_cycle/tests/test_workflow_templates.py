from itertools import product

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import convert_file


MODULE = 'ab_supplier_claim_cycle'


@tagged('post_install', '-at_install')
class TestSupplierClaimWorkflowTemplates(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.templates = cls.env['ab_supplier_claim_workflow'].browse()
        for section, tax, payment in product(
                ('medical', 'cosmo'), ('tax', 'non_tax'),
                ('bank_transfer', 'cheque_north', 'cheque_south')):
            cls.templates |= cls.env.ref(f'{MODULE}.workflow_{section}_{tax}_{payment}')
        cls.participant = new_test_user(
            cls.env, login='template_participant',
            groups=f'{MODULE}.supplier_claim_group_participant')
        cls.secretarial = new_test_user(
            cls.env, login='template_secretarial',
            groups=f'{MODULE}.supplier_claim_group_user')

    def _configure(self, workflows):
        workflows.workflow_stage_ids.write({
            'approver_ids': [Command.set(self.participant.ids)],
        })
        workflows.action_publish()

    def test_draft_templates_and_order(self):
        self.assertEqual(len(self.templates), 12)
        self.assertEqual(len(self.templates.workflow_stage_ids), 84)
        self.assertEqual(set(self.templates.mapped('state')), {'draft'})
        self.assertTrue(all(self.templates.mapped('active')))
        self.assertFalse(self.templates.workflow_stage_ids.approver_ids)
        self.assertFalse(self.templates.workflow_stage_ids.allowed_field_ids)
        for number, workflow in enumerate(self.templates, 1):
            with self.subTest(route=number):
                self.assertTrue(workflow.name.startswith(f'{number:02d} - '))
                names = ['Inventory', 'Purchasing (Medicine)' if number <= 6
                         else 'Purchasing (Cosmetics)', 'Supplier Accounts']
                if number in (1, 2, 3, 7, 8, 9):
                    names += ['Tax Accounts', 'Supplier Accounts After Tax']
                names += ['Bank Accounts']
                if number % 3 != 1:
                    names += ['Cheque Treasury']
                if number % 3 == 0:
                    names += ['Upper Egypt Supplier Accounts']
                names += ['Secretarial Closure']
                stages = workflow.workflow_stage_ids.sorted('sequence')
                self.assertEqual(stages.mapped('name'), names)
                self.assertEqual(stages.mapped('sequence'), list(range(10, len(names) * 10 + 1, 10)))
                with self.assertRaises(ValidationError), self.cr.savepoint():
                    workflow.action_publish()
        claim = self.env['ab_supplier_claim_cycle'].create({
            'section': 'medical', 'tax_classification': 'tax_payment',
            'payment_nature': 'bank_transfer', 'area': 'north',
        })
        self.assertFalse(claim.available_workflow_ids & self.templates)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            claim.write({'workflow_id': self.templates[0].id})

    def test_domain_matrix(self):
        self._configure(self.templates)
        Claim = self.env['ab_supplier_claim_cycle']
        for section, tax, payment, area in product(
                ('medical', 'cosmo', 'other'),
                ('tax_payment', 'non_tax_payment', 'through_supplier'),
                ('bank_transfer', 'check', 'cash', 'check_and_transfer'),
                ('north', 'south')):
            with self.subTest(section=section, tax=tax, payment=payment, area=area):
                claim = Claim.create({
                    'section': section, 'tax_classification': tax,
                    'payment_nature': payment, 'area': area,
                })
                matches = claim.available_workflow_ids & self.templates
                if section == 'other' or tax == 'through_supplier' or payment in ('cash', 'check_and_transfer'):
                    self.assertFalse(matches)
                else:
                    suffix = 'bank_transfer' if payment == 'bank_transfer' else f'cheque_{area}'
                    tax_key = 'tax' if tax == 'tax_payment' else 'non_tax'
                    self.assertEqual(matches, self.env.ref(
                        f'{MODULE}.workflow_{section}_{tax_key}_{suffix}'))
                    self.assertEqual(claim.workflow_id, matches)

    def test_sequential_progress_and_access(self):
        supplier = self.env['ab_costcenter'].create({'name': 'Template supplier', 'code': '1-TEMPLATE'})
        for workflow in (self.templates[0], self.templates[5]):
            with self.subTest(workflow=workflow.name):
                self._configure(workflow)
                values = {leaf[0]: leaf[2] for leaf in workflow._parse_domain(workflow.claim_domain)}
                claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial).create({
                    **values, 'area': values.get('area', 'north'),
                    'supplier_id': supplier.id, 'num_of_invoice': 1,
                    'claim_amount': 100, 'claim_month': '2026-11-01',
                    'type_of_invoice': 'original', 'confirm_contact_info': True,
                    'delivery_representative_name': 'Representative',
                    'delivery_representative_phone': '01012345678',
                })
                claim.action_submit()
                for row in claim.stage_state_ids.sorted('sequence'):
                    self.assertEqual(claim.stage_state_ids.filtered(
                        lambda stage: stage.status == 'pending'), row)
                    row.with_user(self.participant).action_approve()
                self.assertEqual(claim.state, 'closed')
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.templates[1].with_user(self.secretarial).write({'priority': 100})

    def test_upgrade_preserves_configuration(self):
        workflow = self.templates[0]
        workflow.write({'name': 'Administrator route name', 'priority': 17})
        stage = workflow.workflow_stage_ids.sorted('sequence')[0]
        stage.write({'name': 'Administrator stage name'})
        self._configure(workflow)
        original_ids = self.templates.ids
        original_stage_ids = self.templates.workflow_stage_ids.ids
        convert_file(self.env, MODULE, 'data/supplier_claim_workflows.xml', {}, mode='update')
        self.assertEqual(workflow.state, 'published')
        self.assertEqual(workflow.name, 'Administrator route name')
        self.assertEqual(workflow.priority, 17)
        self.assertEqual(stage.name, 'Administrator stage name')
        self.assertEqual(stage.approver_ids, self.participant)
        data = self.env['ir.model.data'].search([
            ('module', '=', MODULE), ('model', 'in',
             ['ab_supplier_claim_workflow', 'ab_supplier_claim_workflow_stage']),
        ])
        self.assertTrue(all(data.mapped('noupdate')))
        self.assertEqual(sorted(data.filtered(
            lambda row: row.model == 'ab_supplier_claim_workflow').mapped('res_id')), sorted(original_ids))
        self.assertEqual(sorted(data.filtered(
            lambda row: row.model == 'ab_supplier_claim_workflow_stage').mapped('res_id')), sorted(original_stage_ids))

    def test_arabic_record_translations(self):
        self.assertTrue(self.env['res.lang']._activate_lang('ar_001'))
        self.env['ir.module.module']._load_module_terms([MODULE], ['ar_001'], overwrite=True)
        workflow = self.templates[0]
        self.assertEqual(workflow.with_context(lang='ar_001').name,
                         '01 - مشتريات الدواء - ضريبي - تحويل بنكي')
        expected = ['المخزون', 'المشتريات (دواء)', 'حسابات الموردين', 'حسابات الضرائب',
                    'حسابات الموردين بعد الضرائب', 'حسابات البنوك', 'تقفيل السكرتارية']
        self.assertEqual(workflow.with_context(lang='ar_001').workflow_stage_ids.sorted(
            'sequence').mapped('name'), expected)
        self.assertEqual(workflow.with_context(lang='en_US').name,
                         '01 - Medicine - Tax - Bank Transfer')
