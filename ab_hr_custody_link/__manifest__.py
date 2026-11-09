{
    'name': 'HR Custody Link',
    'license': 'LGPL-3',
    'category': 'Abdin',
    'version': '19.0.0.1',
    'depends': ['ab_hr', 'ab_custody_request'],
    'data': [
        'security/ir.model.access.csv',
        'views/ab_hr_employee_custody.xml',
        'views/ab_custody_employee_data_inherit.xml',
    ],
    'installable': True,
}
