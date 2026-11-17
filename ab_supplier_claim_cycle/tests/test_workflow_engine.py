from datetime import timedelta
import base64

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestDynamicSupplierClaimWorkflow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.secretarial = new_test_user(
            cls.env, login='dynamic_claim_secretarial',
            groups='ab_supplier_claim_cycle.supplier_claim_group_user')
        cls.approver_a = new_test_user(
            cls.env, login='dynamic_claim_approver_a',
            groups='ab_supplier_claim_cycle.supplier_claim_group_participant')
        cls.approver_b = new_test_user(
            cls.env, login='dynamic_claim_approver_b',
            groups='ab_supplier_claim_cycle.supplier_claim_group_participant')
        cls.outsider = new_test_user(
            cls.env, login='dynamic_claim_outsider',
            groups='ab_supplier_claim_cycle.supplier_claim_group_participant')
        cls.admin = new_test_user(
            cls.env, login='dynamic_claim_admin',
            groups='ab_supplier_claim_cycle.supplier_claim_group_admin')
        cls.supplier = cls.env['ab_costcenter'].create({'name': 'Dynamic supplier', 'code': '1-DYN'})
        model_fields = cls.env['ir.model.fields'].search([
            ('model', '=', 'ab_supplier_claim_cycle'),
            ('name', 'in', ['claim_amount', 'attachment', 'secretarial_notes']),
        ])
        field_by_name = {field.name: field for field in model_fields}
        Workflow = cls.env['ab_supplier_claim_workflow'].with_user(cls.admin)
        cls.workflow = Workflow.create({
            'name': 'Cash workflow',
            'claim_domain': "[('payment_nature', '=', 'cash')]",
            'priority': 1,
            'workflow_stage_ids': [
                Command.create({
                    'name': 'Amount Review', 'sequence': 1,
                    'approver_ids': [Command.set(cls.approver_a.ids)],
                    'allowed_field_ids': [Command.set(
                        (field_by_name['claim_amount'] | field_by_name['attachment']).ids)],
                }),
                Command.create({
                    'name': 'Notes Review', 'sequence': 1,
                    'approver_ids': [Command.set(cls.approver_b.ids)],
                    'allowed_field_ids': [Command.set(field_by_name['secretarial_notes'].ids)],
                }),
                Command.create({
                    'name': 'Preparation', 'sequence': 2,
                    'approver_ids': [Command.set(cls.approver_a.ids)],
                }),
                Command.create({
                    'name': 'Close', 'sequence': 3,
                    'approver_ids': [Command.set(cls.approver_a.ids)],
                }),
            ],
        })
        cls.workflow.action_publish()

    def _claim_values(self, **values):
        return {
            'supplier_id': self.supplier.id,
            'num_of_invoice': 1,
            'area': 'north',
            'claim_amount': 100,
            'type_of_invoice': 'original',
            'payment_nature': 'cash',
            'tax_classification': 'non_tax_payment',
            'section': 'medical',
            'claim_month': '2026-11-01',
            'delivery_representative_phone': '01012345678',
            'delivery_representative_name': 'Supplier representative',
            'confirm_contact_info': True,
            **values,
        }

    def _claim(self):
        claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial).create(
            self._claim_values())
        claim.action_submit()
        return claim

    def test_draft_create_sanitizes_workflow_value(self):
        Claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial)
        automatic = Claim.create(self._claim_values(workflow_id=False))
        self.assertEqual(automatic.workflow_id, self.workflow)

        selected = Claim.create(self._claim_values(
            num_of_invoice=2, workflow_id=self.workflow.id))
        self.assertEqual(selected.workflow_id, self.workflow)

        with self.assertRaises(ValidationError):
            Claim.create(self._claim_values(
                num_of_invoice=3, payment_nature='bank_transfer',
                workflow_id=self.workflow.id))
        with self.assertRaises(AccessError):
            Claim.create(self._claim_values(num_of_invoice=4, state='closed'))

    def test_parallel_stages_allowed_fields_and_close(self):
        claim = self._claim()
        self.assertEqual(claim.state, 'in_progress')
        self.assertEqual(claim.current_sequence, 1)
        first = claim.stage_state_ids.filtered(lambda row: row.sequence == 1)
        self.assertEqual(set(first.mapped('status')), {'pending'})

        amount_stage = first.filtered(lambda row: row.name == 'Amount Review')
        notes_stage = first.filtered(lambda row: row.name == 'Notes Review')
        claim.with_user(self.approver_a).write({'claim_amount': 120})
        claim.with_user(self.approver_a).write({
            'attachment': base64.b64encode(b'stage evidence'),
            'attachment_filename': 'evidence.pdf',
        })
        snapshot = self.env['ab_supplier_claim_document'].search([
            ('claim_id', '=', claim.id), ('kind', '=', 'attachment'),
        ], order='id desc', limit=1)
        self.assertEqual(snapshot.filename, 'evidence.pdf')
        with self.assertRaises(AccessError):
            claim.with_user(self.approver_a).write({'secretarial_notes': 'not assigned'})
        amount_stage.with_user(self.approver_a).action_approve()
        with self.assertRaises(AccessError):
            claim.with_user(self.approver_a).write({'claim_amount': 130})

        claim.with_user(self.approver_b).write({'secretarial_notes': 'reviewed'})
        notes_stage.with_user(self.approver_b).action_approve()
        self.assertEqual(claim.current_sequence, 2)
        preparation = claim.stage_state_ids.filtered(lambda row: row.sequence == 2)
        preparation.with_user(self.approver_a).action_approve()
        self.assertEqual(claim.current_sequence, 3)
        close_stage = claim.stage_state_ids.filtered(lambda row: row.sequence == 3)
        close_stage.with_user(self.approver_a).action_approve()
        self.assertEqual(claim.state, 'closed')

    def test_reject_correct_and_resubmit(self):
        claim = self._claim()
        stage = claim.stage_state_ids.filtered(lambda row: row.name == 'Amount Review')
        stage.claim_id.with_user(self.approver_a)._action_stage_decision(
            stage.with_user(self.approver_a), 'rejected', reason='Correct the amount')
        self.assertEqual(claim.state, 'returned')
        self.assertEqual(stage.user_id, self.approver_a)
        self.assertTrue(stage.decision_at)
        claim.with_user(self.secretarial).write({'claim_amount': 150})
        claim.with_user(self.secretarial).action_resubmit()
        self.assertEqual((claim.state, stage.status), ('in_progress', 'pending'))
        self.assertFalse(stage.user_id)
        self.assertFalse(stage.decision_at)

    def test_defer_and_admin_remove_approval(self):
        claim = self._claim()
        stage = claim.stage_state_ids.filtered(lambda row: row.name == 'Amount Review')
        stage.claim_id.with_user(self.approver_a)._action_stage_decision(
            stage.with_user(self.approver_a), 'deferred', reason='Need evidence',
            followup_date=fields.Date.today() + timedelta(days=1))
        self.assertEqual(stage.status, 'deferred')
        stage.with_user(self.approver_a).action_approve()
        notes_stage = claim.stage_state_ids.filtered(lambda row: row.name == 'Notes Review')
        notes_stage.with_user(self.approver_b).action_approve()
        preparation = claim.stage_state_ids.filtered(lambda row: row.sequence == 2)
        preparation.with_user(self.approver_a).action_approve()
        self.assertEqual(claim.current_sequence, 3)
        claim.with_user(self.admin).action_admin_remove_approval(
            stage.with_user(self.admin), 'Review again')
        self.assertEqual((claim.state, claim.current_sequence, stage.status),
                         ('in_progress', 1, 'pending'))
        self.assertFalse(stage.user_id)
        self.assertFalse(stage.decision_at)
        self.assertEqual(preparation.status, 'waiting')
        self.assertEqual(
            claim.stage_state_ids.filtered(lambda row: row.sequence == 3).status,
            'waiting')

    def test_unassigned_participant_cannot_read_claim(self):
        claim = self._claim()
        with self.assertRaises(AccessError):
            claim.with_user(self.outsider).check_access('read')

    def test_participants_read_complete_assigned_workflow(self):
        Claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial)
        claim = Claim.create(self._claim_values())
        for observer in (self.approver_a, self.approver_b, self.outsider):
            with self.assertRaises(AccessError):
                claim.with_user(observer).check_access('read')

        claim.action_submit()
        claim.with_user(self.approver_a).write({
            'attachment': base64.b64encode(b'shared evidence'),
            'attachment_filename': 'shared-evidence.pdf',
        })
        stage_states = claim.stage_state_ids
        history = claim.history_ids
        documents = self.env['ab_supplier_claim_document'].search([
            ('claim_id', '=', claim.id),
        ])
        self.assertTrue(history)
        self.assertTrue(documents)

        for observer in (self.approver_a, self.approver_b):
            claim.with_user(observer).check_access('read')
            stage_states.with_user(observer).check_access('read')
            history.with_user(observer).check_access('read')
            documents.with_user(observer).check_access('read')
            self.assertEqual(
                self.env['ab_supplier_claim_stage_state'].with_user(observer).search_count([
                    ('claim_id', '=', claim.id),
                ]),
                len(stage_states),
            )
            claim.supplier_id.with_user(observer).check_access('read')
            other_stage = stage_states.filtered(
                lambda row: observer not in row.approver_ids)[:1]
            with self.assertRaises(AccessError):
                other_stage.with_user(observer).action_approve()
            with self.assertRaises(AccessError):
                claim.with_user(observer).write({'num_of_invoice': 999})

        for records in (claim, stage_states, history, documents):
            with self.assertRaises(AccessError):
                records.with_user(self.outsider).check_access('read')

    def test_only_four_generic_security_roles_exist(self):
        from ..tools.security_roles import CURRENT_ROLES, LEGACY_ROLES
        for role in CURRENT_ROLES:
            self.assertTrue(self.env.ref('ab_supplier_claim_cycle.' + role))
        for role in LEGACY_ROLES:
            self.assertFalse(self.env.ref(
                'ab_supplier_claim_cycle.' + role, raise_if_not_found=False))

    def test_reviewer_role_remains_read_only(self):
        claim = self._claim()
        reviewer_group = self.env.ref(
            'ab_supplier_claim_cycle.supplier_claim_group_reviewer')
        self.approver_a.group_ids = [Command.link(reviewer_group.id)]
        stage = claim.stage_state_ids.filtered(lambda row: row.name == 'Amount Review')
        with self.assertRaises(AccessError):
            stage.with_user(self.approver_a).action_approve()
        with self.assertRaises(AccessError):
            claim.with_user(self.approver_a).write({'claim_amount': 300})

    def test_published_workflow_allows_only_safe_stage_extensions(self):
        claim = self._claim()
        stage = self.workflow.workflow_stage_ids.filtered(
            lambda row: row.name == 'Amount Review')
        stage_state = claim.stage_state_ids.filtered(lambda row: row.stage_id == stage)
        self.assertIn('Amount Review', claim.current_stage_names)

        secretarial_notes = self.env['ir.model.fields'].search([
            ('model', '=', 'ab_supplier_claim_cycle'),
            ('name', '=', 'secretarial_notes'),
        ], limit=1)
        self.workflow.with_user(self.admin).write({
            'workflow_stage_ids': [Command.update(stage.id, {
                'name': 'Updated Amount Review',
                'approver_ids': [Command.link(self.outsider.id)],
                'allowed_field_ids': [Command.link(secretarial_notes.id)],
            })],
        })
        self.assertEqual(stage_state.name, 'Updated Amount Review')
        self.assertIn('Updated Amount Review', claim.current_stage_names)
        self.assertIn(self.outsider, stage_state.approver_ids)
        self.assertIn(secretarial_notes, stage_state.allowed_field_ids)
        claim.with_user(self.outsider).write({'secretarial_notes': 'Added after submission'})

        stage.with_user(self.admin).write({
            'approver_ids': [Command.unlink(self.approver_a.id)],
            'allowed_field_ids': [Command.unlink(secretarial_notes.id)],
        })
        self.assertNotIn(self.approver_a, stage.approver_ids)
        self.assertIn(self.approver_a, stage_state.historical_approver_ids)
        claim.with_user(self.approver_a).check_access('read')
        with self.assertRaises(AccessError):
            stage_state.with_user(self.approver_a).action_approve()
        with self.assertRaises(AccessError):
            claim.with_user(self.outsider).write({'secretarial_notes': 'revoked'})
        self.assertNotIn(secretarial_notes, stage.allowed_field_ids)

        with self.assertRaises(AccessError):
            self.workflow.with_user(self.admin).write({'priority': 5})
        with self.assertRaises(AccessError):
            self.workflow.with_user(self.admin).write({'claim_domain': '[]'})
        with self.assertRaises(AccessError):
            stage.with_user(self.admin).write({'sequence': 9})
        with self.assertRaises(AccessError):
            self.env['ab_supplier_claim_workflow_stage'].with_user(self.admin).create({
                'workflow_id': self.workflow.id,
                'name': 'Late stage',
                'sequence': 9,
            })
        with self.assertRaises(AccessError):
            stage.with_user(self.admin).unlink()

    def test_allowed_field_selector_uses_publication_rules(self):
        Stage = self.env['ab_supplier_claim_workflow_stage']
        selector_domain = Stage._fields['allowed_field_ids']._description_domain(self.env)
        self.assertEqual(selector_domain, Stage._allowed_field_domain())

        selectable = self.env['ir.model.fields'].search(selector_domain)
        selectable_names = set(selectable.mapped('name'))
        self.assertTrue({'claim_amount', 'attachment', 'secretarial_notes'} <= selectable_names)
        self.assertFalse(Stage._forbidden_allowed_fields() & selectable_names)

        computed_or_related = self.env['ir.model.fields'].search([
            ('model', '=', 'ab_supplier_claim_cycle'),
            '|', ('compute', '!=', False), ('related', '!=', False),
        ])
        self.assertFalse(selectable & computed_or_related)

        company_field = self.env['ir.model.fields'].search([
            ('model', '=', 'ab_supplier_claim_cycle'),
            ('name', '=', 'company_id'),
        ], limit=1)
        self.assertTrue(company_field)
        self.assertNotIn(company_field, selectable)
        stage = self.workflow.workflow_stage_ids[:1]
        with self.assertRaises(ValidationError):
            stage.with_user(self.admin).write({
                'allowed_field_ids': [Command.link(company_field.id)],
            })
        self.assertNotIn(company_field, stage.allowed_field_ids)

    def test_only_dynamic_workflow_controls_claim_lifecycle(self):
        Claim = self.env['ab_supplier_claim_cycle']
        state_values = dict(Claim._fields['state']._description_selection(self.env))
        self.assertEqual(
            set(state_values), {'draft', 'in_progress', 'returned', 'closed'})
        for method_name in (
                'action_decide', 'action_prepare_payment', 'action_close',
                'action_department_decision', 'action_open_document_replacement'):
            self.assertFalse(hasattr(Claim, method_name), method_name)
        self.assertNotIn('ab_supplier_claim_cycle_decision_wizard', self.env.registry)
        self.assertNotIn('ab_supplier_claim_document_replacement', self.env.registry)
        for field_name in (
                'inventory_decision', 'purchasing_decision',
                'supplier_accounts_decision', 'bank_accounts_decision'):
            self.assertIn(field_name, Claim._fields)

    def test_new_version_remains_structurally_editable(self):
        action = self.workflow.with_user(self.admin).action_new_version()
        draft = self.env['ab_supplier_claim_workflow'].browse(action['res_id'])
        self.assertEqual(draft.state, 'draft')
        draft.with_user(self.admin).write({
            'claim_domain': "[('payment_nature', '=', 'bank_transfer')]",
        })
        draft.workflow_stage_ids[:1].with_user(self.admin).write({'sequence': 10})
        added = self.env['ab_supplier_claim_workflow_stage'].with_user(self.admin).create({
            'workflow_id': draft.id,
            'name': 'Draft-only stage',
            'sequence': 20,
            'approver_ids': [Command.link(self.approver_a.id)],
        })
        added.unlink()
        self.assertFalse(added.exists())

    def test_priority_orders_matches_but_user_selects(self):
        other = self.env['ab_supplier_claim_workflow'].with_user(self.admin).create({
            'name': 'Fallback cash workflow',
            'claim_domain': "[('payment_nature', '=', 'cash')]",
            'priority': 20,
            'workflow_stage_ids': [Command.create({
                'name': 'Fallback Approval',
                'sequence': 1,
                'approver_ids': [Command.set(self.approver_a.ids)],
            })],
        })
        other.action_publish()
        claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial).create(
            self._claim_values(num_of_invoice=3, claim_amount=50))
        self.assertFalse(claim.workflow_id)
        self.assertEqual(claim.available_workflow_ids[:2].mapped('name'), [
            'Cash workflow', 'Fallback cash workflow'])
        with self.assertRaises(ValidationError):
            claim.action_submit()
        claim.write({'workflow_id': self.workflow.id})
        claim.action_submit()
        self.assertEqual(claim.workflow_id, self.workflow)


    def test_incomplete_draft_and_initial_submission_requirements(self):
        Claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial)
        draft = Claim.create({})
        self.assertEqual(draft.state, 'draft')
        self.assertFalse(draft.confirm_contact_info)
        with self.assertRaisesRegex(ValidationError, 'Supplier'):
            draft.action_submit()
        values = self._claim_values(confirm_contact_info=False)
        draft.write(values)
        with self.assertRaisesRegex(ValidationError, 'Confirm contact info'):
            draft.action_submit()
        draft.write({'confirm_contact_info': True})
        draft.action_submit()
        self.assertEqual(draft.state, 'in_progress')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            Claim.create(self._claim_values(claim_amount=-1))
        with self.assertRaises(ValidationError), self.cr.savepoint():
            Claim.create(self._claim_values(num_of_invoice=-1))

    def test_form_payload_excludes_unassigned_attachment_filenames(self):
        from odoo.tests import Form
        Claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial)
        form = Form(Claim)
        values = form._get_save_values()
        self.assertFalse(set(values) - Claim._entry_fields() - {'active', 'workflow_id'})
        draft = Claim.create(values)
        self.assertEqual(draft.state, 'draft')

    def test_contact_defaults_include_archived_claims_and_require_confirmation(self):
        Claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial)
        previous = Claim.create(self._claim_values())
        previous.with_user(self.admin).write({'active': False})
        draft = Claim.create({'supplier_id': self.supplier.id})
        self.assertEqual(draft.delivery_representative_phone, previous.delivery_representative_phone)
        self.assertEqual(draft.delivery_representative_name, previous.delivery_representative_name)
        self.assertEqual(draft.area, previous.area)
        self.assertFalse(draft.confirm_contact_info)
        self.assertFalse(draft.claim_month)
        draft.write({'confirm_contact_info': True})
        draft.write({'delivery_representative_phone': '01099999999'})
        self.assertFalse(draft.confirm_contact_info)
        draft.write({'delivery_representative_phone': '01088888888', 'confirm_contact_info': True})
        self.assertTrue(draft.confirm_contact_info)

    def test_unused_published_workflow_can_reset_but_used_cannot(self):
        draft = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial).create(self._claim_values())
        self.assertEqual(draft.workflow_id, self.workflow)
        self.workflow.with_user(self.admin).action_reset_to_draft()
        self.assertFalse(draft.workflow_id)
        self.workflow.with_user(self.admin).write({'claim_domain': '[]', 'priority': 42})
        self.workflow.workflow_stage_ids[:1].with_user(self.admin).write({'sequence': 5})
        self.workflow.with_user(self.admin).action_publish()
        self._claim()
        with self.assertRaises(UserError):
            self.workflow.with_user(self.admin).action_reset_to_draft()
        self.assertEqual(self.workflow.state, 'published')
        with self.assertRaises(AccessError):
            self.workflow.with_user(self.secretarial).action_reset_to_draft()

    def test_attachment_field_locks_and_chatter_accepts_additional_files(self):
        claim = self._claim()
        participant = claim.with_user(self.approver_a)
        content = base64.b64encode(b'first file').decode()
        participant.action_upload_documents('attachment', [{'name': 'first.txt', 'data': content}])
        for values in ({'attachment': False}, {'attachment_filename': 'renamed.txt'},
                       {'attachment': base64.b64encode(b'replacement')}):
            with self.assertRaises(AccessError):
                participant.write(values)
        with self.assertRaises(AccessError):
            participant.action_upload_documents('attachment', [{'name': 'second.txt', 'data': content}])
        with self.assertRaises(AccessError):
            claim.with_user(self.approver_b).action_upload_documents(
                'attachment', [{'name': 'unauthorized.txt', 'data': content}])
        # The other parallel participant has no attachment field permission.
        message = claim.with_user(self.approver_b).message_post(
            body='Additional evidence', attachments=[('additional.txt', b'additional')],
            message_type='comment', subtype_xmlid='mail.mt_note')
        attachment = message.attachment_ids.with_user(self.approver_b)
        self.assertTrue(attachment)
        with self.assertRaises(AccessError):
            attachment.write({'name': 'renamed.txt'})
        with self.assertRaises(AccessError):
            attachment.write({'datas': base64.b64encode(b'replacement')})
        with self.assertRaises(AccessError):
            attachment.unlink()
        with self.assertRaises(AccessError):
            attachment.sudo()._delete_and_notify()
        with self.assertRaises(AccessError):
            message.write({'attachment_ids': [Command.clear()]})
        with self.assertRaises(AccessError):
            message.unlink()
        with self.assertRaises(AccessError):
            claim.with_user(self.outsider).message_post(body='Not assigned')

    def test_removed_fields_revoke_returned_and_future_stage_edits(self):
        claim = self._claim()
        stage = self.workflow.workflow_stage_ids.filtered(lambda row: row.name == 'Amount Review')
        row = claim.stage_state_ids.filtered(lambda row: row.stage_id == stage)
        claim.with_user(self.approver_a)._action_stage_decision(
            row.with_user(self.approver_a), 'rejected', reason='Correct amount')
        stage.with_user(self.admin).write({'allowed_field_ids': [Command.clear()]})
        with self.assertRaises(AccessError):
            claim.with_user(self.secretarial).write({'claim_amount': 200})
        claim.with_user(self.secretarial).action_resubmit()
        with self.assertRaises(AccessError):
            claim.with_user(self.approver_a).write({'claim_amount': 200})

    def test_claim_month_and_combined_payment(self):
        draft = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial).create(
            self._claim_values(payment_nature='check_and_transfer'))
        self.assertEqual(str(draft.claim_month), '2026-11-01')
        self.assertEqual(draft.payment_nature, 'check_and_transfer')
        draft.write({'claim_month': '2026-11-17'})
        self.assertEqual(str(draft.claim_month), '2026-11-17')
        draft.write({'claim_month': '2028-02-29'})
        self.assertEqual(str(draft.claim_month), '2028-02-29')

    def test_historical_membership_does_not_bypass_company_scope(self):
        claim = self._claim()
        other_company = self.env['res.company'].create({'name': 'Other claim company'})
        records_to_check = (claim, claim.stage_state_ids, claim.history_ids)
        claim._workflow_write({'company_id': other_company.id})
        for records in records_to_check:
            with self.assertRaises(AccessError):
                records.with_user(self.approver_a).check_access('read')

    def test_tax_and_net_amounts_are_independent_draft_entries(self):
        Claim = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial)
        self.assertNotIn('tax_discount_rate', Claim._fields)
        for name in ('tax_discount_amount', 'net_claim_amount'):
            self.assertFalse(Claim._fields[name].compute)
            self.assertFalse(Claim._fields[name].readonly)
        draft = Claim.create(self._claim_values(tax_discount_amount=7.5, net_claim_amount=88))
        draft.write({'claim_amount': 250})
        self.assertEqual(draft.tax_discount_amount, 7.5)
        self.assertEqual(draft.net_claim_amount, 88)
        draft.write({'tax_discount_amount': 10, 'net_claim_amount': 239})
        self.assertEqual(draft.tax_discount_amount, 10)
        self.assertEqual(draft.net_claim_amount, 239)
        draft.action_submit()
        with self.assertRaises(AccessError):
            draft.with_user(self.approver_a).write({'net_claim_amount': 100})

    def test_amount_mismatch_warning_is_nonblocking_and_discount_conditional(self):
        draft = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial).create(
            self._claim_values(tax_discount_amount=0, net_claim_amount=1))
        self.assertFalse(draft.amounts_mismatch)
        draft.write({'tax_discount_amount': 10, 'net_claim_amount': 90})
        self.assertFalse(draft.amounts_mismatch)
        draft.write({'net_claim_amount': 89})
        self.assertTrue(draft.amounts_mismatch)
        draft.action_submit()
        self.assertTrue(draft.amounts_mismatch)
        row = draft.stage_state_ids.filtered(lambda stage: stage.name == 'Amount Review')
        row.with_user(self.approver_a).action_approve()
        self.assertTrue(draft.amounts_mismatch)

    def test_submission_errors_follow_form_labels_and_order(self):
        draft = self.env['ab_supplier_claim_cycle'].with_user(self.secretarial).create({})
        with self.assertRaises(ValidationError) as error:
            draft.action_submit()
        self.assertEqual(str(error.exception).splitlines()[1:], [
            'Supplier', 'Area', 'Name', 'Phone', 'Confirm contact info',
            'Num Of Invoice', 'Claim Amount', 'Claim Month', 'Type Of Invoice',
            'Section', 'Payment Nature', 'Tax Type',
        ])
