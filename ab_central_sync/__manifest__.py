{
    'name': 'Central Synchronization',
    'description': 'Durable central synchronization for native sales, returns and reversals.',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'Abdin Pharmacies',
    'developer': 'hossam elsheikh',
    'category': 'Sales',
    'depends': ['ab_sales', 'ab_sales_inventory', 'ab_inventory', 'ab_sales_contract', 'ab_sales_promo', 'ab_hr'],
    'external_dependencies': {'python': ['requests']},
    'data': ['security/security_groups.xml', 'security/ir.model.access.csv', 'security/record_rules.xml', 'views/operations.xml', 'data/cron.xml'],
    'installable': True,
}
