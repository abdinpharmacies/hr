import datetime

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import SQL, config


class TestReplicationOverride(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Override = cls.env['ab_odoo_replication_override'].sudo()
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_portal = cls.env.ref('base.group_portal')
        cls.regular_user = cls.env['res.users'].sudo().with_context(
            no_reset_password=True,
        ).create({
            'name': 'Replication Override Test User',
            'login': 'replication_override_test_user',
            'email': 'replication-override-test@example.com',
            'group_ids': [Command.set(cls.group_user.ids)],
        })
        cls.portal_user = cls.env['res.users'].sudo().with_context(
            no_reset_password=True,
        ).create({
            'name': 'Replication Override Portal User',
            'login': 'replication_override_portal_user',
            'email': 'replication-override-portal@example.com',
            'group_ids': [Command.set(cls.group_portal.ids)],
        })
        partner_model = cls.env['ir.model']._get('res.partner')
        cls.env['ir.model.access'].sudo().create({
            'name': 'replication.override.test.partner.access',
            'model_id': partner_model.id,
            'group_id': cls.group_user.id,
            'perm_read': True,
            'perm_write': True,
            'perm_create': True,
            'perm_unlink': True,
        })
        cls.admin_user = cls.env.ref('base.user_admin')
        cls.partner_a = cls.env['res.partner'].sudo().create({
            'name': 'Replication Override Partner A',
        })
        cls.partner_b = cls.env['res.partner'].sudo().create({
            'name': 'Replication Override Partner B',
        })

    def _create_partner_policy(self, **values):
        return self.Override.create({
            'model_name': 'res.partner',
            **values,
        })

    def test_default_policy_blocks_crud_without_implicit_admin_bypass(self):
        self._create_partner_policy()

        with self.assertRaisesRegex(AccessError, 'create'):
            self.env['res.partner'].with_user(self.regular_user).create({
                'name': 'Blocked Partner',
            })
        with self.assertRaisesRegex(AccessError, 'write'):
            self.partner_a.with_user(self.regular_user).write({'name': 'Blocked'})
        with self.assertRaisesRegex(AccessError, 'delete'):
            self.partner_a.with_user(self.regular_user).unlink()
        with self.assertRaisesRegex(AccessError, 'write'):
            self.partner_a.with_user(self.admin_user).write({'name': 'Admin Blocked'})

    def test_allowed_groups_bypass_guard(self):
        self._create_partner_policy(
            allowed_write_group_ids=[Command.set(self.group_user.ids)],
            allowed_create_group_ids=[Command.set(self.group_user.ids)],
        )

        created = self.env['res.partner'].with_user(self.regular_user).create({
            'name': 'Allowed Partner',
        })
        self.partner_a.with_user(self.regular_user).write({'name': 'Allowed Write'})

        self.assertTrue(created)
        self.assertEqual(self.partner_a.name, 'Allowed Write')

    def test_allowed_group_does_not_grant_normal_model_access(self):
        self._create_partner_policy(
            allowed_write_group_ids=[Command.set(self.group_portal.ids)],
            allowed_create_group_ids=[Command.set(self.group_portal.ids)],
        )

        with self.assertRaises(AccessError):
            self.partner_a.with_user(self.portal_user).write({'name': 'No ACL'})
        with self.assertRaises(AccessError):
            self.env['res.partner'].with_user(self.portal_user).create({
                'name': 'No Create ACL',
            })

    def test_replication_context_requires_sudo(self):
        self._create_partner_policy()

        with self.assertRaisesRegex(AccessError, 'write'):
            self.partner_a.with_user(self.regular_user).with_context(
                replication=True,
            ).write({'name': 'Spoofed Replication'})

        self.partner_a.with_context(replication=True).sudo().write({
            'name': 'Trusted Replication',
        })
        self.assertEqual(self.partner_a.name, 'Trusted Replication')

    def test_replication_write_preserves_write_date_for_multi_recordsets(self):
        self._create_partner_policy()
        original_a = datetime.datetime(2000, 1, 1, 10, 0, 0)
        original_b = datetime.datetime(2001, 2, 2, 11, 0, 0)
        self.env.cr.execute(SQL(
            'UPDATE res_partner SET write_date = CASE '
            'WHEN id = %s THEN %s ELSE %s END WHERE id IN %s',
            self.partner_a.id,
            original_a,
            original_b,
            tuple((self.partner_a | self.partner_b).ids),
        ))
        partners = self.partner_a | self.partner_b
        partners.invalidate_recordset(['write_date'])

        partners.with_context(replication=True).sudo().write({'city': 'Cairo'})
        partners.invalidate_recordset(['write_date', 'city'])

        self.assertEqual(self.partner_a.write_date, original_a)
        self.assertEqual(self.partner_b.write_date, original_b)
        self.assertEqual(set(partners.mapped('city')), {'Cairo'})

    def test_replication_create_and_unlink_require_explicit_flags(self):
        policy = self._create_partner_policy()
        Partner = self.env['res.partner'].with_context(replication=True).sudo()

        with self.assertRaisesRegex(AccessError, 'create'):
            Partner.create({'name': 'Blocked Replication Create'})

        policy.write({
            'allow_replication_create': True,
            'allow_replication_unlink': True,
        })
        created = Partner.create({'name': 'Allowed Replication Create'})
        self.assertTrue(created)
        created.unlink()
        self.assertFalse(created.exists())

    def test_control_server_bypass_is_per_policy(self):
        policy = self._create_partner_policy()
        original_value = config.get('is_control_server', False)
        config['is_control_server'] = True
        try:
            with self.assertRaisesRegex(AccessError, 'write'):
                self.partner_a.with_user(self.regular_user).write({'city': 'Blocked'})

            policy.write({'control_server_bypass': True})
            self.partner_a.with_user(self.regular_user).write({'city': 'Allowed'})
            self.assertEqual(self.partner_a.city, 'Allowed')
        finally:
            config['is_control_server'] = original_value

    def test_archived_policy_and_install_mode_bypass_guard(self):
        policy = self._create_partner_policy()
        self.partner_a.with_user(self.regular_user).with_context(
            install_mode=True,
        ).write({'city': 'Install Mode'})

        policy.write({'active': False})
        self.partner_a.with_user(self.regular_user).write({'city': 'Archived Policy'})
        self.assertEqual(self.partner_a.city, 'Archived Policy')

    def test_model_name_validation_and_availability(self):
        policy = self._create_partner_policy()
        self.assertTrue(policy.model_available)

        missing_policy = self.Override.create({'model_name': 'x_missing_replication_model'})
        self.assertFalse(missing_policy.model_available)

        with self.assertRaises(ValidationError):
            self.Override.create({'model_name': 'Invalid Model Name'})
        with self.assertRaises(ValidationError):
            self.Override.create({'model_name': 'ab_odoo_replication_override'})

    def test_seeded_compatibility_policies(self):
        expected_models = {
            'ab_costcenter',
            'ab_store',
            'ab_hr_region',
            'ab_hr_job',
            'ab_hr_department',
            'ab_hr_employee',
            'ab_product_company',
            'ab_product_origin',
            'ab_product_group',
            'ab_usage_causes',
            'ab_usage_manner',
            'ab_product_card',
            'ab_uom_type',
            'ab_uom',
            'ab_product',
            'ab_promo_program',
        }
        policies = self.Override.search([('model_name', 'in', sorted(expected_models))])
        self.assertEqual(set(policies.mapped('model_name')), expected_models)
        self.assertTrue(all(policies.mapped('disable_write')))
        self.assertTrue(all(policies.mapped('disable_create')))
        self.assertTrue(all(policies.mapped('disable_unlink')))
        self.assertTrue(all(policies.mapped('ignore_write_date')))

        promo = policies.filtered(lambda policy: policy.model_name == 'ab_promo_program')
        self.assertTrue(promo.control_server_bypass)
        self.assertTrue(promo.allow_replication_create)
        self.assertTrue(promo.allow_replication_unlink)

    def test_non_admin_cannot_manage_policies(self):
        with self.assertRaises(AccessError):
            self.env['ab_odoo_replication_override'].with_user(
                self.regular_user,
            ).create({'model_name': 'x_forbidden_override'})

    def test_missing_local_model_is_skipped(self):
        with self.assertLogs(
            'odoo.addons.ab_odoo_replication.models.ab_odoo_replication',
            level='WARNING',
        ) as logs:
            result = self.env['ab_odoo_replication'].replicate_model(
                'x_missing_replication_model',
            )

        self.assertIsNone(result)
        self.assertIn('Skipping replication for unavailable local model', logs.output[0])
