# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestProductFieldManagement(TransactionCase):
    def setUp(self):
        super().setUp()
        self.group_user = self.env.ref('base.group_user')
        self.price_group = self.env.ref('ab_product.group_ab_product_price_manager')
        self.price_user = self.env['res.users'].sudo().create({
            'name': 'Product Price Manager Test',
            'login': 'product_price_manager_test',
            'email': 'product_price_manager_test@example.com',
            'group_ids': [(6, 0, [self.group_user.id, self.price_group.id])],
        })
        card = self.env['ab_product_card'].sudo().create({
            'name': 'FIELD ACCESS PRODUCT',
            'is_medicine': False,
        })
        self.product = self.env['ab_product'].sudo().create({
            'product_card_id': card.id,
            'code': 'FIELD-ACCESS-001',
            'is_priced': False,
            'location': 'A-01',
        })

    def _product_field(self, name):
        field = self.env['ir.model.fields'].sudo().search([
            ('model', '=', 'ab_product'),
            ('name', '=', name),
        ], limit=1)
        self.assertTrue(field, 'Missing ab_product field %s' % name)
        return field

    def _create_rule(self, *field_names):
        return self.env['ab_product_management_field_rule'].sudo().create({
            'group_id': self.price_group.id,
            'field_ids': [(6, 0, [self._product_field(name).id for name in field_names])],
        })

    def _managed_access(self):
        Rule = self.env['ab_product_management_field_rule'].sudo()
        return self.env['ir.model.access'].sudo().search([
            ('name', '=', Rule._managed_access_name(self.price_group.id)),
            ('model_id.model', '=', 'ab_product'),
            ('group_id', '=', self.price_group.id),
        ])

    def test_rule_generates_and_removes_product_write_acl(self):
        rule = self._create_rule('is_priced')

        access = self._managed_access()
        self.assertTrue(access)
        self.assertTrue(access.perm_read)
        self.assertTrue(access.perm_write)
        self.assertFalse(access.perm_create)
        self.assertFalse(access.perm_unlink)

        rule.unlink()

        self.assertFalse(self._managed_access())

    def test_group_can_write_configured_product_field(self):
        self._create_rule('is_priced')

        self.product.with_user(self.price_user).write({'is_priced': True})

        self.assertTrue(self.product.is_priced)

    def test_group_cannot_write_unconfigured_product_field(self):
        self._create_rule('is_priced')

        with self.assertRaises(AccessError):
            self.product.with_user(self.price_user).write({'location': 'B-02'})

    def test_invalid_fields_cannot_be_selected(self):
        Rule = self.env['ab_product_management_field_rule'].sudo()
        with self.assertRaises(ValidationError):
            Rule.create({
                'group_id': self.price_group.id,
                'field_ids': [(6, 0, [self._product_field('create_uid').id])],
            })
        with self.assertRaises(ValidationError):
            Rule.create({
                'group_id': self.price_group.id,
                'field_ids': [(6, 0, [self._product_field('product_search').id])],
            })

    def test_non_system_user_cannot_manage_rules(self):
        with self.assertRaises(AccessError):
            self.env['ab_product_management_field_rule'].with_user(self.price_user).create({
                'group_id': self.price_group.id,
                'field_ids': [(6, 0, [self._product_field('is_priced').id])],
            })
