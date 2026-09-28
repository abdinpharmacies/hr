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
        cls.roles = ('user', 'inventory', 'purchasing', 'supplier_accounts', 'bank_accounts', 'reviewer', 'admin')
        cls.users = {role: new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True)), login='scc_test_'+role,
                     groups='ab_supplier_claim_cycle.supplier_claim_group_'+role) for role in cls.roles}
        cls.outsider = new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True)), login='scc_test_outsider', groups='base.group_user')
        cls.system = new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True)), login='scc_test_system', groups='base.group_system')
        cls.supplier = cls.env['ab_supplier'].create({'name':'Cycle Supplier Alpha', 'code':'SCC-42',
                                                    'business_category':'medicine', 'tax_type':'tax_payment'})
        cls.cash = cls.env['ab_supplier'].create({'name':'Cash Supplier', 'code':'SCC-43', 'payment_nature':'cash'})
        cls.Claim = cls.env['ab_supplier_claim_cycle']

    def claim(self, cash=False):
        return self.Claim.with_user(self.users['user']).create(self.values(cash))

    def values(self, cash=False):
        return dict(supplier_id=(self.cash if cash else self.supplier).id, num_of_invoice=2,
                    area='north', amount_of_check='100', type_of_invoice='original')

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

    def test_supplier_lookup_defaults_and_snapshot(self):
        self.assertEqual(self.supplier.payment_nature,'non_cash')
        Supplier=self.env['ab_supplier'].with_user(self.users['user'])
        self.assertIn(self.supplier.id,[r[0] for r in Supplier.name_search('Cycle Supplier')])
        self.assertIn(self.supplier.id,[r[0] for r in Supplier.name_search('SCC-4')])
        claim=self.claim(); claim.action_submit()
        self.supplier.write({'payment_nature':'cash','business_category':'cosmetics','tax_type':'non_tax_payment'})
        self.assertEqual((claim.payment_nature,claim.business_category,claim.tax_classification),('non_cash','medicine','tax_payment'))
        self.decide(claim,'inventory','rejected',inventory_notes='Correct invoices')
        claim.action_submit()
        self.assertEqual(claim.state,'inventory')
        self.assertEqual(claim.payment_nature,'non_cash')

    def test_payment_nature_choice_and_route(self):
        claim = self.claim()
        self.assertEqual(claim.payment_nature, 'non_cash')
        claim.write({'payment_nature': 'cash'})
        claim.invalidate_recordset()
        self.assertEqual(claim.payment_nature, 'cash')
        self.assertEqual(self.supplier.payment_nature, 'cash')
        self.assertEqual(self.claim().payment_nature, 'cash')
        claim.action_submit()
        self.assertEqual(claim.state, 'supplier_accounts')
        self.assertEqual(claim.inventory_decision, 'not_required')
        with self.assertRaises(AccessError):
            claim.write({'payment_nature': 'non_cash'})
        self.decide(claim, 'supplier_accounts', 'rejected', supplier_accounts_notes='Correct invoice')
        with self.assertRaises(AccessError):
            claim.write({'payment_nature': 'non_cash'})
        claim.action_submit()
        self.assertEqual((claim.payment_nature, claim.state), ('cash', 'supplier_accounts'))

    def test_payment_nature_batch_defaults_and_form(self):
        claims = self.Claim.with_user(self.users['user']).create([
            dict(self.values(), payment_nature='cash'),
            dict(self.values(), payment_nature='non_cash'),
        ])
        self.assertEqual(claims.mapped('payment_nature'), ['cash', 'non_cash'])
        self.assertEqual(self.supplier.payment_nature, 'non_cash')
        view = self.env.ref('ab_supplier_claim_cycle.invoice_view_form')
        arch = etree.fromstring(self.Claim.with_user(self.users['user']).get_view(
            view_id=view.id, view_type='form')['arch'])
        nodes = arch.xpath('//group[@name="supplier_classification"]/field[@name="payment_nature"]')
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].get('readonly'), "state != 'draft' or not active")
        choices = self.Claim.with_context(lang='ar_001').fields_get(['payment_nature'])['payment_nature']['selection']
        self.assertEqual(choices, [('cash', 'نقدي'), ('non_cash', 'غير نقدي')])

    def test_payment_nature_draft_access_and_validation(self):
        claim = self.Claim.with_user(self.users['user']).create(dict(self.values(True), payment_nature='non_cash'))
        self.assertEqual(claim.payment_nature, 'non_cash')
        for role in ('inventory', 'purchasing', 'supplier_accounts', 'bank_accounts', 'reviewer'):
            with self.assertRaises(AccessError):
                claim.with_user(self.users[role]).write({'payment_nature': 'cash'})
        claim.write({'payment_nature': False})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            claim.action_submit()
        claim.write({'supplier_id': self.supplier.id})
        self.assertEqual(claim.payment_nature, self.supplier.payment_nature)
        claim.action_submit()
        self.assertEqual(claim.state, 'inventory')

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
        with self.assertRaises(ValidationError):
            self.decide(claim, 'supplier_accounts')
        self.decide(claim, 'supplier_accounts', cheque_attachment=base64.b64encode(b'cheque'))
        self.assertEqual(claim.state, 'bank_accounts')
        self.decide(claim, 'bank_accounts')
        claim.action_close()
        self.assertEqual(claim.state, 'closed')

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
            self.decide_write.write({d+'_notes':'Waiting'})
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
            self.assertEqual(tree.xpath('//notebook/page/@name'), ['history'])
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
                action = self.env.ref('ab_supplier_claim_cycle.queue_' + department)
                queue_model = self.Claim.with_user(self.users[department])
                self.assertIn(claim, queue_model.search(safe_eval(action.domain)))
                self.assertTrue(claim.with_user(self.users[department]).has_access('write'))
                extra = {'cheque_attachment': base64.b64encode(b'cheque')} if department == 'supplier_accounts' else {}
                self.decide(claim, department, **extra)
                self.assertNotIn(claim, queue_model.search(safe_eval(action.domain)))

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
        queue_ids = [self.env.ref('ab_supplier_claim_cycle.queue_menu_' + role).id
                     for role in ('user', 'inventory', 'purchasing', 'supplier_accounts', 'bank_accounts')]
        for user in [*self.users.values(), self.system]:
            visible = self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
            self.assertIn(menu.id, visible)
            self.assertFalse(set(queue_ids) & visible)
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
                self.assertFalse(arch.xpath('//div | //details | //section'))
                values = dict(state='draft', payment_nature='non_cash', active=True,
                              **{d + '_decision': 'pending' for d in departments})
                def visible(node):
                    return not any(safe_eval(parent.get('invisible', 'False'), values)
                                   for parent in [node, *node.iterancestors()])
                for stage in ('draft', *departments, 'returned_secretarial', 'ready_to_close', 'closed'):
                    values['state'] = stage
                    notes = [node.get('name') for node in arch.xpath(
                        '//group[@name="department_reviews"]//field[contains(@name,"_notes")]') if visible(node)]
                    self.assertEqual(notes, [stage + '_notes'] if stage in departments else [])
                    buttons = [n for n in arch.xpath('//header/button[@name="action_department_decision"]') if visible(n)]
                    authorized = stage in departments and (user in (self.users['admin'], self.system)
                                                            or user == self.users[stage])
                    self.assertEqual(len(buttons), 3 if authorized else 0)
                    if lang == 'en_US' and buttons:
                        self.assertEqual([n.get('string') for n in buttons], ['Approve', 'Reject', 'Defer'])
                    rejection = arch.xpath('//field[@name="rejection_reason"]')[0]
                    self.assertEqual(visible(rejection), stage == 'returned_secretarial')
                    for node in arch.xpath('//field[@name="cheque_attachment"]'):
                        self.assertEqual(visible(node), stage == 'supplier_accounts')
                for nature in ('cash', 'non_cash'):
                    values.update(payment_nature=nature, state='supplier_accounts')
                    bars = [n for n in arch.xpath('//header/field[@widget="statusbar"]') if visible(n)]
                    self.assertEqual(len(bars), 1)
                    self.assertEqual('inventory' in bars[0].get('statusbar_visible'), nature == 'non_cash')
                values.update(state='inventory', active=False)
                self.assertFalse(any(visible(n) for n in arch.xpath('//header/button')))

    def test_legacy_sequential_migration(self):
        import importlib.util
        from pathlib import Path
        path = Path(__file__).parents[1] / 'migrations/19.0.2.1.0/post-migrate.py'
        spec = importlib.util.spec_from_file_location('scc_sequential_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        cases = []
        for inventory, purchasing, expected in (
                ('pending', 'pending', 'inventory'), ('approved', 'pending', 'purchasing'),
                ('pending', 'approved', 'inventory'), ('approved', 'approved', 'supplier_accounts')):
            claim = self.claim()
            claim.action_submit()
            claim._workflow_write(dict(state='inventory_purchase', inventory_decision=inventory,
                                       purchasing_decision=purchasing))
            claim._log('decision', 'inventory_purchase')
            cases.append((claim, expected, claim.history_ids.ids))
        returned = self.claim()
        returned.action_submit()
        self.decide(returned, 'inventory')
        self.decide(returned, 'purchasing', 'rejected', purchasing_notes='Correct')
        returned._workflow_write({'resume_stage': 'inventory_purchase'})
        returned_inventory = self.claim()
        returned_inventory.action_submit()
        self.decide(returned_inventory, 'inventory', 'rejected', inventory_notes='Correct receipt')
        returned_inventory._workflow_write(dict(resume_stage='inventory_purchase', purchasing_decision='cancelled'))
        deferred = self.claim()
        deferred.action_submit()
        deferred._workflow_write(dict(state='inventory_purchase', purchasing_decision='deferred',
                                      purchasing_notes='Waiting', purchasing_followup_date=fields.Date.today()))
        archived = cases[0][0]
        archived.write({'active': False})
        migration.migrate(self.env.cr, '19.0.2.0.0')
        for claim, expected, history in cases:
            self.assertEqual(claim.state, expected)
            self.assertTrue(set(history).issubset(claim.history_ids.ids))
            self.assertTrue(claim.history_ids.filtered(lambda h: h.to_state == 'inventory_purchase'))
        self.assertFalse(archived.active)
        self.assertEqual(returned_inventory.resume_stage, 'inventory')
        returned_inventory.action_submit()
        self.decide(returned_inventory, 'inventory')
        self.assertEqual(returned_inventory.state, 'purchasing')
        self.assertEqual(returned_inventory.purchasing_decision, 'pending')
        self.decide(deferred, 'inventory')
        self.assertEqual(deferred.state, 'purchasing')
        self.assertEqual(deferred.purchasing_decision, 'deferred')
        self.assertEqual(deferred.purchasing_notes, 'Waiting')
        self.assertEqual(deferred.purchasing_followup_date, fields.Date.today())
        self.assertEqual(returned.resume_stage, 'purchasing')
        returned.action_submit()
        self.assertEqual(returned.inventory_decision, 'approved')
        legacy = cases[2][0]
        self.decide(legacy, 'inventory')
        self.assertEqual(legacy.state, 'supplier_accounts')
        count = len(legacy.history_ids)
        migration.migrate(self.env.cr, '19.0.2.0.0')
        self.assertEqual(len(legacy.history_ids), count)
        invalid = self.claim()
        invalid.action_submit()
        invalid._workflow_write(dict(state='inventory_purchase', inventory_decision='rejected'))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            migration.migrate(self.env.cr, '19.0.2.0.0')
        self.assertEqual(invalid.state, 'inventory_purchase')
        invalid._workflow_write(dict(state='returned_secretarial', resume_stage='inventory_purchase',
                                     rejection_department='purchasing', purchasing_decision='rejected',
                                     inventory_decision='cancelled'))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            migration.migrate(self.env.cr, '19.0.2.0.0')
        self.assertEqual(invalid.resume_stage, 'inventory_purchase')

    def test_classification_defaults_and_first_submission(self):
        self.supplier.write({'tax_type': False, 'section': False})
        first = self.claim()
        self.assertFalse(first.tax_classification)
        self.assertFalse(first.section)
        first.write({'tax_classification': 'through_supplier', 'section': 'supplies'})
        # Drafts must not become other claims' defaults.
        self.assertFalse(self.claim().tax_classification)
        first.action_submit()
        later = self.claim()
        self.assertEqual((later.tax_classification, later.section), ('through_supplier', 'supplies'))
        later.write({'tax_classification': 'non_tax_payment', 'section': 'medical_preparations'})
        later.action_submit()
        third = self.claim()
        self.assertEqual((third.tax_classification, third.section), ('through_supplier', 'supplies'))
        self.assertFalse(self.supplier.tax_type)
        self.assertFalse(self.supplier.section)
        # Master data takes precedence per field, without replacing the fallback.
        self.supplier.write({'section': 'medical'})
        self.assertEqual(self.claim().section, 'medical')
        self.assertEqual(self.claim().tax_classification, 'through_supplier')
        self.supplier.write({'section': False})
        self.assertEqual(self.claim().section, 'supplies')

    def test_classification_empty_choices_and_independent_memory(self):
        claim = self.Claim.with_user(self.users['user']).create({
            **self.values(), 'tax_classification': False, 'section': False})
        claim.action_submit()
        self.assertFalse(claim.tax_classification)
        self.assertFalse(claim.section)
        self.supplier.write({'tax_type': False})
        first = self.claim()
        first.write({'section': 'imp_cosmo'})
        first.action_submit()
        self.assertFalse(self.claim().tax_classification)
        second = self.claim()
        second.write({'tax_classification': 'tax_payment'})
        second.action_submit()
        self.assertEqual(self.claim().tax_classification, 'tax_payment')
        self.assertEqual(self.claim().section, 'imp_cosmo')
        self.decide(second, 'inventory', 'rejected', inventory_notes='Correct invoice')
        with self.assertRaises(AccessError):
            second.write({'section': 'medical'})
        second.action_submit()
        self.assertEqual(second.section, 'imp_cosmo')

    def test_bracket_eligibility_snapshot_and_permissions(self):
        center = self.env['ab_costcenter'].with_context(install_mode=True).create({'name': 'Terms Test', 'code': 'SCC-TERMS'})
        other = self.env['ab_costcenter'].with_context(install_mode=True).create({'name': 'Other Terms', 'code': 'SCC-OTHER'})
        self.supplier.costcenter_id = center
        bracket = self.env['ab_supplier_bracket'].create({
            'supplier_id': center.id, 'payment_type': 'credit', 'start_day': 1,
            'termination_day': 10, 'credit_days': 30, 'discount': 2.5, 'withdrawal_bracket': 500})
        foreign = self.env['ab_supplier_bracket'].create({'supplier_id': other.id, 'credit_days': 90})
        claim = self.claim()
        with self.assertRaises(UserError), self.cr.savepoint():
            claim.write({'bracket_id': foreign.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            claim.with_user(self.users['admin']).write({'bracket_id': foreign.id})
        claim.write({'bracket_id': bracket.id})
        self.assertEqual(claim.bracket_credit_days, 30)
        self.assertIn('30', bracket.with_user(self.users['user']).display_name)
        with self.assertRaises(AccessError):
            bracket.with_user(self.users['user']).write({'discount': 99})
        with self.assertRaises(AccessError):
            claim.write({'bracket_snapshot': {'discount': 99}})
        claim.action_submit()
        self.assertEqual(claim.amount_of_check, '100')
        self.assertEqual(claim.state, 'inventory')
        bracket.write({'credit_days': 60, 'discount': 9})
        self.assertEqual(claim.bracket_credit_days, 30)
        self.assertEqual(claim.bracket_discount, 2.5)
        self.assertEqual(claim.bracket_snapshot['credit_days'], 30)
        self.assertFalse(claim.history_ids)
        with self.assertRaises(AccessError):
            claim.write({'bracket_id': False})
        draft = self.claim()
        draft.write({'bracket_id': bracket.id})
        draft.write({'supplier_id': self.cash.id})
        self.assertFalse(draft.bracket_id)
        self.assertFalse(draft.tax_classification)
        with self.assertRaises(UserError), self.cr.savepoint():
            draft.write({'bracket_id': bracket.id})
        # A bracket reassigned after draft creation is revalidated at submission.
        draft.write({'supplier_id': self.supplier.id})
        draft.write({'bracket_id': bracket.id})
        bracket.supplier_id = other
        with self.assertRaises(UserError), self.cr.savepoint():
            draft.action_submit()

    def test_defaults_model_and_form_access(self):
        self.supplier.tax_type = False
        claim = self.claim()
        claim.write({'tax_classification': 'non_tax_payment'})
        claim.action_submit()
        defaults = self.env['ab_supplier_claim_cycle.defaults'].search(
            fields.Domain('supplier_id', '=', self.supplier.id))
        self.assertEqual(defaults.tax_classification, 'non_tax_payment')
        for role in self.roles:
            Defaults = defaults.with_user(self.users[role])
            with self.assertRaises(AccessError):
                Defaults.write({'tax_classification': 'tax_payment'})
            with self.assertRaises(AccessError):
                Defaults.unlink()
            with self.assertRaises(AccessError):
                Defaults.create({'supplier_id': self.cash.id})
            if role != 'admin':
                with self.assertRaises(AccessError):
                    Defaults.read(['tax_classification'])
        view = self.env.ref('ab_supplier_claim_cycle.invoice_view_form')
        for role in self.roles:
            for lang in ('en_US', 'ar_001'):
                arch = etree.fromstring(self.Claim.with_user(self.users[role]).with_context(lang=lang).get_view(
                    view_id=view.id, view_type='form')['arch'])
                for name in ('tax_classification', 'section'):
                    node = arch.xpath('//field[@name="%s"]' % name)[0]
                    self.assertEqual(node.get('readonly'), "state != 'draft' or not active" if role in ('user', 'admin') else 'True')
                self.assertFalse(arch.xpath('//field[@name="business_category"]'))
                self.assertFalse(arch.xpath('//group[@name="payment_terms"] | //field[@name="bracket_id"]'))
        with Form(self.Claim.with_user(self.users['user'])) as form:
            form.supplier_id = self.supplier
            self.assertEqual(form.tax_classification, 'non_tax_payment')
            form.tax_classification = False
            form.section = 'medical_preparations'
            form.num_of_invoice = 1
            form.area = 'north'
            form.amount_of_check = '100'
            form.type_of_invoice = 'original'
        self.assertFalse(form.record.tax_classification)
        self.assertEqual(form.record.section, 'medical_preparations')

    def test_multi_create_defaults_and_multi_submit_first_choice(self):
        self.supplier.write({'tax_type': False, 'section': False})
        claims = self.Claim.with_user(self.users['user']).create([
            {**self.values(), 'tax_classification': 'through_supplier', 'section': 'supplies'},
            {**self.values(), 'tax_classification': 'tax_payment', 'section': 'medical'},
        ])
        claims.action_submit()
        defaults = self.env['ab_supplier_claim_cycle.defaults'].search(
            fields.Domain('supplier_id', '=', self.supplier.id))
        self.assertEqual(len(defaults), 1)
        self.assertEqual((defaults.tax_classification, defaults.section), ('through_supplier', 'supplies'))
        later = self.Claim.with_user(self.users['user']).create([self.values(), self.values(True)])
        self.assertEqual(later[0].tax_classification, 'through_supplier')
        self.assertFalse(later[1].tax_classification)

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
        # Existing audit rows remain stored, but no longer appear in Stage History.
        legacy = self.claim()
        legacy._log('created')
        legacy._log('submitted', 'draft')
        self.assertEqual(History.search_count(fields.Domain('claim_id', '=', legacy.id)), 2)
        self.assertFalse(legacy.history_ids)

    def test_secretarial_note_history_and_wizard_permissions(self):
        claim = self.claim()
        self.assertFalse(claim.history_ids)
        for role in self.roles:
            if role not in ('user', 'admin'):
                with self.assertRaises(AccessError):
                    claim.with_user(self.users[role]).action_open_secretarial_note()
                with self.assertRaises(AccessError):
                    claim.with_user(self.users[role]).action_add_secretarial_note('Unauthorized')
        with self.assertRaises(ValidationError):
            claim.action_add_secretarial_note('  ')
        action = claim.action_open_secretarial_note()
        Wizard = self.env[action['res_model']].with_user(self.users['user']).with_context(action['context'])
        with Form(Wizard) as form:
            form.note = 'Invoice documents checked'
        form.record.action_save()
        row = claim.history_ids
        self.assertEqual(len(row), 1)
        self.assertEqual((row.event, row.department, row.reason),
                         ('secretarial_note', 'secretarial', 'Invoice documents checked'))
        self.assertEqual(row.user_id, self.users['user'])
        self.assertEqual(claim.state, 'draft')
        self.assertTrue(row.occurred_at)
        pending_wizard = Wizard.create({'note': 'Stale dialog'})
        claim.action_submit()
        self.assertEqual(len(claim.history_ids), 1)
        with self.assertRaises(UserError):
            pending_wizard.action_save()
        with self.assertRaises(UserError):
            claim.with_user(self.users['admin']).action_add_secretarial_note('Wrong stage')
        self.decide(claim, 'inventory', 'rejected', inventory_notes='Correct documents')
        claim.action_add_secretarial_note('Documents corrected')
        self.assertEqual(len(claim.history_ids.filtered(lambda h: h.department == 'secretarial')), 2)
        with self.assertRaises(AccessError):
            row.write({'reason': 'Changed'})
        with self.assertRaises(AccessError):
            row.unlink()
        claim.write({'active': False})
        with self.assertRaises(UserError):
            claim.action_add_secretarial_note('Archived')
        closed = self.claim(True)
        closed.action_submit()
        self.decide(closed, 'supplier_accounts')
        closed.action_close()
        with self.assertRaises(UserError):
            closed.action_add_secretarial_note('Closed')

    def test_secretarial_note_api_and_form_visibility(self):
        claim = self.Claim.with_user(self.users['user']).create({**self.values(), 'secretarial_notes': 'First note'})
        self.assertEqual(claim.history_ids.reason, 'First note')
        claim.write({'secretarial_notes': 'Second note'})
        self.assertEqual(len(claim.history_ids), 2)
        claim.write({'secretarial_notes': 'Second note'})
        self.assertEqual(len(claim.history_ids), 2)
        claim.write({'secretarial_notes': False})
        self.assertEqual(len(claim.history_ids), 2)
        view = self.env.ref('ab_supplier_claim_cycle.invoice_view_form')
        for role in self.roles:
            for lang in ('en_US', 'ar_001'):
                arch = etree.fromstring(self.Claim.with_user(self.users[role]).with_context(lang=lang).get_view(
                    view_id=view.id, view_type='form')['arch'])
                self.assertFalse(arch.xpath('//group[@name="claim_notes"] | //field[@name="secretarial_notes"]'))
                buttons = arch.xpath('//button[@name="action_open_secretarial_note"]')
                self.assertEqual(bool(buttons), role in ('user', 'admin'))
                self.assertTrue(arch.xpath('//field[@name="history_ids"]/list/field[@name="reason"]'))

    def test_existing_secretarial_note_import_is_idempotent(self):
        import importlib.util
        from pathlib import Path
        path = Path(__file__).parents[1] / 'migrations/19.0.2.4.0/post-migrate.py'
        spec = importlib.util.spec_from_file_location('scc_note_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        claim = self.claim(True)
        claim._workflow_write({'secretarial_notes': 'Original user note'})
        claim.action_submit()
        self.decide(claim, 'supplier_accounts')
        claim.action_close()
        original_history = claim.history_ids
        sample_supplier = self.env['ab_supplier'].create({'name': 'Sample note test', 'code': 'SCCS26092706'})
        sample = self.Claim.with_user(self.users['user']).create({**self.values(), 'supplier_id': sample_supplier.id})
        sample._workflow_write({'secretarial_notes': '[SCC SAMPLE 20260927-06] Training only — draft; no payment or stock operation.'})
        migration.migrate(self.env.cr, '19.0.2.3.0')
        imported = claim.history_ids.filtered(lambda h: h.event == 'imported_secretarial_note')
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported.reason, 'Original user note')
        self.assertEqual(imported.department, 'secretarial')
        self.assertEqual(imported.to_state, 'closed')
        self.assertEqual(claim.state, 'closed')
        self.assertTrue(set(original_history.ids).issubset(claim.history_ids.ids))
        self.assertFalse(sample.history_ids)
        migration.migrate(self.env.cr, '19.0.2.3.0')
        self.assertEqual(claim.history_ids.filtered(lambda h: h.event == 'imported_secretarial_note'), imported)
