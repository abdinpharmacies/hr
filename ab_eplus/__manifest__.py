# -*- coding: utf-8 -*-

{
    'name': "ab_eplus link between odoo and BConnect",
    'category': 'Abdin',
    'version': '19.0.0.1',
    'license': 'LGPL-3',

    'depends': ['base', 'mail', 'ab_accounting', 'abdin_eplus', 'ab_hr', 'ab_hr_payroll', 'ab_costcenter', 'ab_eplus_connect'],

    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        # 'views/journal_entries_inherit.xml',
        'views/replicate_employees.xml',
        'views/delivery_points.xml',
    ],
}
