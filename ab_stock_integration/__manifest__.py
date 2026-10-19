{
    'name': 'Abdin Stock Integration',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'application': False,
    'depends': ['ab_inventory', 'ab_product_source', 'ab_store', 'ab_taxes'],
    'data': ['security/record_rules.xml', 'security/ir.model.access.csv', 'views/integration.xml'],
    'installable': True,
    'auto_install': False,
}
