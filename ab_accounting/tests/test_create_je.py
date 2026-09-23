import datetime

from odoo.tests.common import TransactionCase, tagged
from odoo.tests import new_test_user
from odoo.exceptions import UserError, ValidationError


@tagged('post_install')
class TestJournalEntries(TransactionCase):
    def setUp(self, *args, **kw):
        print('testing is running ....')
        super(TestJournalEntries, self).setUp(*args, **kw)

    def test_post_negative_balance(self):
        self.accountant = new_test_user(self.env,
                                        login='accountant',
                                        groups='base.group_user,ab_accounting.group_ab_accounting_accountant',
                                        lang='en_US'
                                        )
        print(f"user created with id {self.accountant.id}")

        self.account_header = self.env['ab_accounting_je_header'].with_user(self.accountant).create({
            'account_id': self.env.ref('ab_accounting.ab_accounting_account_guide_due_salaries').id,
            'doctype_id': 7,
        })
        store_id = self.env['ab_store'].search([('code', '=', '6')]).id
        costcenter_id1 = self.env['ab_costcenter'].search([('code', '=', '1')]).id
        costcenter_id2 = self.env['ab_costcenter'].search([('code', '=', '164')]).id

        header_je = {
            'due_date': datetime.date(2023, 1, 1),
            'explain': 'testing explain...',
            'store_id': store_id,
            'account_id': 267,
            'costcenter_id': costcenter_id1,
            'debit_val': 0,
            'credit_val': 500000,
        }

        balancer_je = {
            'due_date': datetime.date(2023, 1, 1),
            'explain': 'testing explain...',
            'store_id': store_id,
            'account_id': 267,
            'costcenter_id': costcenter_id2,
            'debit_val': 500000,
            'credit_val': 0,
        }

        self.account_header.with_user(self.accountant).write({
            "line_ids": [(0, 0, header_je), (0, 0, balancer_je)]
        })

        with self.assertRaises(UserError), self.cr.savepoint():
            self.account_header.with_user(self.accountant).btn_post_je()

    def test_access_prevented_accounts(self):
        self.accountant = new_test_user(self.env,
                                        login='accountant',
                                        groups='base.group_user,ab_accounting.group_ab_accounting_accountant',
                                        lang='en_US'
                                        )
        print(f"user created with id {self.accountant.id}")
        prevented_account_id = self.env['ab_accounting_je_line_qry'] \
            .search([], limit=1).account_id.id
        allowed_account_id = self.env['ab_accounting_je_line_qry'] \
            .search([('account_id', '!=', prevented_account_id)], limit=1).account_id.id

        self.accountant.write({'account_auth_ids': [
            (0, 0, {'account_id': prevented_account_id,
                    'prevent_enquiry': True,
                    })
        ]
        })
        je = self.env['ab_accounting_je_line_qry'] \
            .with_user(self.accountant).search([('account_id', '=', prevented_account_id)])
        self.assertEqual(bool(je), False, 'There is records here')
        je = self.env['ab_accounting_je_line_qry'] \
            .with_user(self.accountant).search([('account_id', '=', allowed_account_id)])
        self.assertEqual(bool(je), True, 'There is not records here')
