{
    "name": 'HR Effects',
    'summary': """Effects Data like""",
    'license': 'LGPL-3',
    'category': 'Abdin',
    'version': '19.0.1.0.0',
    'depends': ['ab_hr', 'base', 'mail', 'abdin_et', 'ab_costcenter', 'ab_store'],

    'data': [
        'security/ir.model.access.csv',
        'security/record_rules_hr_basic_effect.xml',
        'security/record_rules_hr_effect.xml',
        'security/record_rules_hr_effect_wizard.xml',
        'data/ab_hr_effect_type.xml',
        'views/menus.xml',
        'views/ab_hr_employee_inherit.xml',
        'views/ab_hr_effect_type.xml',
        'views/ab_hr_effect.xml',
        'views/ab_hr_basic_effect.xml',
        'views/ab_hr_effect_wizard.xml'
    ],
    "application": True,
    "installable": True,
    "auto_install": True,

}
