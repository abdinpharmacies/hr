# -*- coding: utf-8 -*-
{
    'name': 'ab_odoo_replication_ctrl',
    'summary': 'Allow local writes on replicated databases while preserving write_date.',
    'description': """
        Enables local writes for models guarded by ab_odoo_replication.
    """,
    'author': 'abdinpharmacies',
    'website': 'https://www.abdinpharmacies.com',
    'license': 'LGPL-3',
    'category': 'Abdin',
    'version': '19.0.1.0.0',
    'depends': ['ab_odoo_replication'],
    'data': [
        'data/ir_config_parameter.xml',
    ],
    'installable': True,
    'application': False,
}
