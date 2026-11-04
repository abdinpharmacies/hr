import base64
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

from ..models.ab_supplier_claim_cycle import DEPARTMENTS


@tagged('post_install', '-at_install')
class TestSupplierClaimCycle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.roles = ('user', 'inventory', 'purchasing', 'tax', 'supplier_accounts', 'bank_accounts', 'reviewer', 'admin')
        cls.users = {role: new_test_user(cls.env, login='scc_test_' + role,
            groups='ab_supplier_claim_cycle.supplier_claim_group_' + role) for role in cls.roles}
        cls.supplier = cls.env['ab_costcenter'].create({'name': 'Test supplier', 'code': '1-42'})
        cls.Claim = cls.env['ab_supplier_claim_cycle']
        cls.document = base64.b64encode(b'original evidence')
        cls.replacement = base64.b64encode(b'corrected evidence')

    def claim(self, payment='bank_transfer', tax='tax_payment', **values):
        return self.Claim.with_user(self.users['user']).create(dict(
            supplier_id=self.supplier.id, num_of_invoice=2, area='north', claim_amount=100,
            type_of_invoice='original', payment_nature=payment, tax_classification=tax, **values))

    def decide(self, claim, role, decision='approved', **values):
        return claim.with_user(self.users[role]).action_decide(role, decision, **values)

    def financial(self, claim):
        claim.action_submit()
        if claim.payment_nature != 'cash':
            self.decide(claim, 'purchasing')
            self.decide(claim, 'inventory')

    def prepare(self, claim):
        self.financial(claim)
        if claim.tax_decision != 'not_required':
            claim.with_user(self.users['tax']).write({'tax_review_attachment': self.document,
                'tax_review_filename': 'tax.pdf', 'tax_discount_decision': 'apply'})
            self.decide(claim, 'tax')
        if claim.payment_nature == 'check':
            claim.with_user(self.users['supplier_accounts']).write({
                'supplier_cheque_attachment': self.document, 'supplier_cheque_filename': 'supplier.pdf'})
        self.decide(claim, 'supplier_accounts')

    def bank(self, claim):
        self.prepare(claim)
        claim.write({'payment_request_attachment': self.document, 'payment_request_filename': 'request.pdf'})
        claim.action_prepare_payment()

    def test_new_secretarial_form_is_editable(self):
        from odoo.tests import Form
        for role in ('user', 'admin'):
            with Form(self.Claim.with_user(self.users[role])) as form:
                self.assertTrue(form.can_edit_open_claim_fields)
                self.assertTrue(form.can_edit_correction_fields)
                form.supplier_id = self.supplier
                form.num_of_invoice = 1
                form.claim_amount = 100
                form.area = 'north'
                form.type_of_invoice = 'original'
                form.payment_nature = 'cash'
                form.tax_classification = 'non_tax_payment'
                form.secretarial_notes = 'New claim note'
            self.assertEqual(form.record.state, 'draft')


    def test_secretary_open_claim_section_and_main_attachment(self):
        from odoo.tests import Form
        claim = self.claim()
        claim.action_submit()
        for stage in ('operational_review', 'financial_review', 'secretarial_preparation',
                      'bank_accounts', 'ready_to_close', 'returned_secretarial'):
            claim._workflow_write({'state': stage})
            for role in ('user', 'admin'):
                record = claim.with_user(self.users[role])
                with Form(record) as form:
                    form.section = 'cosmo'
                    form.attachment = self.replacement
                record.action_upload_documents('attachment', [{'name': 'main.pdf', 'data': self.document.decode()}])
                self.assertEqual(record.attachment, self.document)
                self.assertEqual(record.attachment_filename, 'main.pdf')
                self.assertEqual(record.section, 'cosmo')
            for field_name, value in (('section', 'medical'), ('attachment', self.replacement),
                                      ('attachment_filename', 'forbidden.pdf')):
                with self.assertRaises(AccessError):
                    claim.with_user(self.users['tax']).write({field_name: value})
        claim._workflow_write({'state': 'closed'})
        for role in ('user', 'admin'):
            with self.assertRaises(UserError):
                claim.with_user(self.users[role]).write({'section': 'other'})
            with self.assertRaises(UserError):
                claim.with_user(self.users[role]).action_upload_documents(
                    'attachment', [{'name': 'main.pdf', 'data': self.document.decode()}])

    def test_tax_type_before_and_after_both_approvals(self):
        from odoo.tests import Form
        for role in ('user', 'admin'):
            claim = self.claim(payment='cash')
            self.financial(claim)
            record = claim.with_user(self.users[role])
            with Form(record) as form:
                form.tax_classification = 'withholding_tax'
            with self.assertRaises(AccessError):
                claim.with_user(self.users['tax']).write({'tax_classification': 'through_supplier'})
            claim.with_user(self.users['tax']).write({'tax_discount_decision': 'apply'})
            self.decide(claim, 'tax')
            self.assertTrue(record.can_edit_tax_classification)
            record.write({'tax_classification': 'tax_payment'})
            self.assertEqual(record.tax_decision, 'approved')
            self.assertEqual(record.state, 'financial_review')
            self.decide(claim, 'supplier_accounts')
            self.assertFalse(record.can_edit_tax_classification)
            wizard = self.env['ab_supplier_claim_document_replacement'].with_user(self.users['admin'])
            with Form(wizard.with_context(default_claim_id=claim.id)) as replacement_form:
                self.assertFalse(replacement_form.can_edit_tax_classification)
                with self.assertRaises(AssertionError):
                    replacement_form.change_tax_type = True
                replacement_form.content = self.replacement
                replacement_form.filename = 'replacement.pdf'
                replacement_form.reason = 'Correction'
            with Form(record) as form:
                with self.assertRaises(AssertionError):
                    form.tax_classification = 'through_supplier'
                form.section = 'other'
                form.attachment = self.replacement
            for actor in self.roles:
                with self.assertRaises(UserError if actor in ('user', 'admin') else AccessError):
                    claim.with_user(self.users[actor]).write({'tax_classification': 'through_supplier'})
            with self.assertRaises(UserError):
                claim.sudo().write({'tax_classification': 'through_supplier'})
            with self.assertRaises(UserError), self.env.cr.savepoint():
                claim.with_user(self.users['admin']).action_replace_supplier_document(
                    self.replacement, 'replacement.pdf', 'Correction', tax_classification='through_supplier')
            self.assertEqual(claim.tax_classification, 'tax_payment')
            self.assertEqual(claim.tax_decision, 'approved')
            self.assertEqual(claim.supplier_accounts_decision, 'approved')
            claim.write({'payment_request_attachment': self.document, 'payment_request_filename': 'request.pdf'})
            claim.action_prepare_payment()
            claim.action_close()
            with self.assertRaises(UserError):
                record.write({'tax_classification': 'through_supplier'})

    def test_tax_type_lock_is_atomic_and_requires_both_approvals(self):
        unlocked = self.claim()
        locked = self.claim()
        self.prepare(locked)
        with self.assertRaises(UserError):
            (unlocked | locked).write({'tax_classification': 'through_supplier'})
        self.assertEqual(unlocked.tax_classification, 'tax_payment')
        unlocked._workflow_write({'state': 'financial_review', 'supplier_accounts_decision': 'approved'})
        self.assertTrue(unlocked.can_edit_tax_classification)
        unlocked.write({'tax_classification': 'non_tax_payment'})
        self.assertEqual(unlocked.tax_decision, 'not_required')
        self.assertEqual(unlocked.supplier_accounts_decision, 'approved')
        self.assertEqual(unlocked.state, 'financial_review')
        unlocked.with_user(self.users['admin']).write({'active': False})
        self.assertFalse(unlocked.can_edit_tax_classification)
        self.assertFalse(unlocked.can_edit_supplier_section)
        with self.assertRaises(UserError):
            unlocked.write({'section': 'other'})

    def test_tax_type_changes_preserve_workflow_and_documents(self):
        preserved_fields = ['state', 'resume_stage', 'review_round', 'document_revision',
                            'payment_request_revision', 'bank_approval_revision',
                            'secretarial_preparation_status', 'tax_discount_decision',
                            'tax_review_attachment', 'payment_request_attachment',
                            'supplier_cheque_attachment', 'bank_cheque_attachment']
        preserved_fields += [department + '_decision' for department in DEPARTMENTS]
        for role in ('user', 'admin'):
            for stage in ('draft', 'operational_review', 'financial_review',
                          'returned_secretarial', 'secretarial_preparation',
                          'bank_accounts', 'ready_to_close'):
                for tax_approved in (False, True):
                    with self.subTest(role=role, stage=stage, tax_approved=tax_approved):
                        claim = self.claim()
                        claim._workflow_write({
                            'state': stage, 'resume_stage': 'financial_review',
                            'inventory_decision': 'approved', 'purchasing_decision': 'approved',
                            'tax_decision': 'approved' if tax_approved else 'pending',
                            'supplier_accounts_decision': 'pending' if tax_approved else 'approved',
                            'bank_accounts_decision': 'approved', 'tax_discount_decision': 'apply',
                            'tax_review_attachment': self.document,
                            'payment_request_attachment': self.document,
                            'supplier_cheque_attachment': self.document,
                            'bank_cheque_attachment': self.document,
                        })
                        before = claim.read(preserved_fields)[0]
                        record = claim.with_user(self.users[role])
                        for classification in ('withholding_tax', 'non_tax_payment', 'tax_payment'):
                            record.write({'tax_classification': classification})
                            self.assertEqual(record.tax_classification, classification)
                            self.assertEqual(claim.read(preserved_fields)[0], before)

    def test_replacement_tax_type_does_not_reset_financial_reviews(self):
        claim = self.claim()
        self.financial(claim)
        claim.with_user(self.users['tax']).write({'tax_discount_decision': 'apply'})
        self.decide(claim, 'tax')
        decision_fields = [department + '_decision' for department in DEPARTMENTS]
        before = claim.read(['state'] + decision_fields)[0]
        claim.with_user(self.users['admin']).action_replace_supplier_document(
            self.replacement, 'replacement.pdf', 'Correction', tax_classification='withholding_tax')
        self.assertEqual(claim.tax_classification, 'withholding_tax')
        self.assertEqual(claim.read(['state'] + decision_fields)[0], before)

    def test_followup_dates_survive_saving_and_department_decisions(self):
        from odoo.tests import Form
        claim = self.claim()
        claim.action_submit()
        dates = {department: fields.Date.today() + timedelta(days=index + 1)
                 for index, department in enumerate(('inventory', 'purchasing', 'tax', 'supplier_accounts', 'bank_accounts'))}
        for department in dates:
            if department == 'tax':
                claim.with_user(self.users['tax']).write({
                    'tax_review_attachment': self.document, 'tax_discount_decision': 'apply'})
            if department == 'bank_accounts':
                claim.write({'payment_request_attachment': self.document, 'payment_request_filename': 'request.pdf'})
                claim.action_prepare_payment()
                claim.with_user(self.users['bank_accounts']).write({'bank_cheque_attachment': self.document})
            field_name = department + '_followup_date'
            with Form(claim.with_user(self.users[department])) as form:
                setattr(form, field_name, dates[department])
            claim.flush_recordset([field_name])
            claim.invalidate_recordset([field_name])
            self.assertEqual(claim[field_name], dates[department])
            self.decide(claim, department)
            claim.flush_recordset([field_name])
            claim.invalidate_recordset([field_name])
            self.assertEqual(claim[field_name], dates[department])
            self.assertEqual(claim.history_ids[0].followup_date, dates[department])
        claim.invalidate_recordset()
        for department, date in dates.items():
            self.assertEqual(claim[department + '_followup_date'], date)

    def test_rejection_retains_each_departments_followup_date(self):
        claim = self.claim()
        claim.action_submit()
        inventory_date = fields.Date.today() + timedelta(days=2)
        purchasing_date = fields.Date.today() + timedelta(days=4)
        claim.with_user(self.users['inventory']).write({'inventory_followup_date': inventory_date})
        self.decide(claim, 'purchasing', 'deferred', reason='Waiting', followup_date=purchasing_date)
        self.decide(claim, 'inventory', 'rejected', reason='Correction')
        claim.invalidate_recordset()
        self.assertEqual(claim.inventory_followup_date, inventory_date)
        self.assertEqual(claim.purchasing_followup_date, purchasing_date)
        claim.action_submit()
        self.assertEqual(claim.inventory_followup_date, inventory_date)
        self.assertEqual(claim.purchasing_followup_date, purchasing_date)

    def test_open_claim_input_changes_restart_applicable_reviews(self):
        replacement_supplier = self.env['ab_costcenter'].create({'name': 'Changed supplier', 'code': '1-changed'})
        for stage in ('draft', 'operational_review', 'financial_review', 'secretarial_preparation',
                      'bank_accounts', 'ready_to_close', 'returned_secretarial'):
            for field_name, new_value in (('supplier_id', replacement_supplier.id),
                                          ('payment_nature', 'cash'), ('type_of_invoice', 'copy')):
                with self.subTest(stage=stage, field=field_name):
                    claim = self.claim()
                    if stage in ('operational_review', 'returned_secretarial'):
                        claim.action_submit()
                        if stage == 'returned_secretarial':
                            self.decide(claim, 'inventory', 'rejected', reason='Correction')
                    elif stage == 'financial_review':
                        self.financial(claim)
                    elif stage == 'secretarial_preparation':
                        self.prepare(claim)
                    elif stage in ('bank_accounts', 'ready_to_close'):
                        self.bank(claim)
                        if stage == 'ready_to_close':
                            claim.with_user(self.users['bank_accounts']).write({'bank_cheque_attachment': self.document})
                            self.decide(claim, 'bank_accounts')
                    self.assertEqual(claim.state, stage)
                    previous_history = claim.history_ids.read(['event', 'reason', 'decision'])
                    previous_round, previous_revision = claim.review_round, claim.document_revision
                    self.assertTrue(claim.can_edit_open_claim_fields)
                    self.assertTrue(claim.can_edit_payment_nature)
                    claim.write({field_name: new_value})
                    claim.invalidate_recordset()
                    self.assertEqual(claim[field_name].id if field_name == 'supplier_id' else claim[field_name], new_value)
                    for entry in previous_history:
                        self.assertEqual(self.env['ab_supplier_claim_cycle.history'].browse(entry['id']).read(
                            ['event', 'reason', 'decision'])[0], entry)
                    if stage == 'draft':
                        self.assertEqual(claim.state, 'draft')
                        continue
                    cash = claim.payment_nature == 'cash'
                    self.assertEqual(claim.state, 'financial_review' if cash else 'operational_review')
                    self.assertEqual(claim.inventory_decision, 'not_required' if cash else 'pending')
                    self.assertEqual(claim.purchasing_decision, 'not_required' if cash else 'pending')
                    self.assertEqual(claim.tax_decision, 'pending')
                    self.assertEqual(claim.supplier_accounts_decision, 'pending')
                    self.assertEqual(claim.bank_accounts_decision, 'not_required' if cash else 'pending')
                    self.assertEqual(claim.review_round, previous_round + 1)
                    self.assertEqual(claim.document_revision, previous_revision + 1)
                    self.assertEqual(claim.history_ids[0].event, 'claim_updated')
                    self.assertFalse(claim.payment_request_attachment)
                    self.assertFalse(claim.tax_review_attachment)
                    self.assertFalse(claim.bank_cheque_attachment)
                    self.assertFalse(claim.bank_approval_revision)
                    self.assertFalse(claim.payment_request_revision)
                    self.assertFalse(claim.preparation_due_date)
                    if stage in ('secretarial_preparation', 'bank_accounts', 'ready_to_close'):
                        self.assertTrue(claim.document_ids.filtered(lambda document: document.kind == 'tax_review'))
                    if stage in ('bank_accounts', 'ready_to_close'):
                        self.assertTrue(claim.document_ids.filtered(lambda document: document.kind == 'payment_request'))

    def test_claim_input_edit_permissions_and_noop(self):
        claim = self.claim()
        self.bank(claim)
        for role in ('inventory', 'purchasing', 'tax', 'supplier_accounts', 'bank_accounts', 'reviewer'):
            for name, value in (('supplier_id', self.supplier.id), ('payment_nature', 'cash'), ('type_of_invoice', 'copy')):
                with self.subTest(role=role, field=name):
                    with self.assertRaises(AccessError):
                        claim.with_user(self.users[role]).write({name: value})
        previous = (claim.state, claim.review_round, claim.document_revision, claim.history_ids.ids)
        claim.write({'supplier_id': claim.supplier_id.id, 'payment_nature': claim.payment_nature,
                     'type_of_invoice': claim.type_of_invoice})
        self.assertEqual((claim.state, claim.review_round, claim.document_revision, claim.history_ids.ids), previous)
        claim.with_user(self.users['bank_accounts']).write({'bank_cheque_attachment': self.document})
        self.decide(claim, 'bank_accounts')
        claim.action_close()
        for role in ('user', 'admin'):
            record = claim.with_user(self.users[role])
            self.assertFalse(record.can_edit_open_claim_fields)
            self.assertFalse(record.can_edit_payment_nature)
            for name, value in (('supplier_id', self.supplier.id), ('payment_nature', 'cash'), ('type_of_invoice', 'copy')):
                with self.assertRaises(UserError):
                    record.write({name: value})

    def test_cash_to_cheque_requires_new_operational_reviews_and_evidence(self):
        claim = self.claim('cash')
        self.bank(claim)
        self.assertEqual(claim.state, 'ready_to_close')
        claim.write({'payment_nature': 'check'})
        self.assertEqual(claim.state, 'operational_review')
        self.decide(claim, 'inventory')
        self.decide(claim, 'purchasing')
        claim.with_user(self.users['tax']).write({'tax_review_attachment': self.replacement,
                                                'tax_discount_decision': 'do_not_apply'})
        self.decide(claim, 'tax')
        with self.assertRaises(ValidationError):
            self.decide(claim, 'supplier_accounts')
        claim.with_user(self.users['supplier_accounts']).write({'supplier_cheque_attachment': self.replacement})
        self.decide(claim, 'supplier_accounts')
        with self.assertRaises(ValidationError):
            claim.action_prepare_payment()
        with self.assertRaises(ValidationError):
            claim.write({'payment_request_attachment': self.document})

    def test_open_claim_form_fields_match_server_permissions(self):
        from odoo.tests import Form
        claim = self.claim()
        self.bank(claim)
        supplier = self.env['ab_costcenter'].create({'name': 'Form supplier', 'code': '1-form'})
        for name, value in (('supplier_id', supplier), ('type_of_invoice', 'copy'), ('payment_nature', 'cash')):
            with Form(claim) as form:
                setattr(form, name, value)
            claim.invalidate_recordset()
            self.assertEqual(claim[name], value)
        self.assertEqual(claim.state, 'financial_review')

    def test_batch_supplier_changes_do_not_copy_defaults_to_submitted_claims(self):
        other = self.env['ab_costcenter'].create({'name': 'Batch supplier', 'code': '1-batch'})
        self.Claim.with_user(self.users['user']).create({
            'supplier_id': other.id, 'num_of_invoice': 1, 'area': 'south', 'claim_amount': 100,
            'type_of_invoice': 'copy', 'payment_nature': 'cash', 'tax_classification': 'non_tax_payment'})
        draft = self.claim()
        submitted = self.claim()
        self.bank(submitted)
        (draft | submitted).write({'supplier_id': other.id})
        self.assertEqual((draft.payment_nature, draft.tax_classification, draft.area, draft.type_of_invoice),
                         ('cash', 'non_tax_payment', 'south', 'copy'))
        self.assertEqual((submitted.payment_nature, submitted.tax_classification,
                          submitted.area, submitted.type_of_invoice),
                         ('bank_transfer', 'tax_payment', 'north', 'original'))
        self.assertEqual(submitted.state, 'operational_review')
        self.assertEqual(submitted.tax_decision, 'pending')
        self.assertFalse(submitted.payment_request_attachment)


    def test_documents_tab_and_standard_chatter_layout(self):
        from lxml import etree
        arch = etree.fromstring(self.Claim.get_view(view_type='form')['arch'])
        self.assertEqual(len(arch.xpath('//chatter')), 1)
        self.assertFalse(arch.xpath('//group[@name="claim_document_audit"]'))
        self.assertFalse(arch.xpath('//page[@name="claim_notes" or @name="claim_history"]'))
        self.assertFalse(arch.xpath('//field[@name="note_history_ids" or @name="history_ids"]'))
        self.assertEqual(len(arch.xpath('//field[@name="document_ids"]')), 1)
        documents = arch.xpath('//page[@name="claim_documents"]/field[@name="document_ids"]')[0]
        self.assertEqual(documents.get('readonly'), 'True')
        self.assertEqual({node.get('name') for node in documents.xpath('./list/field')},
                         {'filename', 'user_id', 'occurred_at', 'content'})
        self.assertFalse(arch.xpath('//field[@name="company_id"]'))
        page = documents.getparent()
        self.assertFalse(page.get('invisible'))
        self.assertFalse(page.xpath('.//field[@name="attachment"]'))
        uploads = arch.xpath('//page[@name="claim_reviews"]//field[@name="attachment"]')
        self.assertTrue(arch.xpath('//page[@name="claim_reviews"]//field[@name="secretarial_notes"]'))
        self.assertTrue(uploads)
        self.assertEqual(len(uploads), len(arch.xpath('//field[@name="attachment"]')))
        self.assertTrue(all(node.get('widget') == 'supplier_claim_upload' for node in uploads))
        self.assertTrue(all(node.get('readonly') in (
            'True', 'not can_edit_open_claim_fields') for node in uploads))
        for name in ('document_revision', 'payment_request_revision', 'bank_approval_revision',
                     'migration_gate_exception', 'review_round'):
            self.assertFalse(arch.xpath('//sheet/field[@name="%s"] | //sheet/group/field[@name="%s"]' % (name, name)))
        self.assertIn('activity_ids', self.Claim._fields)
        for name in ('supplier_cheque_attachment', 'tax_review_attachment',
                     'payment_request_attachment', 'bank_cheque_attachment', 'attachment'):
            self.assertTrue(arch.xpath('//field[@name="%s" and @widget="supplier_claim_upload"]' % name))
        self.assertFalse(arch.xpath('//field[@name="can_upload_documents"]'))

    def test_review_view_is_filtered_by_server_role_and_active_stage(self):
        from lxml import etree
        departments = ('inventory', 'purchasing', 'tax', 'supplier_accounts', 'bank_accounts')
        for role in self.roles:
            model = self.Claim.with_user(self.users[role])
            arch = etree.fromstring(model.get_view(view_type='form')['arch'])
            self.assertFalse(arch.xpath('//page[@name="claim_preparation"]'))
            preparation = arch.xpath('//page[@name="claim_reviews"]//group[@name="claim_secretarial_review"]')
            self.assertEqual(len(preparation), int(role in ('user', 'admin')))
            if preparation:
                self.assertEqual(preparation[0].get('invisible'), 'not can_prepare_payment and not can_edit_open_claim_fields')
            for page in arch.xpath('//page[@name="claim_reviews"]'):
                self.assertEqual(page.get('invisible'), 'not can_edit_current_review and not can_prepare_payment and not can_edit_open_claim_fields')
            visible_roles = departments if role == 'admin' else (role,) if role in departments else ()
            groups = arch.xpath('//page[@name="claim_reviews"]//group[@name="department_reviews"]/group')
            self.assertEqual({node.get('name') for node in groups},
                             {department + '_review' for department in visible_roles})
            for node in groups:
                department = node.get('name').removesuffix('_review')
                self.assertEqual(node.get('invisible'), 'not can_edit_' + department)
        claim = self.claim()
        claim.action_submit()
        for role in self.roles:
            record = claim.with_user(self.users[role])
            for department in departments:
                expected = role in ('admin', department) and department in ('inventory', 'purchasing')
                self.assertEqual(record['can_edit_' + department], expected)
        self.decide(claim, 'inventory')
        self.assertFalse(claim.with_user(self.users['inventory']).can_edit_current_review)
        self.decide(claim, 'purchasing')
        for role in self.roles:
            record = claim.with_user(self.users[role])
            for department in departments:
                expected = role in ('admin', department) and department in ('tax', 'supplier_accounts')
                self.assertEqual(record['can_edit_' + department], expected)
        with self.assertRaises(AccessError):
            claim.with_user(self.users['reviewer']).write({'tax_notes': 'Unauthorized'})

    def test_workflow_history_is_mirrored_once_without_notifications(self):
        claim = self.claim(secretarial_notes='<script>old note</script>')
        history = claim.history_ids
        message = self.env['mail.message'].search([('supplier_claim_history_id', 'in', history.ids)])
        self.assertEqual(len(message), 1)
        self.assertEqual(message.author_id, self.users['user'].partner_id)
        self.assertEqual(message.date, history.occurred_at)
        self.assertTrue(message.is_internal)
        self.assertIn('&lt;script&gt;', message.body)
        self.assertNotIn('<script>', message.body)
        mail_count = self.env['mail.mail'].search_count([])
        notification_count = self.env['mail.notification'].search_count([])
        claim.action_submit()
        self.decide(claim, 'inventory', 'deferred', reason='Wait', followup_date=fields.Date.today())
        histories = claim.history_ids
        original = histories.read(['event', 'reason', 'followup_date', 'occurred_at', 'user_id'])
        histories._sync_claim_chatter()
        histories._sync_claim_chatter()
        messages = self.env['mail.message'].search([('supplier_claim_history_id', 'in', histories.ids)])
        self.assertEqual(len(messages), len(histories))
        self.assertEqual(histories.read(['event', 'reason', 'followup_date', 'occurred_at', 'user_id']), original)
        self.assertEqual(self.env['mail.mail'].search_count([]), mail_count)
        self.assertEqual(self.env['mail.notification'].search_count([]), notification_count)
        for values in ({'body': 'Changed'}, {'supplier_claim_history_id': histories[0].id}):
            with self.assertRaises(AccessError):
                message.write(values)
        with self.assertRaises(AccessError):
            message.unlink()
        with self.assertRaises(AccessError):
            self.env['mail.message'].create({'model': claim._name, 'res_id': claim.id,
                                           'supplier_claim_history_id': histories[0].id})

    def test_chatter_backfill_preserves_legacy_history_and_is_idempotent(self):
        claim = self.claim()
        claim._workflow_write({'secretarial_notes': 'Legacy note without an audit entry'})
        history_model = self.env['ab_supplier_claim_cycle.history']
        with patch.object(type(history_model), '_sync_claim_chatter', return_value=None):
            claim.action_submit()
            self.decide(claim, 'inventory', 'deferred', reason='Legacy waiting', followup_date=fields.Date.today())
        history = claim.history_ids
        original = history.read(['event', 'reason', 'followup_date', 'occurred_at', 'user_id'])
        self.assertFalse(self.env['mail.message'].search([('supplier_claim_history_id', 'in', history.ids)]))
        path = Path(__file__).parents[1] / 'migrations/19.0.5.1.0/post-migrate.py'
        spec = importlib.util.spec_from_file_location('claim_chatter_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, '19.0.5.0.0')
        module.migrate(self.env.cr, '19.0.5.0.0')
        self.assertEqual(history.read(['event', 'reason', 'followup_date', 'occurred_at', 'user_id']), original)
        messages = self.env['mail.message'].search([('supplier_claim_history_id', 'in', history.ids)])
        self.assertEqual(len(messages), len(history))
        for message in messages:
            self.assertEqual(message.author_id, message.supplier_claim_history_id.user_id.partner_id)
            self.assertEqual(message.date, message.supplier_claim_history_id.occurred_at)
        legacy_messages = self.env['mail.message'].search([
            ('model', '=', claim._name), ('res_id', '=', claim.id), ('subject', '=', 'Legacy Secretarial Note')])
        self.assertEqual(len(legacy_messages), 1)
        self.assertIn('Legacy note without an audit entry', legacy_messages.body)
        self.assertEqual(claim.secretarial_notes, 'Legacy note without an audit entry')

    def test_chatter_respects_existing_claim_permissions(self):
        claim = self.claim()
        claim.action_submit()
        message = claim.message_post(body='Internal discussion', subtype_xmlid='mail.mt_note')
        self.assertEqual(message.res_id, claim.id)
        with self.assertRaises(AccessError):
            claim.with_user(self.users['reviewer']).message_post(body='Not allowed', subtype_xmlid='mail.mt_note')
        activity = claim.activity_schedule('mail.mail_activity_data_todo', summary='Follow up', user_id=self.users['user'].id)
        self.assertEqual(activity.res_id, claim.id)
        with self.assertRaises(AccessError):
            claim.with_user(self.users['reviewer']).activity_schedule(
                'mail.mail_activity_data_todo', summary='Not allowed', user_id=self.users['reviewer'].id)


    def test_secretarial_and_admin_field_upload_and_workflow_logs(self):
        for role in ('user', 'admin'):
            actor = self.users[role]
            claim = self.Claim.with_user(actor).with_context(tracking_disable=True, mail_notrack=True).create({
                'supplier_id': self.supplier.id, 'num_of_invoice': 2, 'area': 'north', 'claim_amount': 100,
                'type_of_invoice': 'original', 'payment_nature': 'cash', 'tax_classification': 'non_tax_payment'})
            claim.write({'num_of_invoice': 3, 'area': 'south', 'claim_amount': 150})
            entry = claim.history_ids[0]
            self.assertEqual(entry.event, 'claim_updated')
            self.assertIn('100.0 → 150.0', entry.reason)
            self.assertIn('North → South', entry.reason)
            self.assertEqual(entry.user_id, actor)
            claim.action_submit()
            self.decide(claim, 'supplier_accounts')
            filename = role + '-request.pdf'
            claim.write({'payment_request_attachment': self.document, 'payment_request_filename': filename})
            document = claim.document_ids[0]
            message = self.env['mail.message'].search([('supplier_claim_document_id', '=', document.id)])
            self.assertEqual(len(message), 1)
            self.assertEqual(message.author_id, actor.partner_id)
            self.assertEqual(message.date, document.occurred_at)
            self.assertIn(filename, message.body)
            self.assertFalse(message.attachment_ids)
            activity = claim.activity_schedule(
                'mail.mail_activity_data_todo', summary='Role follow-up', user_id=actor.id)
            activity.action_feedback(feedback='Role follow-up completed')
            activity_message = self.env['mail.message'].search([
                ('model', '=', claim._name), ('res_id', '=', claim.id), ('body', 'ilike', 'Role follow-up completed')])
            self.assertEqual(len(activity_message), 1)
            self.assertEqual(activity_message.author_id, actor.partner_id)
            claim.action_prepare_payment()
            claim.action_close()
            expected_ids = self.env['mail.message'].search([
                ('model', '=', claim._name), ('res_id', '=', claim.id)]).ids
            for reader in self.roles:
                readable = self.env['mail.message'].with_user(self.users[reader]).search([
                    ('model', '=', claim._name), ('res_id', '=', claim.id)])
                self.assertEqual(set(readable.ids), set(expected_ids))
            count = len(claim.history_ids)
            with self.assertRaises(UserError):
                claim.write({'num_of_invoice': 9})
            self.assertEqual(len(claim.history_ids), count)

    def test_upload_chatter_covers_all_departments_and_preserves_document_history(self):
        claim = self.claim('check')
        self.bank(claim)
        claim.with_user(self.users['bank_accounts']).write({
            'bank_cheque_attachment': self.document, 'bank_cheque_filename': 'bank.pdf'})
        documents = claim.document_ids
        original = documents.read(['content', 'filename', 'revision', 'user_id', 'occurred_at'])
        documents._sync_claim_chatter()
        messages = self.env['mail.message'].search([('supplier_claim_document_id', 'in', documents.ids)])
        self.assertEqual(len(messages), len(documents))
        self.assertEqual(documents.read(['content', 'filename', 'revision', 'user_id', 'occurred_at']), original)
        self.assertEqual(set(messages.mapped('supplier_claim_document_id.kind')),
                         {'supplier_cheque', 'tax_review', 'payment_request', 'bank_cheque'})
        for message in messages:
            document = message.supplier_claim_document_id
            self.assertEqual(message.author_id, document.user_id.partner_id)
            self.assertEqual(message.date, document.occurred_at)
            self.assertTrue(message.is_internal)
            self.assertFalse(message.attachment_ids)
            with self.assertRaises(AccessError):
                message.write({'body': 'Changed'})
            with self.assertRaises(AccessError):
                message.unlink()
        with self.assertRaises(AccessError):
            self.env['mail.message'].create({'supplier_claim_document_id': documents[0].id})

    def test_upload_chatter_backfill_is_idempotent_and_does_not_notify(self):
        claim = self.claim()
        self.prepare(claim)
        model = self.env['ab_supplier_claim_document']
        with patch.object(type(model), '_sync_claim_chatter', return_value=None):
            claim.write({'payment_request_attachment': self.document, 'payment_request_filename': 'legacy.pdf'})
        document = claim.document_ids.filtered(lambda item: item.kind == 'payment_request')
        original = document.read(['content', 'filename', 'revision', 'user_id', 'occurred_at'])
        mail_count = self.env['mail.mail'].search_count([])
        notifications = self.env['mail.notification'].search_count([])
        path = Path(__file__).parents[1] / 'migrations/19.0.5.2.0/post-migrate.py'
        spec = importlib.util.spec_from_file_location('claim_upload_chatter_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, '19.0.5.1.0')
        module.migrate(self.env.cr, '19.0.5.1.0')
        messages = self.env['mail.message'].search([('supplier_claim_document_id', '=', document.id)])
        self.assertEqual(len(messages), 1)
        self.assertEqual(document.read(['content', 'filename', 'revision', 'user_id', 'occurred_at']), original)
        self.assertEqual(self.env['mail.mail'].search_count([]), mail_count)
        self.assertEqual(self.env['mail.notification'].search_count([]), notifications)

    def test_global_reads_and_draft_isolation(self):
        claim = self.claim()
        for role in self.roles:
            record = claim.with_user(self.users[role])
            if role in ('user', 'admin'):
                record.read(['claim_amount'])
            else:
                with self.assertRaises(AccessError):
                    record.read(['claim_amount'])
        claim.action_submit()
        for role in self.roles:
            self.assertEqual(claim.with_user(self.users[role]).read(['claim_amount'])[0]['claim_amount'], 100)

    def test_all_documents_history_closed_archived_reads(self):
        claim = self.claim('check')
        self.bank(claim)
        claim.with_user(self.users['bank_accounts']).write({'bank_cheque_attachment': self.document,
                                                           'bank_cheque_filename': 'bank.pdf'})
        self.decide(claim, 'bank_accounts')
        claim.action_close()
        claim.with_user(self.users['admin']).write({'active': False})
        for role in self.roles:
            record = claim.with_user(self.users[role])
            for kind in ('supplier_cheque', 'tax_review', 'payment_request', 'bank_cheque'):
                self.assertEqual(record[kind + '_attachment'], self.document)
            record.history_ids.read(['reason', 'tax_decision'])
            self.assertTrue(record.document_ids.read(['content']))

    def test_parallel_operational_orders_and_gate(self):
        for first, second in [('inventory', 'purchasing'), ('purchasing', 'inventory')]:
            claim = self.claim()
            claim.action_submit()
            self.decide(claim, first)
            self.assertEqual(claim.state, 'operational_review')
            with self.assertRaises(AccessError):
                self.decide(claim, 'supplier_accounts')
            self.decide(claim, second)
            self.assertEqual(claim.state, 'financial_review')

    def test_operational_rejection_preserves_approval(self):
        for approved in (True, False):
            claim = self.claim()
            claim.action_submit()
            if approved:
                self.decide(claim, 'inventory')
            self.decide(claim, 'purchasing', 'rejected', reason='Correction')
            self.assertEqual(claim.inventory_decision, 'approved' if approved else 'cancelled')
            claim.action_submit()
            self.assertEqual(claim.inventory_decision, 'approved' if approved else 'pending')
            self.assertEqual(claim.purchasing_decision, 'pending')

    def test_tax_requirements_and_financial_parallelism(self):
        for classification in ('through_supplier', 'tax_payment', 'withholding_tax', 'non_tax_payment'):
            claim = self.claim('cash', classification)
            self.financial(claim)
            required = classification != 'non_tax_payment'
            self.assertEqual(claim.tax_decision, 'pending' if required else 'not_required')
            if required:
                with self.assertRaises(ValidationError):
                    self.decide(claim, 'supplier_accounts')
                self.decide(claim, 'supplier_accounts', 'deferred', reason='Waiting', followup_date=fields.Date.today())
                with self.assertRaises(ValidationError):
                    self.decide(claim, 'tax')
                claim.with_user(self.users['tax']).write({'tax_discount_decision': 'do_not_apply'})
                with self.assertRaises(ValidationError):
                    self.decide(claim, 'tax')
                claim.with_user(self.users['tax']).write({'tax_review_attachment': self.document})
                self.decide(claim, 'tax')
            self.decide(claim, 'supplier_accounts')
            self.assertEqual(claim.state, 'secretarial_preparation')

    def test_financial_rejections_restart_reviews(self):
        for role in ('tax', 'supplier_accounts'):
            claim = self.claim('cash')
            self.financial(claim)
            self.decide(claim, role, 'rejected', reason='Correction')
            self.assertEqual(claim.state, 'returned_secretarial')
            claim.write({'claim_amount': 200})
            claim.action_submit()
            self.assertEqual((claim.tax_decision, claim.supplier_accounts_decision), ('pending', 'pending'))

    def test_deferral_reason_date_and_independence(self):
        claim = self.claim('cash')
        self.financial(claim)
        for kwargs in ({}, {'reason': 'Waiting'}, {'followup_date': fields.Date.today()}):
            with self.assertRaises(ValidationError):
                self.decide(claim, 'tax', 'deferred', **kwargs)
        self.decide(claim, 'tax', 'deferred', reason='Waiting', followup_date=fields.Date.today())
        self.decide(claim, 'supplier_accounts', 'rejected', reason='Different issue')
        self.assertEqual(claim.state, 'returned_secretarial')

    def test_amount_rounding_and_protection(self):
        claim = self.claim('cash')
        claim.write({'claim_amount': 100.50})
        self.financial(claim)
        claim.with_user(self.users['tax']).write({'tax_discount_decision': 'apply'})
        self.assertEqual((claim.tax_discount_amount, claim.net_claim_amount), (1.01, 99.49))
        claim.with_user(self.users['tax']).write({'tax_discount_decision': 'do_not_apply'})
        self.assertEqual((claim.tax_discount_amount, claim.net_claim_amount), (0, 100.50))
        for field in ('tax_discount_amount', 'tax_discount_rate', 'net_claim_amount'):
            with self.assertRaises(AccessError):
                claim.with_user(self.users['admin']).write({field: 99})
        for amount in (0, -1, float('inf'), float('nan')):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.claim().write({'claim_amount': amount})

    def test_cash_check_transfer_and_required_preparation(self):
        for payment in ('cash', 'check', 'bank_transfer'):
            claim = self.claim(payment)
            self.prepare(claim)
            with self.assertRaises(ValidationError):
                claim.action_prepare_payment()
            claim.write({'payment_request_attachment': self.document})
            claim.action_prepare_payment()
            if payment != 'cash':
                self.assertEqual(claim.state, 'bank_accounts')
                self.decide(claim, 'bank_accounts')
            self.assertEqual(claim.state, 'ready_to_close')
            claim.action_close()
            self.assertEqual(claim.state, 'closed')

    def test_check_requires_supplier_document(self):
        claim = self.claim('check', 'non_tax_payment')
        self.financial(claim)
        with self.assertRaises(ValidationError):
            self.decide(claim, 'supplier_accounts')

    def test_bank_gate_return_destinations(self):
        claim = self.claim('check')
        claim.action_submit()
        with self.assertRaises(AccessError):
            self.decide(claim, 'bank_accounts')
        claim = self.claim('check')
        self.bank(claim)
        with self.assertRaises(ValidationError):
            self.decide(claim, 'bank_accounts', 'rejected', reason='Correct request')
        self.decide(claim, 'bank_accounts', 'rejected', reason='Correct request', return_destination='secretarial')
        self.assertEqual(claim.secretarial_preparation_status, 'returned')
        self.assertFalse(claim.payment_request_attachment)
        self.assertEqual(claim.tax_review_attachment, self.document)
        with self.assertRaises(ValidationError):
            claim.action_prepare_payment()
        claim.write({'payment_request_attachment': self.replacement})
        claim.action_prepare_payment()
        self.decide(claim, 'bank_accounts', 'rejected', reason='Amount issue', return_destination='supplier_accounts', affects_tax=True)
        self.assertEqual((claim.state, claim.tax_decision, claim.supplier_accounts_decision), ('financial_review', 'pending', 'pending'))
        self.assertFalse(claim.payment_request_attachment)

    def test_bank_financial_return_preserves_unaffected_tax(self):
        claim = self.claim()
        self.bank(claim)
        self.decide(claim, 'bank_accounts', 'rejected', reason='Supplier document', return_destination='supplier_accounts')
        self.assertEqual(claim.tax_decision, 'approved')
        self.assertEqual(claim.secretarial_preparation_status, 'suspended')

    def test_document_replacement_revision_and_history(self):
        claim = self.claim('check')
        self.bank(claim)
        for role in self.roles:
            if role == 'admin':
                continue
            with self.assertRaises(AccessError):
                claim.with_user(self.users[role]).action_replace_supplier_document(self.replacement, 'new.pdf', 'Correction')
        manager = claim.with_user(self.users['admin'])
        with self.assertRaises(ValidationError):
            manager.action_replace_supplier_document(self.replacement, 'new.pdf', '')
        manager.action_replace_supplier_document(self.replacement, 'new.pdf', 'Correction')
        self.assertEqual((claim.document_revision, claim.state), (2, 'secretarial_preparation'))
        self.assertFalse(claim.payment_request_attachment)
        self.assertIn(self.document, claim.document_ids.mapped('content'))
        manager.action_replace_supplier_document(self.replacement, 'new.pdf', 'Amount correction', claim_amount=200)
        self.assertEqual((claim.state, claim.tax_decision, claim.supplier_accounts_decision), ('financial_review', 'pending', 'pending'))

    def test_direct_orm_and_combined_group_security(self):
        claim = self.claim()
        claim.action_submit()
        for role in self.roles:
            record = claim.with_user(self.users[role]).with_context(workflow_internal=True, skip_security=True)
            for field, value in [('state', 'closed'), ('tax_decision', 'approved'), ('claim_amount', 500), ('payment_request_attachment', self.document), ('migration_gate_exception', True)]:
                with self.assertRaises(AccessError):
                    record.write({field: value})
            with self.assertRaises(AccessError):
                record.unlink()
        combined = new_test_user(self.env, login='scc_combined', groups=','.join(
            'ab_supplier_claim_cycle.supplier_claim_group_' + r for r in ('inventory', 'purchasing')))
        with self.assertRaises(AccessError):
            claim.with_user(combined).action_decide('supplier_accounts', 'approved')
        reviewer = new_test_user(self.env, login='scc_reviewer_combined', groups=','.join(
            'ab_supplier_claim_cycle.supplier_claim_group_' + r for r in ('reviewer', 'inventory')))
        with self.assertRaises(AccessError):
            claim.with_user(reviewer).action_decide('inventory', 'approved')

    def test_forged_create_defaults_and_history(self):
        claim = self.Claim.with_user(self.users['user']).with_context(default_state='closed',
            default_migration_gate_exception=True, default_tax_decision='approved').create({
                'supplier_id': self.supplier.id, 'num_of_invoice': 1, 'area': 'north',
                'claim_amount': 100, 'type_of_invoice': 'original'})
        self.assertEqual(claim.state, 'draft')
        self.assertFalse(claim.migration_gate_exception)
        claim.write({'payment_nature': 'cash', 'tax_classification': 'non_tax_payment'})
        claim.action_submit()
        for role in self.roles:
            history = claim.with_user(self.users[role]).history_ids
            with self.assertRaises(AccessError):
                history.write({'reason': 'Forged'})
            with self.assertRaises(AccessError):
                history.unlink()

    def test_multiple_attachments_through_existing_stage_fields(self):
        files = [{'name': 'first.pdf', 'data': self.document.decode()},
                 {'name': 'second.pdf', 'data': self.replacement.decode()}]
        scenarios = [('draft', 'user', 'attachment'), ('returned_secretarial', 'user', 'attachment'),
                     ('financial_review', 'tax', 'tax_review'),
                     ('financial_review', 'supplier_accounts', 'supplier_cheque'),
                     ('secretarial_preparation', 'user', 'payment_request'),
                     ('bank_accounts', 'bank_accounts', 'bank_cheque')]
        for state, role, kind in scenarios:
            claim = self.claim()
            claim._workflow_write({'state': state, 'secretarial_preparation_status':
                'prepared' if state == 'bank_accounts' else 'pending',
                **{department + '_decision': 'pending' for department in DEPARTMENTS}})
            record = claim.with_user(self.users[role])
            field = 'attachment' if kind == 'attachment' else kind + '_attachment'
            self.assertTrue(record.action_upload_documents(field, files))
            documents = claim.document_ids
            self.assertEqual(len(documents), 2)
            self.assertEqual(set(documents.mapped('filename')), {'first.pdf', 'second.pdf'})
            self.assertEqual(documents.mapped('user_id'), self.users[role])
            self.assertEqual(set(documents.mapped('kind')), {kind})
            self.assertEqual(set(documents.mapped('revision')), {claim.document_revision})
            self.assertEqual(claim[field], self.replacement)
            self.assertEqual(claim.state, state)
            if kind == 'payment_request':
                self.assertEqual(claim.payment_request_revision, claim.document_revision)
            self.assertEqual(self.env['mail.message'].search_count([
                ('supplier_claim_document_id', 'in', documents.ids)]), 2)
            record.action_upload_documents(field, [{'name': 'third.pdf', 'data': self.document.decode()}])
            self.assertEqual(len(claim.document_ids), 3)
            with self.assertRaises(AccessError):
                documents.with_user(self.users[role]).write({'filename': 'changed.pdf'})
            if state == 'draft':
                record.write({'secretarial_notes': 'Draft supporting documents'})
                self.assertTrue(claim.history_ids.filtered(
                    lambda entry: entry.event == 'secretarial_note' and entry.reason == 'Draft supporting documents'))
                record.action_submit()
                self.assertEqual(len(claim.document_ids), 3)
                self.assertEqual(set(claim.document_ids.mapped('filename')),
                                 {'first.pdf', 'second.pdf', 'third.pdf'})
                with self.assertRaises(AccessError):
                    record.write({'secretarial_notes': 'Change after submission'})

    def test_multiple_attachment_access_and_atomic_validation(self):
        files = [{'name': 'first.pdf', 'data': self.document.decode()}]
        claim = self.claim(tax='non_tax_payment')
        self.financial(claim)
        for role in ('user', 'inventory', 'purchasing', 'tax', 'bank_accounts', 'reviewer'):
            with self.assertRaises(AccessError):
                claim.with_user(self.users[role]).action_upload_documents('supplier_cheque_attachment', files)
        supplier = claim.with_user(self.users['supplier_accounts'])
        with self.assertRaises(ValidationError):
            supplier.action_upload_documents('supplier_cheque_attachment', files + [{'name': 'bad.pdf', 'data': 'invalid!'}])
        self.assertFalse(claim.document_ids)
        self.assertFalse(claim.supplier_cheque_attachment)
        with self.assertRaises(AccessError):
            supplier.action_upload_documents('tax_review_attachment', files)
        with self.assertRaises(AccessError):
            supplier.action_upload_documents('state', files)
        self.decide(claim, 'supplier_accounts')
        with self.assertRaises(AccessError):
            supplier.action_upload_documents('supplier_cheque_attachment', files)
        for values in ({'state': 'closed'}, {'active': False}):
            claim._workflow_write(values)
            with self.assertRaises(UserError):
                claim.with_user(self.users['admin']).action_upload_documents('attachment', files)
        claim._workflow_write({'state': 'draft', 'active': True,
            'company_id': self.env['res.company'].create({'name': 'Upload isolated company'}).id})
        with self.assertRaises(AccessError):
            claim.action_upload_documents('attachment', files)

    def test_multiple_payment_files_preserve_required_and_invalidated_checks(self):
        import hashlib
        claim = self.claim(payment='cash', tax='non_tax_payment')
        self.prepare(claim)
        claim._workflow_write({'invalidated_payment_request_digest': hashlib.sha256(base64.b64decode(self.document)).hexdigest()})
        with self.assertRaises(ValidationError):
            claim.action_upload_documents('payment_request_attachment', [
                {'name': 'invalidated.pdf', 'data': self.document.decode()},
                {'name': 'corrected.pdf', 'data': self.replacement.decode()}])
        self.assertFalse(claim.payment_request_attachment)
        claim.action_upload_documents('payment_request_attachment', [
            {'name': 'corrected.pdf', 'data': self.replacement.decode()},
            {'name': 'annex.pdf', 'data': base64.b64encode(b'payment annex').decode()}])
        claim.action_prepare_payment()
        self.assertEqual(claim.state, 'ready_to_close')

    def test_company_and_branch_scope(self):
        company = self.env['res.company'].create({'name': 'Isolated branch'})
        claim = self.claim()
        claim._workflow_write({'company_id': company.id})
        for role in self.roles:
            with self.assertRaises(AccessError):
                claim.with_user(self.users[role]).read(['claim_amount'])
            with self.assertRaises(AccessError):
                claim.with_user(self.users[role]).action_submit()

    def test_calendar_sla_holiday_and_snapshot(self):
        calendar = self.env.company.resource_calendar_id
        self.env['resource.calendar.leaves'].create({'name': 'Test holiday', 'calendar_id': calendar.id,
            'date_from': datetime(2026, 11, 2, 0), 'date_to': datetime(2026, 11, 2, 23, 59, 59)})
        claim = self.claim('cash', 'non_tax_payment')
        self.financial(claim)
        with patch.object(fields.Datetime, 'now', return_value=datetime(2026, 10, 30, 10)):
            self.decide(claim, 'supplier_accounts')
        due = claim.preparation_due_date
        self.assertEqual(due.date().isoformat(), '2026-11-04')
        self.env.company.supplier_claim_secretarial_sla_days = 5
        self.assertEqual(claim.preparation_due_date, due)
        with patch.object(fields.Datetime, 'now', return_value=due + timedelta(days=1)):
            claim.invalidate_recordset(['preparation_overdue'])
            self.assertTrue(claim.preparation_overdue)

    def test_migration_amount_parser(self):
        path = Path(__file__).parents[1] / 'migrations/19.0.5.0.0/pre-migrate.py'
        spec = importlib.util.spec_from_file_location('claim_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for raw, expected in [(' 1,234.50 ', 1234.50), ('10', 10), ('100.505', 100.51), ('10000000000000000', 10000000000000000)]:
            self.assertEqual(float(module.parse_amount(raw)), expected)
        for raw in ('', 'abc', '1,2', '-5', '0', 'NaN', 'Infinity'):
            with self.assertRaises(ValueError):
                module.parse_amount(raw)

    def test_migration_invalid_input_is_atomic(self):
        path = Path(__file__).parents[1] / 'migrations/19.0.5.0.0/pre-migrate.py'
        spec = importlib.util.spec_from_file_location('claim_atomic_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.env.cr.savepoint():
            self.env.cr.execute('CREATE TEMP TABLE ab_supplier_claim_cycle (id integer, amount_of_check varchar, cheque_attachment bytea, cheque_filename varchar) ON COMMIT DROP')
            self.env.cr.execute("INSERT INTO ab_supplier_claim_cycle VALUES (1, '1,000.50', %s, 'one.pdf'), (2, 'invalid', NULL, NULL)", [b'evidence'])
            with self.assertRaisesRegex(ValueError, 'IDs \\[2\\]'):
                module.migrate(self.env.cr, '19.0.4.2.1')
            self.env.cr.execute('SELECT amount_of_check FROM ab_supplier_claim_cycle ORDER BY id')
            self.assertEqual(self.env.cr.fetchall(), [('1,000.50',), ('invalid',)])
            self.env.cr.execute("UPDATE ab_supplier_claim_cycle SET amount_of_check='2.50' WHERE id=2")
            module.migrate(self.env.cr, '19.0.4.2.1')
            self.env.cr.execute('SELECT claim_amount, supplier_cheque_attachment, supplier_cheque_filename FROM ab_supplier_claim_cycle WHERE id=1')
            amount, content, filename = self.env.cr.fetchone()
            self.assertEqual((amount, bytes(content), filename), (1000.50, b'evidence', 'one.pdf'))
            self.env.cr.execute('DROP TABLE pg_temp.ab_supplier_claim_cycle')

    def test_document_history_is_immutable(self):
        claim = self.claim('check')
        self.bank(claim)
        for role in self.roles:
            docs = claim.with_user(self.users[role]).document_ids
            with self.assertRaises(AccessError):
                docs.write({'content': self.replacement})
            with self.assertRaises(AccessError):
                docs.unlink()

    def test_bank_return_cannot_reuse_invalidated_request(self):
        claim = self.claim()
        self.bank(claim)
        self.decide(claim, 'bank_accounts', 'rejected', reason='Fix request', return_destination='secretarial')
        with self.assertRaises(ValidationError):
            claim.write({'payment_request_attachment': self.document})

    def test_english_arabic_views_and_queues(self):
        from lxml import etree
        self.env['res.lang']._activate_lang('ar_001')
        self.env['ir.module.module'].search([('name', '=', 'ab_supplier_claim_cycle')])._update_translations(filter_lang=['ar_001'])
        for language, expected in [('en_US', 'Complete Preparation'), ('ar_001', 'إتمام تجهيز طلب الدفع')]:
            for role in self.roles:
                model = self.Claim.with_user(self.users[role]).with_context(lang=language)
                arch = etree.fromstring(model.get_view(view_id=self.env.ref('ab_supplier_claim_cycle.invoice_view_form').id, view_type='form')['arch'])
                self.assertEqual(arch.xpath('//button[@name="action_prepare_payment"]')[0].get('string'), expected)
                self.assertEqual(bool(arch.xpath('//field[@name="tax_review_attachment"]')), role in ('tax', 'admin'))
                self.assertFalse(arch.xpath('//*[@attrs or @states]'))
        selection = self.Claim.with_context(lang='ar_001').fields_get(['tax_decision'])['tax_decision']['selection']
        self.assertEqual(dict(selection)['approved'], 'تمت الموافقة')
        all_claims = self.env.ref('ab_supplier_claim_cycle.invoice_action')
        self.assertEqual(all_claims.domain, "[]")

    def test_supplier_defaults_and_reference_normalization(self):
        first = self.claim('cash', 'non_tax_payment', claim_reference='  test-42  ')
        self.assertEqual(first.claim_reference, 'TEST-42')
        other = self.env['ab_costcenter'].create({'name': 'Other supplier', 'code': '1-other'})
        draft = self.Claim.with_user(self.users['user']).create({
            'supplier_id': other.id, 'num_of_invoice': 1, 'area': 'north', 'claim_amount': 200,
            'type_of_invoice': 'copy'})
        draft.write({'supplier_id': self.supplier.id})
        self.assertEqual((draft.payment_nature, draft.tax_classification), ('cash', 'non_tax_payment'))
        self.assertEqual(draft.claim_amount, 200)

    def test_zero_amount_create_and_manager_stage_guards(self):
        with self.assertRaises(ValidationError):
            self.Claim.with_user(self.users['user']).create({'supplier_id': self.supplier.id,
                'num_of_invoice': 1, 'area': 'north', 'type_of_invoice': 'original'})
        claim = self.claim()
        claim.action_submit()
        with self.assertRaises(UserError):
            claim.with_user(self.users['admin']).action_decide('bank_accounts', 'approved')
        with self.assertRaises(UserError):
            claim.with_user(self.users['admin']).action_replace_supplier_document(self.document, 'supplier.pdf', 'Correction')

    def test_multiple_company_migration_requires_mapping(self):
        path = Path(__file__).parents[1] / 'migrations/19.0.5.0.0/pre-migrate.py'
        spec = importlib.util.spec_from_file_location('claim_company_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.env['res.company'].create({'name': 'Another branch'})
        with self.env.cr.savepoint():
            self.env.cr.execute('CREATE TEMP TABLE ab_supplier_claim_cycle (id integer, amount_of_check varchar, cheque_attachment bytea, cheque_filename varchar) ON COMMIT DROP')
            self.env.cr.execute("INSERT INTO ab_supplier_claim_cycle VALUES (123, '100', NULL, NULL)")
            with self.assertRaisesRegex(ValueError, 'explicit company XML ID'):
                module.migrate(self.env.cr, '19.0.4.2.1')
            self.env['ir.config_parameter'].set_param('ab_supplier_claim_cycle.migration_company_map', '{"123": "base.main_company"}')
            module.migrate(self.env.cr, '19.0.4.2.1')
            self.env.cr.execute('SELECT company_id FROM ab_supplier_claim_cycle')
            self.assertEqual(self.env.cr.fetchone()[0], self.env.ref('base.main_company').id)
            self.env.cr.execute('DROP TABLE pg_temp.ab_supplier_claim_cycle')

    def test_secretarial_form_creates_and_submits(self):
        from odoo.tests import Form
        with Form(self.Claim.with_user(self.users['user'])) as form:
            form.supplier_id = self.supplier
            form.num_of_invoice = 1
            form.area = 'north'
            form.claim_amount = 100
            form.type_of_invoice = 'original'
            form.payment_nature = 'cash'
            form.tax_classification = 'non_tax_payment'
        claim = form.record
        claim.action_submit()
        self.assertEqual(claim.state, 'financial_review')

    def test_migrated_bank_return_can_resume(self):
        path = Path(__file__).parents[1] / 'migrations/19.0.5.0.0/post-migrate.py'
        spec = importlib.util.spec_from_file_location('claim_return_migration', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        claim = self.claim()
        claim._workflow_write({'state': 'returned_secretarial', 'resume_stage': 'bank_accounts',
            'supplier_accounts_decision': 'approved', 'inventory_decision': 'approved',
            'purchasing_decision': 'approved'})
        self.env.flush_all()
        self.env.cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS cheque_attachment bytea')
        self.env.cr.execute('ALTER TABLE ab_supplier_claim_cycle ADD COLUMN IF NOT EXISTS cheque_filename varchar')
        module.migrate(self.env.cr, '19.0.4.2.1')
        claim.invalidate_recordset()
        self.assertEqual((claim.state, claim.resume_stage), ('returned_secretarial', 'financial_review'))
        self.assertFalse(claim.migration_gate_exception)
        claim.action_submit()
        self.assertEqual((claim.state, claim.tax_decision, claim.supplier_accounts_decision),
                         ('financial_review', 'pending', 'pending'))

    def test_views_load_in_xml_developer_mode(self):
        from lxml import etree
        from odoo.addons.base.models.ir_ui_view import get_view_arch_from_file
        root = Path(__file__).parents[1]
        for path in root.rglob('*.xml'):
            tree = etree.parse(str(path))
            for record in tree.xpath('//record[@model="ir.ui.view"]'):
                if record.find('field[@name="arch"]') is not None:
                    xmlid = 'ab_supplier_claim_cycle.' + record.get('id')
                    with self.subTest(view=xmlid):
                        self.assertTrue(get_view_arch_from_file(str(path), xmlid))

    def test_parallel_workflow_preserves_original_design(self):
        from lxml import etree
        view = self.env.ref('ab_supplier_claim_cycle.invoice_view_form')
        arch = etree.fromstring(self.Claim.get_view(view_id=view.id, view_type='form')['arch'])
        self.assertIn('o_scc_form', arch.get('class', ''))
        for name, style in [('supplier_classification', 'o_scc_classification'),
                            ('claim_details', 'o_scc_details'), ('department_reviews', 'o_scc_reviews')]:
            group = arch.xpath('//group[@name="%s"]' % name)[0]
            self.assertIn(style, group.get('class', ''))
        for name in ('operational_parallel_timeline', 'financial_parallel_timeline'):
            self.assertTrue(arch.xpath('//div[@name="%s"]' % name))
        self.assertTrue(arch.xpath('//page[@name="claim_exceptions"]/field[@name="exception_history_ids"]'))
        self.assertFalse(arch.xpath('//field[@name="note_history_ids"]'))
        self.assertFalse(arch.xpath('//page[@name="claim_history"]'))
        self.assertTrue(arch.xpath('//chatter'))
        self.assertTrue(arch.xpath('//group[@name="payment_preparation"]'))
        listing = etree.fromstring(self.Claim.get_view(view_id=self.env.ref(
            'ab_supplier_claim_cycle.invoice_view_tree').id, view_type='list')['arch'])
        state = listing.xpath('//field[@name="state"]')[0]
        self.assertEqual(state.get('decoration-info'), "state == 'operational_review'")
        self.assertEqual(state.get('decoration-primary'), "state == 'financial_review'")
