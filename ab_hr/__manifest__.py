# -*- coding: utf-8 -*-
{
    'name': "Abdin hr",

    'summary': """Abdin HR employee and organization data""",

    'description': """
        Long description of module's purpose
    """,
    'license': 'LGPL-3',

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Abdin',
    'version': '19.0.1.1.0',
    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'abdin_et', 'mail', 'abdin_telegram', 'ab_costcenter',
                'ab_store', 'report_xlsx'],

    # always loaded
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/00_menus.xml',
        'views/ab_hr_job_occupied.xml',
        'views/job_wizard.xml',
        'views/history.xml',
        'views/ab_hr_job.xml',
        'views/history_report.xml',
        'views/hris.xml',
        'views/history_action_type.xml',
        'views/manpower.xml',
        'views/ab_hr_employee.xml',
        'views/ab_hr_department.xml',
        'views/res_users_inherit.xml',
        'static/templates/template_termination_feedback.xml',
        'static/templates/xlsx_termination_feedback.xml',
        'views/report_wizard.xml',
        'views/report_model.xml',
    ],
    "application": True,
    "installable": True,
    "auto_install": True,

    'assets': {
        'web.assets_backend': [
            'ab_hr/static/src/scss/hr.scss',
            'ab_hr/static/src/js/employee_views.js',
        ],
    },
}
