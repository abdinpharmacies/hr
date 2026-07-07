from odoo import Command
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError, AccessError


@tagged('core_ui')
class TestCoreUICategory(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Category = self.env['core_ui.category']
        self.Component = self.env['core_ui.component']

    def test_category_creation(self):
        category = self.Category.create({
            'name': 'Test Dialogs',
            'sequence': 10,
            'description': 'Dialog components',
            'icon': 'fa-window-maximize',
        })
        self.assertEqual(category.name, 'Test Dialogs')
        self.assertEqual(category.sequence, 10)
        self.assertEqual(category.icon, 'fa-window-maximize')
        self.assertEqual(category.component_count, 0)
        self.assertFalse(category.has_children)

    def test_category_unique_name(self):
        name = 'test_unique_%d' % self.Category.search([], order='id desc', limit=1).id
        self.Category.create({'name': name})
        with self.assertRaises(Exception):
            self.Category.create({'name': name})

    def test_category_parent_hierarchy(self):
        parent = self.Category.create({'name': 'Test Inputs'})
        child = self.Category.create({
            'name': 'Text Inputs',
            'parent_id': parent.id,
        })
        self.assertTrue(parent.has_children)
        self.assertEqual(len(parent.child_ids), 1)
        self.assertEqual(parent.child_ids[0], child)
        self.assertEqual(child.parent_id, parent)

    def test_category_computed_component_count(self):
        category = self.Category.create({'name': 'Test Cards'})
        self.assertEqual(category.component_count, 0)
        self.Component.create({
            'component_id': 'core_ui.card.standard',
            'name': 'Standard Card',
            'category_id': category.id,
        })
        self.Component.create({
            'component_id': 'core_ui.card.stat',
            'name': 'Stat Card',
            'category_id': category.id,
        })
        category._invalidate_cache(['component_count'])
        self.assertEqual(category.component_count, 2)

    def test_category_order_by_sequence(self):
        c1 = self.Category.create({'name': 'Test Z', 'sequence': 30})
        c2 = self.Category.create({'name': 'Test A', 'sequence': 10})
        c3 = self.Category.create({'name': 'Test M', 'sequence': 20})
        categories = self.Category.search([('id', 'in', [c1.id, c2.id, c3.id])])
        self.assertEqual(categories[0], c2)
        self.assertEqual(categories[1], c3)
        self.assertEqual(categories[2], c1)

    def test_category_subcategory_count(self):
        parent = self.Category.create({'name': 'Test Parent'})
        self.Category.create({'name': 'Test Child 1', 'parent_id': parent.id})
        self.Category.create({'name': 'Test Child 2', 'parent_id': parent.id})
        parent._invalidate_cache(['has_children', 'component_count'])
        self.assertTrue(parent.has_children)
        self.assertEqual(parent.component_count, 0)


@tagged('core_ui')
class TestCoreUIComponent(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Category = self.env['core_ui.category']
        self.Component = self.env['core_ui.component']
        self.category = self.Category.create({'name': 'Test Category'})

    def test_component_creation(self):
        component = self.Component.create({
            'component_id': 'core_ui.test.dialog',
            'name': 'Test Dialog',
            'category_id': self.category.id,
            'version': '1.0.0',
            'status': 'stable',
            'author': 'Test',
            'tags': 'dialog,modal',
            'keywords': 'alert,confirm,prompt',
        })
        self.assertEqual(component.component_id, 'core_ui.test.dialog')
        self.assertEqual(component.name, 'Test Dialog')
        self.assertEqual(component.version, '1.0.0')
        self.assertEqual(component.status, 'stable')
        self.assertEqual(component.author, 'Test')
        self.assertEqual(component.usage_count, 0)
        self.assertFalse(component.is_favorite)

    def test_component_unique_component_id(self):
        cid = 'core_ui.unique.%d' % self.Component.search([], order='id desc', limit=1).id
        self.Component.create({
            'component_id': cid,
            'name': 'First',
            'category_id': self.category.id,
        })
        with self.assertRaises(Exception):
            self.Component.create({
                'component_id': cid,
                'name': 'Duplicate',
                'category_id': self.category.id,
            })

    def test_component_toggle_favorite(self):
        component = self.Component.create({
            'component_id': 'core_ui.test.fav',
            'name': 'Favorite Test',
            'category_id': self.category.id,
        })
        user = self.env.ref('base.user_admin')
        self.assertFalse(component.favorite_ids)
        component.favorite_ids = [(4, user.id)]
        self.assertTrue(component.favorite_ids)
        self.assertIn(user, component.favorite_ids)
        component.favorite_ids = [(3, user.id)]
        self.assertFalse(component.favorite_ids)

    def test_component_increment_usage(self):
        component = self.Component.create({
            'component_id': 'core_ui.test.usage',
            'name': 'Usage Test',
            'category_id': self.category.id,
        })
        self.assertEqual(component.usage_count, 0)
        component.action_increment_usage()
        self.assertEqual(component.usage_count, 1)
        component.action_increment_usage()
        self.assertEqual(component.usage_count, 2)

    def test_component_defaults(self):
        component = self.Component.create({
            'component_id': 'core_ui.test.defaults',
            'name': 'Defaults',
            'category_id': self.category.id,
        })
        self.assertEqual(component.status, 'stable')
        self.assertEqual(component.version, '1.0.0')
        self.assertTrue(component.active)
        self.assertTrue(component.has_dark_mode)
        self.assertTrue(component.has_light_mode)

    def test_component_category_relation(self):
        component = self.Component.create({
            'component_id': 'core_ui.test.catrel',
            'name': 'Category Relation',
            'category_id': self.category.id,
        })
        self.assertEqual(component.category_id, self.category)
        self.assertIn(component, self.category.component_ids)

    def test_component_deactivate(self):
        component = self.Component.create({
            'component_id': 'core_ui.test.deactivate',
            'name': 'Deactivate',
            'category_id': self.category.id,
        })
        self.assertTrue(component.active)
        component.active = False
        self.assertFalse(component.active)


@tagged('core_ui')
class TestCoreUIDesignToken(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Token = self.env['core_ui.design_token']
        self.TokenCategory = self.env['core_ui.token_category']

    def test_token_creation(self):
        token = self.Token.create({
            'name': 'Primary Color',
            'token_name': '--core-ui-color-primary',
            'value': '#2563eb',
            'type': 'color',
        })
        self.assertEqual(token.token_name, '--core-ui-color-primary')
        self.assertEqual(token.value, '#2563eb')
        self.assertEqual(token.type, 'color')
        self.assertTrue(token.active)

    def test_token_categorization(self):
        cat = self.TokenCategory.create({
            'name': 'Colors',
            'icon': 'fa-palette',
        })
        token = self.Token.create({
            'name': 'Secondary',
            'token_name': '--core-ui-secondary',
            'value': '#64748b',
            'category_id': cat.id,
        })
        self.assertEqual(token.category_id, cat)
        self.assertIn(token, cat.token_ids)


@tagged('core_ui')
class TestCoreUIPattern(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Category = self.env['core_ui.category']
        self.Component = self.env['core_ui.component']
        self.Pattern = self.env['core_ui.pattern']
        self.category = self.Category.create({'name': 'Patterns'})

    def test_pattern_creation(self):
        pattern = self.Pattern.create({
            'name': 'Empty State',
            'pattern_id': 'pattern.empty_state',
            'category_id': self.category.id,
            'description': 'Show when no data exists',
            'steps': '1. Check data\n2. Show illustration\n3. Provide CTA',
        })
        self.assertEqual(pattern.name, 'Empty State')
        self.assertEqual(pattern.pattern_id, 'pattern.empty_state')
        self.assertTrue(pattern.active)

    def test_pattern_component_relation(self):
        comp1 = self.Component.create({
            'component_id': 'core_ui.test.empty_state',
            'name': 'Test Empty State',
            'category_id': self.category.id,
        })
        comp2 = self.Component.create({
            'component_id': 'core_ui.test.btn',
            'name': 'Test Button',
            'category_id': self.category.id,
        })
        pattern = self.Pattern.create({
            'name': 'Empty State Pattern',
            'pattern_id': 'pattern.empty_state.v2',
            'category_id': self.category.id,
            'component_ids': [(6, 0, [comp1.id, comp2.id])],
        })
        self.assertIn(comp1, pattern.component_ids)
        self.assertIn(comp2, pattern.component_ids)

    def test_pattern_inactive(self):
        pattern = self.Pattern.create({
            'name': 'Deprecated Pattern',
            'pattern_id': 'pattern.old',
            'category_id': self.category.id,
            'active': False,
        })
        self.assertFalse(pattern.active)


@tagged('core_ui')
class TestCoreUISettings(TransactionCase):

    def test_action_launch_workspace(self):
        action = self.env['res.config.settings'].action_launch_workspace()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'core_ui.workspace')
        self.assertEqual(action['target'], 'new')

    def test_action_open_component_gallery(self):
        action = self.env['res.config.settings'].action_open_component_gallery()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'core_ui.gallery')
        self.assertEqual(action['target'], 'new')


@tagged('core_ui')
class TestCoreUIGroupPermissions(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Category = self.env['core_ui.category']
        self.user_group = self.env.ref('ab_core_ui.group_core_ui_user')
        self.dev_group = self.env.ref('ab_core_ui.group_core_ui_developer')
        self.manager_group = self.env.ref('ab_core_ui.group_core_ui_manager')

        Users = self.env['res.users'].with_context(no_reset_password=True)
        self.user = Users.create({
            'name': 'Test User',
            'login': 'test_core_ui_user',
        })
        self.user.write({'group_ids': [Command.link(self.user_group.id)]})
        self.developer = Users.create({
            'name': 'Test Developer',
            'login': 'test_core_ui_dev',
        })
        self.developer.write({'group_ids': [Command.link(self.dev_group.id)]})
        self.manager = Users.create({
            'name': 'Test Manager',
            'login': 'test_core_ui_mgr',
        })
        self.manager.write({'group_ids': [Command.link(self.manager_group.id)]})

    def test_user_read_only(self):
        cats = self.Category.with_user(self.user).search([])
        self.assertTrue(len(cats) >= 0)
        with self.assertRaises(AccessError):
            self.Category.with_user(self.user).create({'name': 'User Cant Create'})

    def test_developer_full_access(self):
        cat = self.Category.with_user(self.developer).create({'name': 'Dev Cat'})
        self.assertEqual(cat.name, 'Dev Cat')
        cat.with_user(self.developer).write({'description': 'Updated'})
        self.assertEqual(cat.description, 'Updated')
        cat.with_user(self.developer).unlink()

    def test_manager_full_access(self):
        cat = self.Category.with_user(self.manager).create({'name': 'Mgr Cat'})
        self.assertEqual(cat.name, 'Mgr Cat')
        cat.with_user(self.manager).write({'description': 'Updated by mgr'})
        self.assertEqual(cat.description, 'Updated by mgr')
        cat.with_user(self.manager).unlink()

    def test_user_cannot_write(self):
        admin_cat = self.Category.create({'name': 'Admin Cat'})
        with self.assertRaises(AccessError):
            admin_cat.with_user(self.user).write({'description': 'Should fail'})

    def test_user_cannot_delete(self):
        cat = self.Category.create({'name': 'Will not be deleted'})
        with self.assertRaises(AccessError):
            cat.with_user(self.user).unlink()

    def test_implied_group_inheritance(self):
        self.assertTrue(
            self.developer.has_group('ab_core_ui.group_core_ui_user'),
            "Developer should inherit User group",
        )
        self.assertTrue(
            self.manager.has_group('ab_core_ui.group_core_ui_user'),
            "Manager should inherit User group",
        )
        self.assertTrue(
            self.manager.has_group('ab_core_ui.group_core_ui_developer'),
            "Manager should inherit Developer group",
        )

    def test_user_does_not_have_higher_groups(self):
        self.assertFalse(
            self.user.has_group('ab_core_ui.group_core_ui_developer'),
        )
        self.assertFalse(
            self.user.has_group('ab_core_ui.group_core_ui_manager'),
        )
        self.assertFalse(
            self.developer.has_group('ab_core_ui.group_core_ui_manager'),
        )
