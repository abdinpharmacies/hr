{
    'name': 'Ab Distribution Store',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base'],
    'category': 'AbdinSupplyChain',
    'data': [
        'security/ir.model.access.csv',
        'views/distribution_product.xml',
        'views/distribution_inventory.xml',
        'views/distribution_header.xml',
        'views/menus.xml',
        'report/distribution_store_report.xml',
    ],
    'installable': True,
}
