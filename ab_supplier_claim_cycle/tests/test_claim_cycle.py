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
        self.assertEqual(claim.state,'inventory_purchase')
        self.assertEqual(claim.payment_nature,'non_cash')

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

    def test_parallel_both_orders(self):
        for first,second in [('inventory','purchasing'),('purchasing','inventory')]:
            claim=self.claim(); claim.action_submit()
            self.assertEqual(claim.bank_accounts_decision, 'pending')
            self.decide(claim,first)
            self.assertEqual(claim.state,'inventory_purchase')
            self.decide(claim,second); self.assertEqual(claim.state,'supplier_accounts')
            with self.assertRaises(ValidationError):self.decide(claim,'supplier_accounts')
            self.assertEqual(claim.state,'supplier_accounts')
            self.decide(claim,'supplier_accounts',cheque_attachment=base64.b64encode(b'cheque'))
            self.assertEqual(claim.state,'bank_accounts')
            self.decide(claim,'bank_accounts'); self.assertEqual(claim.state,'ready_to_close')
            claim.action_close()

    def test_parallel_rejection_new_round(self):
        for rejecting,other in [('inventory','purchasing'),('purchasing','inventory')]:
            claim=self.claim(); claim.action_submit()
            with self.assertRaises(ValidationError):self.decide(claim,rejecting,'rejected')
            self.decide(claim,other,'deferred',**{other+'_notes':'Waiting',other+'_followup_date':fields.Date.today()})
            self.decide(claim,rejecting,'rejected',**{rejecting+'_notes':'Mismatch'})
            self.assertEqual(claim.state,'returned_secretarial')
            self.assertEqual(claim[other+'_decision'],'cancelled')
            claim.action_submit()
            self.assertEqual(claim.review_round,2)
            self.assertEqual((claim.inventory_decision,claim.purchasing_decision),('pending','pending'))
            self.assertTrue(claim.history_ids.filtered(lambda h:h.decision=='cancelled'))
            self.assertTrue(claim.history_ids.filtered(lambda h:h.reason=='Mismatch' and h.review_round==1))

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
            else:claim.action_submit()
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
        self.assertEqual(claim.with_user(self.users['reviewer']).state,'inventory_purchase')
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

    def test_parallel_rejection_after_approval_and_early_close(self):
        claim = self.claim()
        with self.assertRaises(UserError):
            claim.action_close()
        claim.action_submit()
        self.decide(claim, 'inventory')
        self.decide(claim, 'purchasing', 'rejected', purchasing_notes='Invoice mismatch')
        claim.action_submit()
        self.assertEqual(claim.inventory_decision, 'pending')
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
