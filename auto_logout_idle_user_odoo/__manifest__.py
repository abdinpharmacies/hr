# Copyright (C) 2023-TODAY Cybrosys Technologies (https://www.cybrosys.com).
# Original author: Yadhukrishnan K. Odoo 19 adaptation: emadco88.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).
{
    'name': 'Logout Idle User',
    'version': '19.0.2.0.0',
    'summary': 'Log out inactive browser sessions using each user’s timeout',
    'author': 'Cybrosys Techno Solutions',
    'developer': 'emadco88',
    'license': 'AGPL-3',
    'depends': ['web'],
    'data': ['views/res_users_views.xml'],
    'assets': {'web.assets_backend': [
        'auto_logout_idle_user_odoo/static/src/timer.js',
        'auto_logout_idle_user_odoo/static/src/timer.xml',
    ]},
    'installable': True,
    'application': False,
}
