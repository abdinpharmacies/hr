# -*- coding: utf-8 -*-
{
    'name': 'HR Employee Permissions',
    'summary': 'Compatibility shim for legacy hr_employee_permissions database state.',
    'description': """
Legacy compatibility addon kept to satisfy databases where
`hr_employee_permissions` is still marked as installed.
    """,
    'license': 'LGPL-3',
    'author': 'Local Maintenance',
    'category': 'Human Resources',
    'version': '19.0.1.0.0',
    'depends': ['hr'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
