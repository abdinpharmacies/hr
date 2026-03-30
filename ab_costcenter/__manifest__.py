# -*- coding: utf-8 -*-
{
    'name': "Abdin Cost Centers",
    'author': "emadco88",
    'website': "https://www.abdinpharmacies.com",
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'version': '19.0.1.0.0',
    'application': False,
    'depends': ['base', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/costcenter.xml',
    ],
    'installable': True,
}
