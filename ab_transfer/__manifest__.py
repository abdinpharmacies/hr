{
    'name': 'Abdin Transfer',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'application': True,
    'depends': ['base', 'ab_store', 'mail', 'web_domain_field', 'ab_product', 'ab_employee', 'ab_inventory'],
    'category': 'AbdinSupplyChain',
    'data': ['security/ir.model.access.csv',
             'views/transfer_line.xml',
             'views/transfer_header.xml',
             ],

    'installable': True,
}
