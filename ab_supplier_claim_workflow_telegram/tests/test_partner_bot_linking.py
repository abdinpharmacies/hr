from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestSupplierClaimTelegramPartnerLinking(TransactionCase):
    def setUp(self):
        super().setUp()
        seed = (self.env['ab_costcenter'].sudo().search([], order='id desc', limit=1).id or 0) + 2000000
        self.costcenter_a = self.env['ab_costcenter'].sudo().create({
            'name': 'Telegram Cost Center A',
            'code': 'TGA%s' % seed,
        })
        self.costcenter_b = self.env['ab_costcenter'].sudo().create({
            'name': 'Telegram Cost Center B',
            'code': 'TGB%s' % seed,
        })
        self.employee_a = self.env['ab_hr_employee'].sudo().create({
            'name': 'Telegram Employee A',
            'costcenter_id': self.costcenter_a.id,
        })
        self.employee_b = self.env['ab_hr_employee'].sudo().create({
            'name': 'Telegram Employee B',
            'costcenter_id': self.costcenter_b.id,
        })
        self.Account = self.env['ab_partner_bot'].sudo()
        self.Registration = self.env['ab_supplier_claim_telegram_registration'].sudo()

    def _create_account(self, costcenter, chat_id, linked_at, active=True, username=False):
        return self.Account.create({
            'costcenter_id': costcenter.id,
            'chat_id': chat_id,
            'telegram_username': username or chat_id,
            'linked_at': linked_at,
            'active': active,
        })

    def _refresh(self, registration):
        self.env.invalidate_all()
        return self.Registration.browse(registration.id)

    def test_registration_auto_links_to_matching_costcenter(self):
        registration = self.Registration.create({'employee_id': self.employee_a.id})
        self.assertFalse(registration.telegram_account_id)
        self.assertFalse(registration.telegram_connected)
        self.assertFalse(self.Account.search([('costcenter_id', '=', self.costcenter_a.id)]))

        account = self._create_account(
            self.costcenter_a,
            'tg-auto-link-1',
            fields.Datetime.subtract(fields.Datetime.now(), minutes=5),
        )
        registration = self._refresh(registration)

        self.assertEqual(registration.telegram_account_id, account)
        self.assertTrue(registration.telegram_connected)
        self.assertEqual(registration.telegram_chat_id, 'tg-auto-link-1')
        self.assertEqual(registration.telegram_username, 'tg-auto-link-1')
        self.assertEqual(registration.linked_at, account.linked_at)

    def test_newest_active_account_is_selected_with_deactivation_fallback(self):
        older = self._create_account(
            self.costcenter_a,
            'tg-auto-link-older',
            fields.Datetime.subtract(fields.Datetime.now(), hours=2),
        )
        newest = self._create_account(
            self.costcenter_a,
            'tg-auto-link-newest',
            fields.Datetime.subtract(fields.Datetime.now(), hours=1),
        )
        registration = self.Registration.create({'employee_id': self.employee_a.id})

        self.assertEqual(registration.telegram_account_id, newest)

        older.write({'linked_at': fields.Datetime.add(fields.Datetime.now(), hours=1)})
        registration = self._refresh(registration)
        self.assertEqual(registration.telegram_account_id, older)

        older.write({'active': False})
        registration = self._refresh(registration)
        self.assertEqual(registration.telegram_account_id, newest)

        newest.write({'active': False})
        registration = self._refresh(registration)
        self.assertFalse(registration.telegram_account_id)
        self.assertFalse(registration.telegram_connected)

    def test_newer_account_added_after_registration_becomes_selected(self):
        old_account = self._create_account(
            self.costcenter_a,
            'tg-auto-link-existing',
            fields.Datetime.subtract(fields.Datetime.now(), days=1),
        )
        registration = self.Registration.create({'employee_id': self.employee_a.id})
        self.assertEqual(registration.telegram_account_id, old_account)

        new_account = self._create_account(
            self.costcenter_a,
            'tg-auto-link-added',
            fields.Datetime.now(),
        )
        registration = self._refresh(registration)

        self.assertEqual(registration.telegram_account_id, new_account)

    def test_employee_change_recomputes_account_from_new_costcenter(self):
        account_a = self._create_account(self.costcenter_a, 'tg-employee-a', fields.Datetime.now())
        account_b = self._create_account(self.costcenter_b, 'tg-employee-b', fields.Datetime.now())
        registration = self.Registration.create({'employee_id': self.employee_a.id})
        self.assertEqual(registration.telegram_account_id, account_a)

        registration.write({'employee_id': self.employee_b.id})
        registration = self._refresh(registration)

        self.assertEqual(registration.telegram_account_id, account_b)
        self.assertNotEqual(registration.telegram_account_id, account_a)

    def test_duplicate_chat_id_is_rejected_globally(self):
        self._create_account(self.costcenter_a, 'tg-duplicate-chat', fields.Datetime.now())

        with self.assertRaises(ValidationError):
            self._create_account(self.costcenter_b, 'tg-duplicate-chat', fields.Datetime.now())

    def test_generic_costcenter_recipient_resolution_is_consistent(self):
        account = self._create_account(self.costcenter_a, 'tg-generic-routing', fields.Datetime.now())
        supplier = self.env['ab_supplier'].sudo().create({
            'name': 'Telegram Supplier',
            'code': 'TG-SUP-%s' % self.costcenter_a.id,
            'costcenter_id': self.costcenter_a.id,
        })
        recipients = [self.employee_a, supplier]
        Customer = self.env.get('ab_customer')
        if Customer:
            recipients.append(Customer.sudo().create({
                'name': 'Telegram Customer',
                'code': 'TG-CUS-%s' % self.costcenter_a.id,
                'costcenter_id': self.costcenter_a.id,
            }))

        for recipient in recipients:
            self.assertEqual(self.Account.get_account_for_record(recipient), account)
            self.assertEqual(self.Account.get_chat_id_for_record(recipient), 'tg-generic-routing')

        self.assertFalse(self.Account.get_chat_id_for_record(self.employee_b))

    def test_register_from_telegram_creates_partner_bot_account(self):
        result = self.Registration.register_from_telegram(
            self.employee_a.accid,
            'tg-register-flow',
            username='register_flow',
        )
        registration = self.Registration.browse(result.get('id'))

        self.assertTrue(result.get('success'))
        self.assertEqual(registration.employee_id, self.employee_a)
        self.assertEqual(registration.telegram_account_id.costcenter_id, self.costcenter_a)
        self.assertEqual(registration.telegram_chat_id, 'tg-register-flow')
        self.assertEqual(registration.telegram_username, 'register_flow')
