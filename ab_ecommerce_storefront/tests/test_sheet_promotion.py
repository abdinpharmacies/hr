from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestSheetPromotion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref('website.default_website')
        cls.company = cls.website.company_id
        cls.partner = cls.env['res.partner'].create({'name': 'Promotion buyer'})
        cls.products = cls.env['product.product'].create([
            {'name': name, 'list_price': price, 'taxes_id': [Command.clear()]}
            for name, price in [('Sheet A', 300), ('Sheet B', 200), ('Sheet C', 50)]
        ])
        cls.egp = cls.env.ref('base.EGP')
        cls.egp.active = True
        cls.pricelist = cls.env['product.pricelist'].create({
            'name': 'Sheet prices', 'website_id': cls.website.id,
            'company_id': cls.company.id, 'currency_id': cls.egp.id,
        })

    def promotion(self, name, products, group=1, rate=100, **values):
        model = self.env['loyalty.program']
        if 'pos_ok' in model._fields:
            values['pos_ok'] = False
        return model.create({
            'name': name, 'ab_sheet_key': name, 'program_type': 'promotion',
            'website_id': self.website.id, 'company_id': self.company.id,
            'trigger': 'auto', 'applies_on': 'current', 'sale_ok': False, 'ecommerce_ok': True,
            'ab_sheet_group_qty': group, 'rule_ids': [Command.create({
                'minimum_qty': group, 'reward_point_amount': 1,
                'reward_point_mode': 'order', 'product_ids': [Command.set(products.ids)],
                'minimum_amount': 0,
            })],
            'reward_ids': [Command.create({
                'discount': rate, 'discount_mode': 'percent', 'discount_applicability': 'cheapest',
                'discount_product_ids': [Command.set(products.ids)], 'required_points': 1,
            })], **values,
        })

    def cart(self, quantities):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id, 'website_id': self.website.id,
            'company_id': self.company.id, 'pricelist_id': self.pricelist.id,
            'order_line': [Command.create({
                'product_id': product.id, 'price_unit': price, 'product_uom_qty': qty,
            }) for product, qty, price in zip(self.products, quantities, (300, 200, 50)) if qty],
        })

    def apply_promotions(self, order):
        order._update_programs_and_rewards()
        order._auto_apply_rewards()

    def test_manual_sheet_offer_shares_cart_rules_and_employee_list(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        self.website.warehouse_id = warehouse
        products = self.products[:2]
        products.write({'is_storable': True})
        for product in products:
            self.env['stock.quant'].with_context(inventory_mode=True).create({
                'product_id': product.id, 'location_id': warehouse.lot_stock_id.id,
                'inventory_quantity': 5,
            }).action_apply_inventory()
        offer = self.env['ab_storefront_offer'].create({
            'name': 'Two eligible items', 'offer_type': 'sheet', 'website_id': self.website.id,
            'product_id': products[0].id, 'second_product_ids': [Command.set(products[1:].ids)],
            'sheet_group_qty': 2, 'sheet_discount_qty': 2, 'sheet_rate': 30,
        })
        program = offer.generated_program_ids
        cart = self.cart([1, 1, 0])
        self.apply_promotions(cart)
        self.assertEqual(cart.amount_total, 350)
        offer.sheet_fixed_price = 125
        second_cart = self.cart([1, 1, 0])
        self.apply_promotions(second_cart)
        self.assertEqual(second_cart.amount_total, 250)
        self.assertEqual(offer.generated_program_ids, program)
        imported = self.promotion('Imported group', self.products[2:])
        self.env.flush_all()
        staff = new_test_user(self.env, login='group_offer_staff',
                              groups='ab_ecommerce_storefront.group_call_center')
        overview = self.env['ab_storefront_offer_overview'].with_user(staff)
        rows = overview.search([('name', 'in', [offer.name, imported.name])])
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows.mapped('source')), {'manual', 'sheet'})
        self.assertEqual(rows.filtered(lambda r: r.source == 'manual').action_open_offer()['res_id'], offer.id)
        with self.assertRaises(AccessError):
            rows.write({'state': 'archived'})
        with self.assertRaises(AccessError):
            overview.with_user(self.env.ref('base.public_user')).search([])
        offer.active = False
        self.assertFalse(program.active)

    def test_cheapest_eligible_repeats_and_recalculates(self):
        self.promotion('Second half', self.products[:2], group=2, rate=50)
        order = self.cart([2, 2, 1])
        self.apply_promotions(order)
        self.assertEqual(order.amount_total, 850)
        order.order_line.filtered(lambda line: line.product_id == self.products[1]).product_uom_qty = 1
        self.apply_promotions(order)
        self.assertEqual(order.amount_total, 750)

    def test_overlap_choices_and_separate_discount(self):
        monthly = self.promotion('Monthly', self.products, rate=30)
        weekend = self.promotion('Weekend', self.products[:2], group=2, rate=100)
        order = self.cart([1, 1, 1])
        self.apply_promotions(order)
        self.assertEqual(order.amount_total, 335)
        self.assertEqual(order.order_line.reward_id.program_id, monthly | weekend)
        monthly.ab_sheet_priority = 1
        self.apply_promotions(order)
        self.assertEqual(order.amount_total, 385)
        self.assertEqual(order.order_line.reward_id.program_id, monthly)
        monthly.ab_sheet_priority = 0
        self.apply_promotions(order)
        self.assertEqual(order.amount_total, 335)

    def test_unpaired_unit_keeps_its_own_discount(self):
        self.promotion('Monthly', self.products, rate=30)
        self.promotion('Second free', self.products, group=2, rate=100)
        order = self.cart([3])
        self.apply_promotions(order)
        self.assertEqual(order.amount_total, 510)

    def test_fixed_price_includes_percentage_tax(self):
        country = self.company.account_fiscal_country_id or self.env.ref('base.eg')
        group = self.env['account.tax.group'].create({
            'name': 'Sheet VAT', 'company_id': self.company.id, 'country_id': country.id,
        })
        tax = self.env['account.tax'].create({
            'tax_group_id': group.id, 'country_id': country.id, 'name': 'Sheet VAT', 'amount': 10, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': self.company.id,
            'price_include_override': 'tax_excluded',
        })
        self.promotion('Taxed final price', self.products[:1], ab_sheet_fixed_price=220)
        order = self.cart([1])
        order.order_line.tax_ids = [Command.set(tax.ids)]
        self.apply_promotions(order)
        self.assertAlmostEqual(order.amount_total, 220, places=2)

    def test_fixed_price_never_increases_price(self):
        program = self.promotion('Final price', self.products, ab_sheet_fixed_price=190)
        order = self.cart([2, 1, 1])
        self.apply_promotions(order)
        self.assertEqual(order.amount_total, 620)
        self.assertEqual(order.order_line.reward_id.program_id, program)

    def test_native_rule_restrictions(self):
        regular = self.promotion('Regular', self.products, rate=10)
        special = self.promotion('Eligible selection', self.products, rate=50)
        special.rule_ids.product_domain = repr([('id', '=', self.products[1].id)])
        special.rule_ids.minimum_amount = 1000000
        order = self.cart([1, 1])
        self.apply_promotions(order)
        self.assertEqual(order.order_line.reward_id.program_id, regular)
        self.assertEqual(order.amount_total, 450)
        special.rule_ids.minimum_amount = 0
        self.apply_promotions(order)
        self.assertEqual(order.amount_total, 370)
        with self.assertRaises(ValidationError):
            special.reward_ids.write({'discount_applicability': 'order'})

    def test_duplicate_keeps_storefront_pricing(self):
        program = self.promotion('Original', self.products, ab_sheet_fixed_price=80)
        duplicate = program.copy()
        self.assertTrue(duplicate.ab_sheet_key)
        self.assertNotEqual(duplicate.ab_sheet_key, program.ab_sheet_key)
        self.assertEqual(duplicate.ab_sheet_fixed_price, 80)
        self.assertFalse(duplicate.sale_ok)
        if 'pos_ok' in program._fields:
            with self.assertRaises(ValidationError):
                program.pos_ok = True
            self.assertFalse(duplicate.pos_ok)

    def test_other_site_and_salesperson(self):
        program = self.promotion('Only this website', self.products)
        user = new_test_user(self.env, login='sheet_salesperson', groups='sales_team.group_sale_salesman')
        with self.assertRaises(AccessError):
            program.with_user(user).write({'ab_sheet_priority': 2})
        order = self.cart([1, 1, 1])
        order.website_id = False
        self.apply_promotions(order)
        self.assertFalse(order.order_line.reward_id.program_id)
        self.assertEqual(order.amount_total, 550)
