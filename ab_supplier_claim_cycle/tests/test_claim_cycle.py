import base64
from datetime import timedelta
from lxml import etree
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestSupplierClaimCycle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('ar_001')
        cls.env['ir.module.module'].search(
            fields.Domain('name', '=', 'ab_supplier_claim_cycle')
        )._update_translations(filter_lang=['ar_001'])
        cls.roles = ('user', 'inventory', 'purchasing', 'supplier_accounts', 'bank_accounts', 'reviewer', 'admin')
        cls.users = {role: new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True)), login='scc_test_'+role,
                     groups='ab_supplier_claim_cycle.supplier_claim_group_'+role) for role in cls.roles}
        cls.outsider = new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True)), login='scc_test_outsider', groups='base.group_user')
        cls.system = new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True)), login='scc_test_system', groups='base.group_system')
        cls.supplier = cls.env['ab_costcenter'].create({
            'name': 'Cycle Supplier Alpha', 'code': '1-42',
        })
        cls.cash = cls.env['ab_costcenter'].create({
            'name': 'Cash Supplier', 'code': '1-43',
        })
        cls.non_supplier_center = cls.env['ab_costcenter'].create({
            'name': 'Internal Cost Center', 'code': '2-10',
        })
        cls.Claim = cls.env['ab_supplier_claim_cycle']

    def claim(self, cash=False):
        return self.Claim.with_user(self.users['user']).create(self.values(cash))

    def values(self, cash=False):
        return dict(supplier_id=(self.cash if cash else self.supplier).id, num_of_invoice=2,
                    area='north', amount_of_check='100', type_of_invoice='original',
                    payment_nature='cash' if cash else 'bank_transfer',
                    tax_classification='tax_payment', section='medical')

    def decide(self, claim, department, decision='approved', **vals):
        record=claim.with_user(self.users[department])
        if vals: record.write(vals)
        return record.action_decide(department, decision)

    def accounts(self, claim):
        claim.action_submit()
        self.decide(claim,'inventory')
        self.decide(claim,'purchasing')

    def bank(self, claim):
        self.accounts(claim)
        self.decide(claim,'supplier_accounts',cheque_attachment=base64.b64encode(b'cheque'),cheque_filename='cheque.pdf')

    def test_timeline_details_follow_each_stage(self):
        claim = self.claim().with_context(lang='en_US', tz='UTC')
        self.assertFalse(claim.timeline_inventory)
        self.bank(claim)
        self.assertIn(self.users['inventory'].display_name, claim.timeline_inventory)
        self.assertTrue(claim.timeline_inventory_date)
        self.assertNotIn('→', claim.timeline_inventory)
        self.assertTrue(claim.timeline_supplier_accounts_date)
        self.assertNotIn('→', claim.timeline_supplier_accounts)
        self.assertFalse(claim.timeline_closure)
        self.decide(claim, 'bank_accounts')
        self.assertTrue(claim.timeline_bank_accounts_date)
        self.assertNotIn('→', claim.timeline_bank_accounts)
        claim.action_close()
        self.assertTrue(claim.timeline_closure_date)
        self.assertNotIn('→', claim.timeline_closure)
        self.assertIn(self.users['user'].display_name, claim.timeline_closure)
        self.assertIn(self.users['bank_accounts'].display_name, claim.timeline_bank_accounts)
        with self.assertRaises(AccessError):
            claim.with_user(self.outsider).read(['timeline_inventory'])

    def test_review_panel_visibility_and_note_attachments(self):
        claim = self.claim()
        self.assertFalse(claim.can_edit_current_review)
        claim.action_submit()
        self.assertFalse(claim.can_edit_current_review)
        self.assertTrue(claim.with_user(self.users['inventory']).can_edit_current_review)
        self.assertTrue(claim.with_user(self.users['admin']).can_edit_current_review)
        self.decide(claim, 'inventory')
        self.assertFalse(claim.with_user(self.users['inventory']).can_edit_current_review)
        self.decide(claim, 'purchasing')
        supplier_file = base64.b64encode(b'supplier evidence')
        bank_file = base64.b64encode(b'bank evidence')
        self.decide(claim, 'supplier_accounts', supplier_accounts_notes='Supplier note',
                    cheque_attachment=supplier_file, cheque_filename='supplier.pdf')
        self.decide(claim, 'bank_accounts', bank_accounts_notes='Bank note',
                    bank_cheque_attachment=bank_file, bank_cheque_filename='bank.pdf')
        entries = claim.note_history_ids
        supplier_entry = entries.filtered(lambda entry: entry.department == 'supplier_accounts')
        bank_entry = entries.filtered(lambda entry: entry.department == 'bank_accounts')
        self.assertEqual(supplier_entry.cheque_attachment, supplier_file)
        self.assertEqual(supplier_entry.cheque_filename, 'supplier.pdf')
        self.assertEqual(bank_entry.cheque_attachment, bank_file)
        self.assertEqual(bank_entry.cheque_filename, 'bank.pdf')
        self.assertTrue(supplier_entry.occurred_at)
        self.assertFalse(claim.with_user(self.users['admin']).can_edit_current_review)
        with self.assertRaises(AccessError):
            bank_entry.with_user(self.outsider).read(['cheque_attachment'])
        with self.assertRaises(AccessError):
            bank_entry.write({'cheque_attachment': supplier_file})

    def test_attachment_only_history_note(self):
        claim = self.claim().with_context(lang='en_US')
        self.accounts(claim)
        self.assertFalse(claim.note_history_ids)
        self.decide(claim, 'supplier_accounts', cheque_attachment=base64.b64encode(b'supplier'),
                    cheque_filename='supplier.pdf', supplier_accounts_notes='  ')
        supplier_entry = claim.note_history_ids
        self.assertEqual(len(supplier_entry), 1)
        self.assertFalse(supplier_entry.reason)
        self.assertEqual(supplier_entry.display_note, 'Cheque attachment')
        self.assertEqual(supplier_entry.with_context(lang='ar_001').display_note, 'مرفق الشيك')
        self.decide(claim, 'bank_accounts', bank_cheque_attachment=base64.b64encode(b'bank'),
                    bank_cheque_filename='bank.pdf')
        self.assertEqual(len(claim.note_history_ids), 2)
        self.assertEqual(set(claim.note_history_ids.mapped('display_note')), {'Cheque attachment'})
        self.assertEqual(set(claim.note_history_ids.mapped('cheque_filename')), {'supplier.pdf', 'bank.pdf'})
        other = self.claim()
        self.accounts(other)
        self.decide(other, 'supplier_accounts', supplier_accounts_notes='User note',
                    cheque_attachment=base64.b64encode(b'proof'))
        self.assertEqual(other.note_history_ids.display_note, 'User note')

    def test_costcenter_lookup_and_security(self):
        CostCenter = self.env['ab_costcenter'].with_user(self.users['user'])
        self.assertIn(self.supplier.id, [row[0] for row in CostCenter.name_search('Cycle Supplier')])
        self.assertFalse(CostCenter.search(fields.Domain('id', '=', self.non_supplier_center.id)))
        with self.assertRaises(AccessError):
            self.non_supplier_center.with_user(self.users['user']).read(['name'])
        self.assertEqual(self.non_supplier_center.with_user(self.system).name, 'Internal Cost Center')

    def test_cash_closure_and_archive(self):
        claim=self.claim(True); claim.action_submit()
        self.assertEqual(claim.state,'supplier_accounts')
        for d in ('inventory','purchasing','bank_accounts'):self.assertEqual(claim[d+'_decision'],'not_required')
        self.decide(claim,'supplier_accounts')
        self.assertEqual(claim.state,'ready_to_close')
        for role in ('inventory','purchasing','supplier_accounts','bank_accounts','reviewer'):
            with self.assertRaises(AccessError):claim.with_user(self.users[role]).action_close()
        claim.action_close()
        for role in ('user','admin'):
            with self.assertRaises(UserError):claim.with_user(self.users[role]).write({'amount_of_check':'999'})
            with self.assertRaises(AccessError):claim.with_user(self.users[role]).unlink()
        with self.assertRaises(UserError):claim.sudo().unlink()
        claim.write({'active':False}); self.assertFalse(claim.active)
        claim.write({'active':True}); self.assertEqual(claim.state,'closed')

    def test_sequential_approvals_and_no_early_purchasing(self):
        claim = self.claim()
        claim.action_submit()
        self.assertEqual(claim.state, 'inventory')
        with self.assertRaises(AccessError):
            self.decide(claim, 'purchasing')
        for user in (self.users['admin'], self.system):
            with self.assertRaises(UserError):
                claim.with_user(user).action_decide('purchasing', 'approved')
            with self.assertRaises(AccessError):
                claim.with_user(user).write({'purchasing_notes': 'Too early'})
        self.decide(claim, 'inventory')
        self.assertEqual(claim.state, 'purchasing')
        self.decide(claim, 'purchasing')
        self.assertEqual(claim.state, 'supplier_accounts')
        self.decide(claim, 'supplier_accounts')
        self.assertEqual(claim.state, 'bank_accounts')
        self.decide(claim, 'bank_accounts')
        claim.action_close()
        self.assertEqual(claim.state, 'closed')

    def test_check_uses_full_review_route(self):
        claim = self.Claim.with_user(self.users['user']).create({
            **self.values(),
            'payment_nature': 'check',
        })
        claim.action_submit()
        self.assertEqual(claim.state, 'inventory')
        for department in ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts'):
            self.decide(claim, department)
        self.assertEqual(claim.state, 'ready_to_close')

    def test_sequential_rejection_new_round(self):
        for rejecting in ('inventory', 'purchasing'):
            claim = self.claim()
            claim.action_submit()
            if rejecting == 'purchasing':
                self.decide(claim, 'inventory')
            with self.assertRaises(ValidationError):
                self.decide(claim, rejecting, 'rejected')
            self.decide(claim, rejecting, 'rejected', **{rejecting + '_notes': 'Mismatch'})
            self.assertEqual(claim.state, 'returned_secretarial')
            claim.action_submit()
            self.assertEqual(claim.state, rejecting)
            self.assertEqual(claim.review_round, 2)
            self.assertEqual(claim[rejecting + '_decision'], 'pending')
            if rejecting == 'purchasing':
                self.assertEqual(claim.inventory_decision, 'approved')
            self.assertFalse(claim.history_ids.filtered(lambda h: h.decision == 'cancelled'))
            self.assertTrue(claim.history_ids.filtered(lambda h: h.reason == 'Mismatch' and h.review_round == 1))

    def test_late_rejections_resume(self):
        for stage in ('supplier_accounts','bank_accounts'):
            claim=self.claim()
            self.accounts(claim) if stage=='supplier_accounts' else self.bank(claim)
            self.decide(claim,stage,'rejected',**{stage+'_notes':'Please correct'})
            self.assertEqual(claim.resume_stage,stage)
            claim.write({'secretarial_notes':'Corrected'}); claim.action_submit()
            self.assertEqual(claim.state,stage)
            self.assertEqual(claim.inventory_decision,'approved')
            self.assertEqual(claim.purchasing_decision,'approved')
            self.assertEqual(claim[stage+'_decision'],'pending')

    def test_deferral_validation_every_department(self):
        for d in ('inventory','purchasing','supplier_accounts','bank_accounts'):
            claim=self.claim()
            if d=='bank_accounts':self.bank(claim)
            elif d=='supplier_accounts':self.accounts(claim)
            else:
                claim.action_submit()
                if d == 'purchasing': self.decide(claim, 'inventory')
            before=claim.state
            with self.assertRaises(ValidationError):self.decide(claim,d,'deferred')
            self.decide_write=claim.with_user(self.users[d])
            self.assertEqual(claim[d+'_followup_date'], fields.Date.context_today(claim))
            self.decide_write.write({d+'_notes':'Waiting', d+'_followup_date': False})
            with self.assertRaises(ValidationError):self.decide(claim,d,'deferred')
            self.decide_write.write({d+'_followup_date':fields.Date.today()-timedelta(days=1)})
            with self.assertRaises(ValidationError):self.decide(claim,d,'deferred')
            self.decide(claim,d,'deferred',**{d+'_followup_date':fields.Date.today()})
            self.assertEqual(claim.state,before); self.assertEqual(claim[d+'_decision'],'deferred')
            extra={'cheque_attachment':base64.b64encode(b'cheque')} if d=='supplier_accounts' else {}
            self.decide(claim,d,**extra)

    def test_security_every_group(self):
        claim=self.claim(); claim.action_submit()
        for role in self.roles:
            rec=claim.with_user(self.users[role])
            for vals in ({'state':'closed'},{'inventory_decision':'approved'},{'payment_nature':'cash'}, {'review_round':99}):
                with self.assertRaises(AccessError):rec.with_context(workflow_internal=True).write(vals)
            if role not in ('user','admin'):
                with self.assertRaises(AccessError):self.Claim.with_user(self.users[role]).create(self.values())
                with self.assertRaises(AccessError):rec.write({'amount_of_check':'22'})
            if role not in ('inventory','admin'):
                with self.assertRaises(AccessError):rec.action_decide('inventory','approved')
            if role not in ('purchasing','admin'):
                with self.assertRaises(AccessError):rec.write({'purchasing_notes':'Forged'})
        with self.assertRaises(AccessError):claim.with_user(self.outsider).read(['state'])
        with self.assertRaises(AccessError):claim.with_user(self.users['bank_accounts']).read(['state'])
        self.assertEqual(claim.with_user(self.users['reviewer']).state,'inventory')
        with self.assertRaises(AccessError):self.Claim.with_user(self.users['user']).create(dict(self.values(),state='closed'))
        draft=self.Claim.with_user(self.users['user']).with_context(default_state='closed',default_inventory_decision='approved').create(self.values())
        self.assertEqual(draft.state,'draft'); self.assertEqual(draft.inventory_decision,'not_required')
        self.assertTrue(self.system.has_group('ab_supplier_claim_cycle.supplier_claim_group_admin'))
        claim.with_user(self.system).action_decide('inventory','approved')
        claim.with_user(self.users['admin']).action_decide('purchasing','approved')
        with self.assertRaises(AccessError):claim.with_user(self.users['inventory']).write({'inventory_notes':'Late'})
        with self.assertRaises(AccessError):claim.with_user(self.users['supplier_accounts']).action_decide('bank_accounts','approved')
        with self.assertRaises(AccessError):claim.with_user(self.users['supplier_accounts']).action_submit()
        with self.assertRaises(AccessError):claim.with_user(self.users['user']).action_decide('supplier_accounts','approved')

    def test_history_immutable_and_visibility(self):
        claim=self.claim(); self.accounts(claim)
        history=claim.history_ids
        for role in self.roles:
            h=history.with_user(self.users[role])
            with self.assertRaises(AccessError):h.write({'reason':'Forgery'})
            with self.assertRaises(AccessError):h.unlink()
            with self.assertRaises(AccessError):self.env['ab_supplier_claim_cycle.history'].with_user(self.users[role]).create({'claim_id':claim.id})
        self.assertTrue(history.filtered(lambda h:h.department=='inventory' and h.user_id==self.users['inventory']))
        with self.assertRaises(AccessError):history.with_user(self.users['bank_accounts']).read(['reason'])

    def test_buttons_and_view_validation(self):
        view=self.env.ref('ab_supplier_claim_cycle.invoice_view_form')
        view._check_xml()
        for role in self.roles:
            arch=self.Claim.with_user(self.users[role]).get_view(view_id=view.id,view_type='form')['arch']
            tree=etree.fromstring(arch)
            self.assertFalse(tree.xpath('//notebook/page'))
            self.assertTrue(tree.xpath('//field[@name="note_history_ids"]/list[@no_open="True"]'))
            self.assertFalse(tree.xpath('//sheet//button'))
            self.assertTrue(tree.xpath('//group[@name="department_reviews"]'))
            for department in ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts'):
                self.assertTrue(tree.xpath(
                    '//group[@name="department_reviews"]//field[@name="%s_notes"]' % department))
            closures=tree.xpath("//button[@name='action_close']")
            self.assertEqual(bool(closures),role in ('user','admin'))
            for button in tree.xpath("//button[@name='action_department_decision']"):
                self.assertIn(role,('admin','inventory','purchasing','supplier_accounts','bank_accounts'))
                self.assertIn("not in ('pending', 'deferred')",button.get('invisible'))
                if role!='admin':self.assertIn("'claim_department': '"+role+"'",button.get('context'))

    def test_secretarial_form_create(self):
        with Form(self.Claim.with_user(self.users['user'])) as form:
            form.supplier_id = self.cash
            form.num_of_invoice = 3
            form.area = 'north'
            form.amount_of_check = '200'
            form.type_of_invoice = 'original'
        self.assertEqual(form.record.state, 'draft')

    def test_purchasing_rejection_preserves_inventory_and_early_close(self):
        claim = self.claim()
        with self.assertRaises(UserError):
            claim.action_close()
        claim.action_submit()
        self.decide(claim, 'inventory')
        self.decide(claim, 'purchasing', 'rejected', purchasing_notes='Invoice mismatch')
        claim.action_submit()
        self.assertEqual(claim.inventory_decision, 'approved')
        self.assertEqual(claim.purchasing_decision, 'pending')
        self.assertEqual(claim.review_round, 2)

    def test_multi_record_actions(self):
        claims = self.Claim.with_user(self.users['user']).create([self.values(True), self.values(True)])
        claims.action_submit()
        claims.with_user(self.users['supplier_accounts']).action_decide('supplier_accounts', 'approved')
        claims.action_close()
        self.assertEqual(set(claims.mapped('state')), {'closed'})
        claims.write({'active': False})
        self.assertFalse(any(claims.mapped('active')))

    def test_force_unlink_context_cannot_bypass_protection(self):
        claim = self.claim(True)
        claim.action_submit()
        self.decide(claim, 'supplier_accounts')
        with self.assertRaises(UserError):
            claim.sudo().with_context(_force_unlink=True).unlink()
        with self.assertRaises(UserError):
            self.supplier.sudo().with_context(_force_unlink=True).unlink()
        with self.assertRaises(AccessError):
            claim.history_ids.sudo().with_context(_force_unlink=True).unlink()

    def test_optional_cheques_and_bank_upload_access(self):
        claim = self.claim()
        self.accounts(claim)
        self.decide(claim, 'supplier_accounts')
        self.assertEqual(claim.state, 'bank_accounts')
        self.assertFalse(claim.cheque_attachment)
        for role in ('user', 'inventory', 'purchasing', 'supplier_accounts', 'reviewer'):
            with self.assertRaises(AccessError):
                claim.with_user(self.users[role]).write({'bank_cheque_attachment': base64.b64encode(b'bank')})
        claim.with_user(self.users['bank_accounts']).write({
            'bank_cheque_attachment': base64.b64encode(b'bank'), 'bank_cheque_filename': 'bank.pdf'})
        self.assertTrue(claim.bank_cheque_attachment)
        self.assertFalse(claim.cheque_attachment)
        self.decide(claim, 'bank_accounts')
        with self.assertRaises(AccessError):
            claim.with_user(self.users['bank_accounts']).write({'bank_cheque_attachment': False})
        claim.action_close()
        other = self.claim()
        self.accounts(other)
        self.decide(other, 'supplier_accounts')
        self.decide(other, 'bank_accounts')
        other.action_close()
        self.assertEqual(other.state, 'closed')

    def test_evidence_and_archived_claim_protection(self):
        claim = self.claim()
        self.bank(claim)
        with self.assertRaises(AccessError):
            claim.with_user(self.users['supplier_accounts']).write({'cheque_attachment': False})
        self.decide(claim, 'bank_accounts')
        claim.action_close()
        with self.assertRaises(UserError):
            claim.with_user(self.users['admin']).write({'cheque_attachment': False})
        claim.write({'active': False})
        with self.assertRaises(UserError):
            claim.action_submit()
        self.assertTrue(claim.cheque_attachment)

    def test_deferred_details_cannot_be_cleared(self):
        claim = self.claim()
        claim.action_submit()
        self.decide(claim, 'inventory', 'deferred', inventory_notes='Awaiting receipt',
                    inventory_followup_date=fields.Date.today())
        for vals in ({'inventory_notes': False}, {'inventory_followup_date': False}):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                claim.with_user(self.users['inventory']).write(vals)
        self.assertEqual(claim.inventory_decision, 'deferred')
        self.assertTrue(claim.inventory_followup_date)

    def test_rejected_cycles_finish_with_audited_closure(self):
        for cash, rejecting in ((False, 'inventory'), (False, 'purchasing'),
                                (False, 'supplier_accounts'), (False, 'bank_accounts'),
                                (True, 'supplier_accounts')):
            with self.subTest(cash=cash, rejecting=rejecting):
                claim = self.claim(cash)
                if cash or rejecting in ('inventory', 'purchasing'):
                    claim.action_submit()
                    if rejecting == 'purchasing': self.decide(claim, 'inventory')
                elif rejecting == 'supplier_accounts':
                    self.accounts(claim)
                else:
                    self.bank(claim)
                self.decide(claim, rejecting, 'rejected', **{rejecting + '_notes': 'Correct invoice'})
                self.assertEqual(claim.state, 'returned_secretarial')
                claim.write({'secretarial_notes': 'Invoice corrected'})
                claim.action_submit()
                self.assertEqual(claim.review_round, 2)
                if claim.state == 'inventory':
                    self.decide(claim, 'inventory')
                if claim.state == 'purchasing':
                    self.decide(claim, 'purchasing')
                if claim.state == 'supplier_accounts':
                    evidence = {} if cash else {'cheque_attachment': base64.b64encode(b'corrected cheque')}
                    self.decide(claim, 'supplier_accounts', **evidence)
                if claim.state == 'bank_accounts':
                    self.decide(claim, 'bank_accounts')
                self.assertEqual(claim.state, 'ready_to_close')
                claim.action_close()
                self.assertEqual(claim.state, 'closed')
                history = claim.history_ids.sorted('id')
                self.assertEqual(history[-1].event, 'closed')
                self.assertEqual(history[-1].user_id, self.users['user'])
                self.assertEqual(history[-1].review_round, 2)
                self.assertTrue(all(history.mapped('occurred_at')))
                for previous, current in zip(history, history[1:]):
                    if current.decision != 'cancelled':
                        self.assertEqual(previous.to_state, current.from_state)

    def test_stage_permissions_and_queues_every_department(self):
        from odoo.tools.safe_eval import safe_eval
        for department in ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts'):
            with self.subTest(department=department):
                claim = self.claim()
                if department == 'bank_accounts':
                    self.bank(claim)
                elif department == 'supplier_accounts':
                    self.accounts(claim)
                else:
                    claim.action_submit()
                    if department == 'purchasing': self.decide(claim, 'inventory')
                for role in self.roles:
                    rec = claim.with_user(self.users[role])
                    if role not in (department, 'admin'):
                        with self.assertRaises(AccessError), self.env.cr.savepoint():
                            rec.write({department + '_notes': 'Unauthorized'})
                        with self.assertRaises(AccessError), self.env.cr.savepoint():
                            rec.action_decide(department, 'approved')
                    with self.assertRaises(AccessError), self.env.cr.savepoint():
                        rec.write({department + '_decision': 'approved'})
                self.decide(claim, department, 'deferred', **{
                    department + '_notes': 'Awaiting documents',
                    department + '_followup_date': fields.Date.today(),
                })
                queue_domain = fields.Domain('state', '=', department)
                queue_model = self.Claim.with_user(self.users[department])
                self.assertIn(claim, queue_model.search(queue_domain))
                self.assertTrue(claim.with_user(self.users[department]).has_access('write'))
                extra = {'cheque_attachment': base64.b64encode(b'cheque')} if department == 'supplier_accounts' else {}
                self.decide(claim, department, **extra)
                self.assertNotIn(claim, queue_model.search(queue_domain))

    def test_administrators_complete_both_routes(self):
        for user in (self.users['admin'], self.system):
            for cash in (False, True):
                with self.subTest(user=user.login, cash=cash):
                    claim = self.Claim.with_user(user).create(self.values(cash))
                    claim.action_submit()
                    if not cash:
                        claim.action_decide('inventory', 'approved')
                        claim.action_decide('purchasing', 'approved')
                        claim.write({'cheque_attachment': base64.b64encode(b'cheque')})
                    claim.action_decide('supplier_accounts', 'approved')
                    if not cash:
                        claim.action_decide('bank_accounts', 'approved')
                    claim.action_close()
                    self.assertEqual(claim.state, 'closed')
                    self.assertEqual(set(claim.history_ids.mapped('user_id').ids), {user.id})
                    with self.assertRaises(UserError):
                        claim.write({'secretarial_notes': 'Forbidden after closure'})

    def test_shared_claims_menu_and_completed_visibility(self):
        from odoo.tools.safe_eval import safe_eval
        action = self.env.ref('ab_supplier_claim_cycle.invoice_action')
        self.assertEqual(safe_eval(action.domain), [])
        self.assertEqual(safe_eval(action.context), {})
        menu = self.env.ref('ab_supplier_claim_cycle.invoice_menu')
        for user in [*self.users.values(), self.system]:
            visible = self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
            self.assertIn(menu.id, visible)
        self.assertNotIn(menu.id, self.env['ir.ui.menu'].with_user(self.outsider)._visible_menu_ids())

        claim = self.claim()
        claim.action_submit()
        domain = fields.Domain('id', '=', claim.id)
        def assert_visible(role):
            self.assertIn(claim, self.Claim.with_user(self.users[role]).search(domain))
        assert_visible('user')
        self.assertFalse(self.Claim.with_user(self.users['bank_accounts']).search(domain))
        self.decide(claim, 'inventory', 'deferred', inventory_notes='Waiting',
                    inventory_followup_date=fields.Date.today())
        assert_visible('inventory')
        self.decide(claim, 'inventory')
        self.decide(claim, 'purchasing')
        assert_visible('inventory')
        assert_visible('purchasing')
        self.decide(claim, 'supplier_accounts', 'rejected', supplier_accounts_notes='Correct invoice')
        assert_visible('supplier_accounts')
        assert_visible('user')
        claim.action_submit()
        self.decide(claim, 'supplier_accounts', cheque_attachment=base64.b64encode(b'cheque'))
        assert_visible('supplier_accounts')
        self.decide(claim, 'bank_accounts')
        claim.action_close()
        for role in self.roles:
            assert_visible(role)
        self.assertIn(claim, self.Claim.with_user(self.system).search(domain))
        claim.write({'active': False})
        for role in self.roles:
            self.assertIn(claim, self.Claim.with_user(self.users[role]).with_context(active_test=False).search(domain))

    def test_plain_form_stage_visibility(self):
        from odoo.tools.safe_eval import safe_eval
        view = self.env.ref('ab_supplier_claim_cycle.invoice_view_form')
        departments = ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts')
        for user in [*self.users.values(), self.system]:
            for lang in ('en_US', 'ar_001'):
                arch = etree.fromstring(self.Claim.with_user(user).with_context(lang=lang).get_view(
                    view_id=view.id, view_type='form')['arch'])
                self.assertTrue(arch.xpath("//div[@class='o_scc_top_tracking']"))
                values = dict(state='draft', payment_nature='bank_transfer', active=True, cheque_attachment=False, resume_stage=False,
                              **{d + '_decision': 'pending' for d in departments})
                def visible(node):
                    return not any(safe_eval(parent.get('invisible', 'False'), values)
                                   for parent in [node, *node.iterancestors()])
                for stage in ('draft', *departments, 'returned_secretarial', 'ready_to_close', 'closed'):
                    values['state'] = stage
                    authorized = stage in departments and (user in (self.users['admin'], self.system) or user == self.users[stage])
                    values['can_edit_current_review'] = authorized
                    notes = [node.get('name') for node in arch.xpath(
                        '//group[@name="department_reviews"]//field[contains(@name,"_notes")]') if visible(node)]
                    self.assertEqual(notes, [stage + '_notes'] if authorized else [])
                    buttons = [n for n in arch.xpath('//header/button[@name="action_department_decision"]') if visible(n)]
                    authorized = stage in departments and (user in (self.users['admin'], self.system)
                                                            or user == self.users[stage])
                    self.assertEqual(len(buttons), 3 if authorized else 0)
                    if lang == 'en_US' and buttons:
                        self.assertEqual([n.get('string') for n in buttons], ['Approve', 'Reject', 'Defer'])
                    rejection = arch.xpath('//field[@name="rejection_reason"]')[0]
                    self.assertEqual(visible(rejection), stage == 'returned_secretarial')
                    for node in arch.xpath('//group[@name="department_reviews"]//field[@name="cheque_attachment"]'):
                        expected = authorized and stage == 'supplier_accounts' and node.get('invisible') != 'not cheque_attachment'
                        self.assertEqual(visible(node), expected)
                for nature in ('cash', 'bank_transfer', 'check'):
                    values.update(payment_nature=nature, state='supplier_accounts')
                    bars = [n for n in arch.xpath('//header/field[@widget="statusbar"]') if visible(n)]
                    self.assertEqual(len(bars), 1)
                    self.assertEqual('inventory' in bars[0].get('statusbar_visible'), nature != 'cash')
                values.update(state='inventory', active=False)
                self.assertFalse(any(visible(n) for n in arch.xpath('//header/button')))

    def test_history_starts_with_department_decisions(self):
        History = self.env['ab_supplier_claim_cycle.history']
        for cash in (False, True):
            claim = self.claim(cash)
            domain = fields.Domain('claim_id', '=', claim.id)
            self.assertFalse(History.search(domain))
            claim.action_submit()
            self.assertFalse(History.search(domain))
            self.assertFalse(claim.history_ids)
            department = 'supplier_accounts' if cash else 'inventory'
            self.decide(claim, department, 'rejected', **{department + '_notes': 'Review invoice'})
            self.assertEqual(claim.history_ids.mapped('event'), ['decision'])
            claim.action_submit()
            self.assertEqual(set(claim.history_ids.mapped('event')), {'decision', 'resubmitted'})

    def test_inline_secretarial_note_history_and_permissions(self):
        claim = self.claim()
        self.assertFalse(claim.history_ids)
        for role in self.roles:
            if role not in ('user', 'admin'):
                with self.assertRaises(AccessError):
                    claim.with_user(self.users[role]).write({'secretarial_notes': 'Unauthorized'})
        claim.write({'secretarial_notes': '  '})
        self.assertFalse(claim.history_ids)
        claim.write({'secretarial_notes': 'Invoice documents checked'})
        row = claim.history_ids
        self.assertEqual(len(row), 1)
        self.assertEqual((row.event, row.department, row.reason),
                         ('secretarial_note', 'secretarial', 'Invoice documents checked'))
        self.assertEqual(row.user_id, self.users['user'])
        self.assertTrue(row.occurred_at)
        claim.action_submit()
        with self.assertRaises(AccessError):
            claim.with_user(self.users['admin']).write({'secretarial_notes': 'Wrong stage'})
        self.decide(claim, 'inventory', 'rejected', inventory_notes='Correct documents')
        claim.write({'secretarial_notes': 'Documents corrected'})
        self.assertEqual(len(claim.history_ids.filtered(lambda h: h.department == 'secretarial')), 2)
        with self.assertRaises(AccessError):
            row.write({'reason': 'Changed'})
        with self.assertRaises(AccessError):
            row.unlink()
        claim.write({'active': False})
        with self.assertRaises(UserError):
            claim.write({'secretarial_notes': 'Archived'})
        closed = self.claim(True)
        closed.action_submit()
        self.decide(closed, 'supplier_accounts')
        closed.action_close()
        with self.assertRaises(UserError):
            closed.write({'secretarial_notes': 'Closed'})

    def test_claim_attachment_permissions(self):
        draft_file = base64.b64encode(b'draft attachment')
        claim = self.Claim.with_user(self.users['user']).create({
            **self.values(),
            'attachment': draft_file,
        })
        self.assertEqual(claim.attachment, draft_file)

        updated_file = base64.b64encode(b'updated attachment')
        claim.write({'attachment': updated_file})
        self.assertEqual(claim.attachment, updated_file)

        claim.action_submit()
        with self.assertRaises(AccessError):
            claim.with_user(self.users['inventory']).write({'attachment': draft_file})

    def test_secretarial_note_api_and_form_visibility(self):
        claim = self.Claim.with_user(self.users['user']).create({**self.values(), 'secretarial_notes': 'First note'})
        self.assertEqual(claim.history_ids.reason, 'First note')
        claim.write({'secretarial_notes': 'Second note'})
        self.assertEqual(len(claim.history_ids), 2)
        claim.write({'secretarial_notes': 'Second note'})
        self.assertEqual(len(claim.history_ids), 2)
        claim.write({'secretarial_notes': False})
        self.assertEqual(len(claim.history_ids), 2)
        claim._log('restored')
        claim._log('decision', department='inventory', reason='   ')
        self.assertEqual(len(claim.note_history_ids), 2)
        self.assertEqual(len(claim.history_ids), 4)
        self.assertEqual(set(claim.note_history_ids.mapped('reason')), {'First note', 'Second note'})
        with self.assertRaises(AccessError):
            claim.with_user(self.users['inventory']).write({'secretarial_notes': 'Unauthorized'})
        view = self.env.ref('ab_supplier_claim_cycle.invoice_view_form')
        for role in self.roles:
            for lang in ('en_US', 'ar_001'):
                arch = etree.fromstring(self.Claim.with_user(self.users[role]).with_context(lang=lang).get_view(
                    view_id=view.id, view_type='form')['arch'])
                self.assertTrue(arch.xpath('//group[@name="claim_secretarial_review"]//field[@name="secretarial_notes"]'))
                self.assertTrue(arch.xpath('//group[@name="claim_secretarial_review"]//field[@name="attachment"]'))
                self.assertTrue(arch.xpath('//chatter'))
                buttons = arch.xpath('//button[@name="action_open_secretarial_note"]')
                self.assertFalse(buttons)
                self.assertTrue(arch.xpath('//field[@name="note_history_ids"]/list/field[@name="display_note"]'))

    def test_timeline_payment_routes(self):
        from odoo.tools.safe_eval import safe_eval
        arch = etree.fromstring(self.Claim.get_view(
            view_id=self.env.ref('ab_supplier_claim_cycle.invoice_view_form').id, view_type='form')['arch'])
        self.assertTrue(arch.xpath('//field[@name="note_history_ids"]/list[@no_open="True"]'))
        steps = arch.xpath('//div[@class="o_scc_route_step"]')
        for nature, count in [('cash', 3), ('bank_transfer', 6), ('check', 6)]:
            values = dict(payment_nature=nature, state='draft', resume_stage=False,
                          **{d + '_decision': 'not_required' for d in ('inventory','purchasing','supplier_accounts','bank_accounts')})
            visible = [node for node in steps if not safe_eval(node.get('invisible', 'False'), values)]
            self.assertEqual(len(visible), count)
            for node in visible:
                variants = [part for part in node if not safe_eval(part.get('invisible', 'False'), values)]
                self.assertEqual(len(variants), 1)

    def test_latest_claim_defaults_include_archived_drafts(self):
        older = self.claim()
        older.write({
            'type_of_invoice': 'original', 'payment_nature': 'bank_transfer',
            'tax_classification': 'tax_payment', 'section': 'medical',
        })
        latest = self.claim()
        latest.write({
            'type_of_invoice': 'copy', 'payment_nature': 'cash',
            'tax_classification': 'through_supplier', 'section': 'cosmo',
        })
        latest.write({'active': False})

        values = {
            'supplier_id': self.supplier.id, 'num_of_invoice': 3,
            'area': 'south', 'amount_of_check': '250',
        }
        claim = self.Claim.with_user(self.users['user']).create(values)
        self.assertEqual(
            tuple(claim[name] for name in ('type_of_invoice', 'payment_nature', 'tax_classification', 'section')),
            ('copy', 'cash', 'through_supplier', 'cosmo'),
        )

    def test_explicit_values_override_previous_claim(self):
        self.claim()
        values = {
            **self.values(),
            'type_of_invoice': 'copy', 'payment_nature': 'cash',
            'tax_classification': 'non_tax_payment', 'section': 'other',
        }
        claim = self.Claim.with_user(self.users['user']).create(values)
        self.assertEqual(
            tuple(claim[name] for name in ('type_of_invoice', 'payment_nature', 'tax_classification', 'section')),
            ('copy', 'cash', 'non_tax_payment', 'other'),
        )

    def test_supplier_change_loads_or_clears_previous_values(self):
        previous_cash = self.claim(True)
        previous_cash.write({
            'type_of_invoice': 'copy', 'tax_classification': 'through_supplier', 'section': 'cosmo',
        })
        draft = self.claim()
        draft.write({'supplier_id': self.cash.id})
        self.assertEqual(
            tuple(draft[name] for name in ('type_of_invoice', 'payment_nature', 'tax_classification', 'section')),
            ('copy', 'cash', 'through_supplier', 'cosmo'),
        )

        empty_center = self.env['ab_costcenter'].create({'name': 'No Claims', 'code': '1-99'})
        draft.write({'supplier_id': empty_center.id})
        self.assertFalse(any(draft[name] for name in (
            'type_of_invoice', 'payment_nature', 'tax_classification', 'section',
        )))

    def test_draft_form_uses_latest_claim_values(self):
        previous = self.claim()
        previous.write({
            'type_of_invoice': 'copy', 'payment_nature': 'cash',
            'tax_classification': 'through_supplier', 'section': 'other',
        })
        with Form(self.Claim.with_user(self.users['user'])) as form:
            form.supplier_id = self.supplier
            self.assertEqual(form.type_of_invoice, 'copy')
            self.assertEqual(form.payment_nature, 'cash')
            self.assertEqual(form.tax_classification, 'through_supplier')
            self.assertEqual(form.section, 'other')
            form.num_of_invoice = 2
            form.area = 'north'
            form.amount_of_check = '100'
        self.assertEqual(form.record.supplier_id, self.supplier)

    def test_classification_form_is_editable_only_for_secretarial_drafts(self):
        for role in self.roles:
            arch = etree.fromstring(self.Claim.with_user(self.users[role]).get_view(
                view_id=self.env.ref('ab_supplier_claim_cycle.invoice_view_form').id, view_type='form')['arch'])
            for name in ('tax_classification', 'section', 'payment_nature'):
                nodes = arch.xpath('//group[@name="supplier_classification"]/field[@name="%s"]' % name)
                self.assertTrue(nodes)
                expected = "state != 'draft' or not active" if role in ('user', 'admin') else 'True'
                self.assertTrue(all(node.get('readonly') == expected for node in nodes))
        previous = self.claim()
        with Form(self.Claim.with_user(self.users['user'])) as form:
            form.supplier_id = self.supplier
            self.assertEqual(form.tax_classification, previous.tax_classification)
            form.num_of_invoice = 1
            form.area = 'north'
            form.amount_of_check = '100'
            form.type_of_invoice = 'original'
        self.assertEqual(form.record.supplier_id, self.supplier)

    def test_fresh_model_contract(self):
        self.assertEqual(set(dict(self.Claim._fields['state'].selection)), {
            'draft', 'inventory', 'purchasing', 'supplier_accounts', 'bank_accounts',
            'returned_secretarial', 'ready_to_close', 'closed',
        })
        self.assertEqual(self.Claim._fields['supplier_id'].comodel_name, 'ab_costcenter')
        self.assertNotIn('business_category', self.Claim._fields)
        self.assertNotIn('bracket_id', self.Claim._fields)
        self.assertNotIn('bracket_snapshot', self.env['ab_supplier_claim_cycle.history']._fields)
        self.assertEqual(set(dict(self.env['ab_supplier_claim_cycle.history']._fields['event'].selection)), {
            'resubmitted', 'decision', 'closed', 'archived', 'restored', 'secretarial_note',
        })
        self.supplier.active = False
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.claim().action_submit()

    def test_followup_defaults_and_exception_steps(self):
        claim = self.claim()
        claim.action_submit()
        for department in ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts'):
            record = claim.with_user(self.users[department])
            today = fields.Date.context_today(record)
            self.assertEqual(record[f'{department}_followup_date'], today)
            future = today + timedelta(days=3)
            self.decide(claim, department, 'deferred', **{
                f'{department}_notes': 'Waiting for documents',
                f'{department}_followup_date': future})
            self.assertEqual(record[f'{department}_followup_date'], future)
            self.decide(claim, department, 'deferred')
            self.decide(claim, department, 'rejected')
            events = claim[f'timeline_{department}_exception_ids']
            self.assertEqual(events.mapped('decision'), ['deferred', 'deferred', 'rejected'])
            self.assertEqual(events.mapped('user_id'), self.users[department])
            self.assertEqual(events[0].followup_date, future)
            claim.action_submit()
            self.assertEqual(record[f'{department}_followup_date'], today)
            self.decide(claim, department)
            self.assertEqual(claim[f'timeline_{department}_exception_ids'], events)
        with self.assertRaises(AccessError):
            claim.with_user(self.outsider).read(['timeline_inventory_exception_ids'])
        cash = self.claim(cash=True)
        cash.action_submit()
        self.assertEqual(cash.supplier_accounts_followup_date, fields.Date.context_today(cash))
