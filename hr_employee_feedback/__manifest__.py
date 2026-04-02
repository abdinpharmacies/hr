# -*- coding: utf-8 -*-
# Manifest for the Employee Feedback module.
# It declares metadata, dependencies, and XML/CSV files load order.
{
    'name': 'Employee Feedback - Complaints & Suggestions',
    'version': '19.0.1.0.38',
    'category': 'Human Resources',
    'summary': 'Trello-style employee feedback management',
    'description': """
        Employee Feedback Management Module
        ==================================
        - Submit complaints and suggestions
        - Trello-style Kanban workflow
        - Priority colors and quick actions
        - Employee self-service + Manager oversight
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': ['hr', 'mail', 'web'],
    'data': [
        # Groups/rules must load before access CSV because CSV references group XML IDs.
        'security/hr_employee_feedback_security.xml',
        'security/ir.model.access.csv',
        # Seed stages and sequence before loading views.
        'data/hr_employee_feedback_data.xml',
        'data/hr_employee_feedback_sequence.xml',
        'data/hr_employee_feedback_cron.xml',
        # UI components.
        'views/hr_employee_feedback_views.xml',
        'views/hr_employee_feedback_menus.xml',
        # Optional report scaffold.
        'report/hr_employee_feedback_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_employee_feedback/static/src/js/feedback_action_restrictions.js',
            'hr_employee_feedback/static/src/js/feedback_cog_menu_restrictions.js',
            'hr_employee_feedback/static/src/js/feedback_form_exit_guard.js',
            'hr_employee_feedback/static/src/scss/feedback_board.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}
