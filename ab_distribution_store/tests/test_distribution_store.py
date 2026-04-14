from odoo.tests.common import TransactionCase


class TestDistributionStore(TransactionCase):
    def setUp(self):
        super().setUp()
        Product = self.env['ab_distribution_store_product']
        Inventory = self.env['ab_distribution_store_inventory']
        Header = self.env['ab_distribution_store_header']
        self.product = Product.create({'name': 'Test Product'})
        self.inventory = Inventory.create({
            'product_id': self.product.id,
            'balance': 10.0,
            'customer_price': 5.0,
        })
        self.header = Header.create({'customer_name': 'Test Customer'})

    def test_inventory_balance_updates(self):
        Line = self.env['ab_distribution_store_line']
        line = Line.create({
            'header_id': self.header.id,
            'inventory_id': self.inventory.id,
            'qty': 3.0,
        })
        self.inventory.invalidate_cache(['balance'])
        self.assertEqual(self.inventory.balance, 7.0)

        line.write({'qty': 5.0})
        self.inventory.invalidate_cache(['balance'])
        self.assertEqual(self.inventory.balance, 5.0)

        line.unlink()
        self.inventory.invalidate_cache(['balance'])
        self.assertEqual(self.inventory.balance, 10.0)
