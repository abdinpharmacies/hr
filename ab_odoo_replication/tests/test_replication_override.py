import datetime
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.addons.ab_odoo_connect import OdooConnectionSingleton
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import SQL, config


class TestReplicationOverride(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Override = cls.env['ab_odoo_replication_override'].sudo()
        cls.WriteRule = cls.env['ab_odoo_replication_override_write_rule'].sudo()
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

    def _field(self, model_name, field_name):
        field = self.env['ir.model.fields'].sudo().search([
            ('model', '=', model_name),
            ('name', '=', field_name),
        ], limit=1)
        self.assertTrue(field, f'Missing field {model_name}.{field_name}')
        return field

    def _add_write_rule(self, policy, group, *field_names):
        return self.WriteRule.create({
            'override_id': policy.id,
            'group_id': group.id,
            'field_ids': [Command.set([
                self._field(policy.model_name, field_name).id
                for field_name in field_names
            ])],
        })

    def _new_group(self, suffix):
        return self.env['res.groups'].sudo().create({
            'name': f'Replication Override {suffix}',
        })

    def test_default_policy_blocks_crud_without_implicit_admin_bypass(self):
        self._create_partner_policy()

        with self.assertRaisesRegex(AccessError, 'create'):
            self.env['res.partner'].with_user(self.regular_user).create({
                'name': 'Blocked Partner',
            })
        with self.assertRaises(AccessError):
            self.partner_a.with_user(self.regular_user).write({'name': 'Blocked'})
        with self.assertRaisesRegex(AccessError, 'delete'):
            self.partner_a.with_user(self.regular_user).unlink()
        with self.assertRaises(AccessError):
            self.partner_a.with_user(self.admin_user).write({'name': 'Admin Blocked'})

    def test_allowed_groups_bypass_guard(self):
        policy = self._create_partner_policy(
            allowed_create_group_ids=[Command.set(self.group_user.ids)],
        )
        self._add_write_rule(policy, self.group_user, 'name')

        created = self.env['res.partner'].with_user(self.regular_user).create({
            'name': 'Allowed Partner',
        })
        self.partner_a.with_user(self.regular_user).write({'name': 'Allowed Write'})

        self.assertTrue(created)
        self.assertEqual(self.partner_a.name, 'Allowed Write')

    def test_allowed_group_does_not_grant_normal_model_access(self):
        policy = self._create_partner_policy(
            allowed_create_group_ids=[Command.set(self.group_portal.ids)],
        )
        self._add_write_rule(policy, self.group_portal, 'name')

        with self.assertRaises(AccessError):
            self.partner_a.with_user(self.portal_user).write({'name': 'No ACL'})
        with self.assertRaises(AccessError):
            self.env['res.partner'].with_user(self.portal_user).create({
                'name': 'No Create ACL',
            })

    def test_replication_context_requires_sudo(self):
        self._create_partner_policy()

        with self.assertRaises(AccessError):
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
            with self.assertRaises(AccessError):
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
        with self.assertRaises(ValidationError):
            self.Override.create({'model_name': 'ab_odoo_replication_override_write_rule'})

    def test_field_rule_rejects_mixed_write_atomically(self):
        policy = self._create_partner_policy()
        self._add_write_rule(policy, self.group_user, 'name')
        original_name = self.partner_a.name
        original_city = self.partner_a.city

        with self.assertRaisesRegex(AccessError, 'city'):
            self.partner_a.with_user(self.regular_user).write({
                'name': 'Should Roll Back',
                'city': 'Denied City',
            })

        self.assertEqual(self.partner_a.name, original_name)
        self.assertEqual(self.partner_a.city, original_city)

    def test_multiple_write_groups_combine_fields_by_union(self):
        name_group = self._new_group('Name Group')
        city_group = self._new_group('City Group')
        self.regular_user.sudo().write({
            'group_ids': [Command.link(name_group.id), Command.link(city_group.id)],
        })
        policy = self._create_partner_policy()
        self._add_write_rule(policy, name_group, 'name')
        self._add_write_rule(policy, city_group, 'city')

        self.partner_a.with_user(self.regular_user).write({
            'name': 'Union Name',
            'city': 'Union City',
        })

        self.assertEqual(self.partner_a.name, 'Union Name')
        self.assertEqual(self.partner_a.city, 'Union City')

    def test_write_rule_changes_invalidate_cached_fields(self):
        policy = self._create_partner_policy()
        rule = self._add_write_rule(policy, self.group_user, 'name')
        self.partner_a.with_user(self.regular_user).write({'name': 'Initially Allowed'})

        rule.write({'field_ids': [Command.set([self._field('res.partner', 'city').id])]})

        with self.assertRaisesRegex(AccessError, 'name'):
            self.partner_a.with_user(self.regular_user).write({'name': 'Now Denied'})
        self.partner_a.with_user(self.regular_user).write({'city': 'Now Allowed'})
        self.assertEqual(self.partner_a.city, 'Now Allowed')

    def test_write_rule_validates_fields_and_parent_model(self):
        policy = self._create_partner_policy()
        groups = [self._new_group(str(index)) for index in range(4)]
        invalid_field_sets = [
            [],
            [self._field('res.users', 'login').id],
            [self._field('res.partner', 'write_date').id],
            [self._field('res.partner', 'display_name').id],
        ]

        for group, field_ids in zip(groups, invalid_field_sets):
            with self.assertRaises(ValidationError):
                self.WriteRule.create({
                    'override_id': policy.id,
                    'group_id': group.id,
                    'field_ids': [Command.set(field_ids)],
                })

        rule = self._add_write_rule(policy, self.group_user, 'name')
        self.assertEqual(rule.editable_fields, 'name')
        with self.assertRaisesRegex(ValidationError, 'Remove the writable-field rules'):
            policy.write({'model_name': 'res.users'})

    def test_missing_policy_tables_bypass_guard_during_bootstrap(self):
        policy = self._create_partner_policy()
        self._add_write_rule(policy, self.group_user, 'name')
        self.env.registry.clear_cache()
        try:
            with patch(
                'odoo.addons.ab_odoo_replication.models.'
                'ab_odoo_replication_override.sql.table_exists',
                return_value=False,
            ):
                self.partner_a.with_user(self.regular_user).write({
                    'city': 'Bootstrap Allowed',
                })
        finally:
            self.env.registry.clear_cache()

        self.assertEqual(self.partner_a.city, 'Bootstrap Allowed')

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

        policy = self._create_partner_policy()
        with self.assertRaises(AccessError):
            self.env['ab_odoo_replication_override_write_rule'].with_user(
                self.regular_user,
            ).create({
                'override_id': policy.id,
                'group_id': self.group_user.id,
                'field_ids': [Command.set([self._field('res.partner', 'name').id])],
            })

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


class TestReplicationSourceCompatibility(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Replication = self.env['ab_odoo_replication']
        share = self.Replication.ReplShare
        self.previous_share = {
            'model_name': share.model_name,
            'source_major_version': share.source_major_version,
            'conn': share.conn,
        }

    def tearDown(self):
        for field_name, value in self.previous_share.items():
            setattr(self.Replication.ReplShare, field_name, value)
        super().tearDown()

    def test_odoo_15_chatter_positions_are_mapped_to_odoo_19_values(self):
        self.Replication.ReplShare.model_name = 'res.users'
        self.Replication.ReplShare.source_major_version = 15

        for source_value, expected_value in (
            ('normal', 'bottom'),
            ('sided', 'side'),
        ):
            source_record = {
                'id': 10,
                'chatter_position': source_value,
                'name': 'Mapped User',
            }
            normalized_record = self.Replication._normalize_remote_record(
                source_record,
            )

            self.assertEqual(
                normalized_record['chatter_position'],
                expected_value,
            )
            self.assertEqual(source_record['chatter_position'], source_value)
            self.assertEqual(normalized_record['name'], source_record['name'])

    def test_chatter_position_mapping_is_limited_to_odoo_15_users(self):
        source_record = {'id': 10, 'chatter_position': 'normal'}

        self.Replication.ReplShare.model_name = 'res.users'
        self.Replication.ReplShare.source_major_version = 19
        self.assertIs(
            self.Replication._normalize_remote_record(source_record),
            source_record,
        )

        self.Replication.ReplShare.model_name = 'res.partner'
        self.Replication.ReplShare.source_major_version = 15
        self.assertIs(
            self.Replication._normalize_remote_record(source_record),
            source_record,
        )

    def test_unknown_odoo_15_chatter_position_is_not_silently_changed(self):
        self.Replication.ReplShare.model_name = 'res.users'
        self.Replication.ReplShare.source_major_version = 15
        source_record = {'id': 10, 'chatter_position': 'unexpected'}

        self.assertIs(
            self.Replication._normalize_remote_record(source_record),
            source_record,
        )

    def test_source_major_version_uses_structured_and_string_metadata(self):
        conn = self.Replication.ReplShare.conn = MagicMock()

        conn.get_server_version_info.return_value = {
            'server_version_info': [15, 0, 0, 'final', 0],
        }
        self.assertEqual(self.Replication._get_source_major_version(), 15)

        conn.get_server_version_info.return_value = {
            'server_version': '19.0+e',
        }
        self.assertEqual(self.Replication._get_source_major_version(), 19)

    def test_invalid_source_version_metadata_raises_clear_error(self):
        conn = self.Replication.ReplShare.conn = MagicMock()
        conn.get_server_version_info.return_value = {}

        with self.assertRaisesRegex(UserError, 'major version'):
            self.Replication._get_source_major_version()

    def test_connection_server_version_is_cached(self):
        connection = object.__new__(OdooConnectionSingleton)
        connection._srv = 'https://odoo-source.example.com'
        connection._headers = [('x-sync-key', 'test')]
        connection._server_version_info = None
        version_metadata = {
            'server_version': '15.0',
            'server_version_info': [15, 0, 0, 'final', 0],
        }

        with patch(
            'odoo.addons.ab_odoo_connect.ab_odoo_connect.client.ServerProxy',
        ) as server_proxy:
            server_proxy.return_value.version.return_value = version_metadata

            first_result = connection.get_server_version_info()
            second_result = connection.get_server_version_info()

        self.assertEqual(first_result, version_metadata)
        self.assertIs(second_result, first_result)
        server_proxy.assert_called_once_with(
            'https://odoo-source.example.com/xmlrpc/2/common',
            headers=[('x-sync-key', 'test')],
        )
        server_proxy.return_value.version.assert_called_once_with()

    def test_connection_server_version_failure_raises_clear_error(self):
        connection = object.__new__(OdooConnectionSingleton)
        connection._srv = 'https://odoo-source.example.com'
        connection._headers = []
        connection._server_version_info = None

        with patch(
            'odoo.addons.ab_odoo_connect.ab_odoo_connect.client.ServerProxy',
        ) as server_proxy:
            server_proxy.return_value.version.side_effect = RuntimeError('offline')
            with self.assertRaisesRegex(UserError, 'remote Odoo server version'):
                connection.get_server_version_info()


class TestForceIdReplication(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Replication = cls.env['ab_odoo_replication']
        cls.Partner = cls.env['res.partner'].sudo().with_context(active_test=False)

    def _configure_partner_replication(self):
        share = self.Replication.ReplShare
        previous = {
            'model_name': share.model_name,
            'table_name': share.table_name,
            'has_main_rec_id': share.has_main_rec_id,
            'missing_many2one_flds': share.missing_many2one_flds,
            'fld__type_rel_dict': share.fld__type_rel_dict,
            'source_major_version': share.source_major_version,
        }
        share.model_name = 'res.partner'
        share.table_name = 'res_partner'
        share.has_main_rec_id = False
        share.missing_many2one_flds = []
        share.fld__type_rel_dict = {
            'id': ('integer', None),
            'name': ('char', None),
            'city': ('char', None),
            'active': ('boolean', None),
        }
        share.source_major_version = None
        return previous

    def _restore_replication_share(self, previous):
        for field_name, value in previous.items():
            setattr(self.Replication.ReplShare, field_name, value)

    def test_refresh_force_id_record_discards_cached_values(self):
        partner = self.Partner.create({'name': 'Before forced SQL update'})
        self.assertEqual(partner.name, 'Before forced SQL update')

        self.env.cr.execute(SQL(
            'UPDATE res_partner SET name = %s WHERE id = %s',
            'After forced SQL update',
            partner.id,
        ))
        refreshed = self.Replication._refresh_force_id_record(
            self.Partner,
            partner.id,
            changed_fields=['name'],
        )

        self.assertEqual(refreshed.name, 'After forced SQL update')

    def test_partner_insert_uses_sql_without_orm_write_replay(self):
        self.env.cr.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM res_partner')
        forced_id = self.env.cr.fetchone()[0]
        previous = self._configure_partner_replication()
        try:
            with patch.object(
                type(self.Partner),
                'write',
                autospec=True,
            ) as write:
                change = self.Replication._replicate_main_fields({
                    'id': forced_id,
                    'name': 'Forced ID Partner',
                    'active': True,
                })
                operation, local_id, values, replay_write, changed_values = change
                self.Replication._finalize_force_id_batch(self.Partner, {
                    'create': {
                        local_id: {
                            'values': values,
                            'replay_write': replay_write,
                            'changed_values': changed_values,
                        },
                    },
                    'write': {},
                })

            self.assertEqual(operation, 'create')
            self.assertEqual(local_id, forced_id)
            self.assertFalse(replay_write)
            self.assertFalse(changed_values)
            self.assertEqual(self.Partner.browse(forced_id).name, 'Forced ID Partner')
            write.assert_not_called()
        finally:
            self._restore_replication_share(previous)

    def test_replay_values_exclude_orm_managed_fields(self):
        replay_values = self.Replication._get_force_id_replay_values(
            self.Partner,
            {
                'id': 999,
                'name': 'Replay Name',
                'create_date': '2025-01-01 00:00:00',
                'write_date': '2025-01-02 00:00:00',
                'display_name': 'Computed Name',
                'child_ids': [],
            },
        )

        self.assertEqual(replay_values, {'name': 'Replay Name'})

    def test_partner_update_uses_sql_without_orm_write(self):
        partner = self.Partner.create({'name': 'Before replication'})
        previous = self._configure_partner_replication()
        try:
            with patch.object(type(partner), 'write', autospec=True) as write:
                operation, local_id, values, replay_write, changed_values = (
                    self.Replication._replicate_main_fields({
                        'name': 'After replication',
                        'id': partner.id,
                    })
                )
                self.Replication._finalize_force_id_batch(self.Partner, {
                    'create': {},
                    'write': {
                        local_id: {
                            'values': values,
                            'replay_write': replay_write,
                            'changed_values': changed_values,
                        },
                    },
                })

            self.assertEqual(operation, 'write')
            self.assertEqual(local_id, partner.id)
            self.assertFalse(replay_write)
            self.assertFalse(changed_values)
            self.assertEqual(partner.name, 'After replication')
            write.assert_not_called()
        finally:
            self._restore_replication_share(previous)

    def test_exact_copy_identical_update_skips_orm_write_values(self):
        partner = self.Partner.create({'name': 'Unchanged replication'})
        previous = self._configure_partner_replication()
        try:
            with patch.object(type(partner), 'write', autospec=True) as write:
                operation, local_id, values, replay_write, changed_values = (
                    self.Replication._replicate_main_fields({
                        'id': partner.id,
                        'name': partner.name,
                        'active': partner.active,
                    })
                )

            self.assertEqual(operation, 'write')
            self.assertEqual(local_id, partner.id)
            self.assertFalse(replay_write)
            self.assertFalse(changed_values)
            self.assertEqual(values['name'], partner.name)
            write.assert_not_called()
        finally:
            self._restore_replication_share(previous)

    def test_partner_sql_update_accepts_id_in_any_dictionary_position(self):
        partner = self.Partner.create({
            'name': 'Partially changed replication',
            'city': 'Cairo',
        })
        previous = self._configure_partner_replication()
        try:
            operation, local_id, values, replay_write, changed_values = (
                self.Replication._replicate_main_fields({
                    'id': partner.id,
                    'name': partner.name,
                    'city': 'Giza',
                })
            )

            self.assertEqual(operation, 'write')
            self.assertEqual(local_id, partner.id)
            self.assertFalse(replay_write)
            self.assertFalse(changed_values)
            self.assertEqual(values['name'], partner.name)
            self.assertEqual(partner.city, 'Giza')
        finally:
            self._restore_replication_share(previous)

    def test_users_update_uses_sql_without_orm_write(self):
        user = self.env['res.users'].sudo().with_context(
            no_reset_password=True,
        ).create({
            'name': 'SQL-only Replication User',
            'login': 'sql-only-replication-user-before',
        })
        share = self.Replication.ReplShare
        previous = {
            'model_name': share.model_name,
            'table_name': share.table_name,
            'has_main_rec_id': share.has_main_rec_id,
            'missing_many2one_flds': share.missing_many2one_flds,
            'fld__type_rel_dict': share.fld__type_rel_dict,
            'source_major_version': share.source_major_version,
        }
        share.model_name = 'res.users'
        share.table_name = 'res_users'
        share.has_main_rec_id = False
        share.missing_many2one_flds = []
        share.fld__type_rel_dict = {
            'id': ('integer', None),
            'login': ('char', None),
        }
        share.source_major_version = None
        try:
            with patch.object(type(user), 'write', autospec=True) as write:
                change = self.Replication._replicate_main_fields({
                    'id': user.id,
                    'login': 'sql-only-replication-user-after',
                })
                operation, local_id, values, replay_write, changed_values = change
                self.Replication._finalize_force_id_batch(
                    self.env['res.users'].sudo(),
                    {
                        'create': {},
                        'write': {
                            local_id: {
                                'values': values,
                                'replay_write': replay_write,
                                'changed_values': changed_values,
                            },
                        },
                    },
                )

            self.assertEqual(operation, 'write')
            self.assertFalse(replay_write)
            self.assertFalse(changed_values)
            self.assertEqual(user.login, 'sql-only-replication-user-after')
            write.assert_not_called()
        finally:
            self._restore_replication_share(previous)

    def test_partner_deferred_many2one_uses_sql_without_orm_write(self):
        parent = self.Partner.create({'name': 'Replication Parent'})
        child = self.Partner.create({'name': 'Replication Child'})
        previous = self._configure_partner_replication()
        self.Replication.ReplShare.missing_many2one_flds = [
            ('res.partner', 'parent_id', parent.id, child.id),
        ]
        try:
            with patch.object(type(child), 'write', autospec=True) as write:
                deferred_changes = self.Replication._replicate_missing_many2one()

            self.assertFalse(deferred_changes)
            self.assertEqual(child.parent_id, parent)
            write.assert_not_called()
        finally:
            self._restore_replication_share(previous)

    def test_other_models_retain_orm_update_behavior(self):
        category = self.env['res.partner.category'].sudo().create({
            'name': 'Before ORM Replication',
        })
        share = self.Replication.ReplShare
        previous = {
            'model_name': share.model_name,
            'table_name': share.table_name,
            'has_main_rec_id': share.has_main_rec_id,
            'missing_many2one_flds': share.missing_many2one_flds,
            'fld__type_rel_dict': share.fld__type_rel_dict,
            'source_major_version': share.source_major_version,
        }
        share.model_name = 'res.partner.category'
        share.table_name = 'res_partner_category'
        share.has_main_rec_id = False
        share.missing_many2one_flds = []
        share.fld__type_rel_dict = {
            'id': ('integer', None),
            'name': ('char', None),
        }
        share.source_major_version = None
        try:
            with patch.object(type(category), 'write', autospec=True) as write:
                operation, local_id, values, replay_write, changed_values = (
                    self.Replication._replicate_main_fields({
                        'id': category.id,
                        'name': 'After ORM Replication',
                    })
                )

            self.assertEqual(operation, 'write')
            self.assertEqual(local_id, category.id)
            self.assertFalse(replay_write)
            self.assertEqual(values['name'], 'After ORM Replication')
            self.assertEqual(changed_values, {'name': 'After ORM Replication'})
            write.assert_called_once()
        finally:
            self._restore_replication_share(previous)
