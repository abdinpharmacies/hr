{
    'name': "Accounting",

    'summary': """
        Accounting Module
        """,

    'description': """
        This module have entries table and double entries on validation,
        after validation you can edit only specific fields like branch or costcenter.
    """,

    'author': "emadco88",
    'website': "http://www.abdinpharmacies.com",
    'license': 'LGPL-3',
    'category': 'Accounting',
    'version': '0.1',
    'application': True,
    'depends': ['base', 'ab_base_models_inherit', 'mail', 'abdin_et', 'ab_costcenter',
                'report_xlsx', 'ab_store',
                'ab_data_from_excel', 'web_domain_field'],
    'data': [
        'security/security_groups.xml',
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'data/allowed_fields.xml',
        'data/doctype.xml',
        'data/account_guide.xml',
        'views/z_menus.xml',
        'views/ab_accounting_account_levels.xml',
        'views/account_guide.xml',
        'views/doctype.xml',
        'views/user_auth.xml',
        'views/account_auth.xml',
        'views/ab_accounting_auth_group.xml',
        'views/journal_entries.xml',
        'views/journal_entries_one2many.xml',
        'views/account_header.xml',
        'views/journal_entries_qry.xml',
        'views/ab_due_salaries_wizard.xml',
        'views/ab_costcenter_deduction_forbidden.xml',
        'views/ab_costcenter_deduction_month_prevented.xml',
        'report_wizard/templates/template_account_statement.xml',
        'report_wizard/templates/pdf_account_statement.xml',
        'report_wizard/templates/xlsx_account_statement.xml',
        'report_wizard/templates/template_due_salaries_details.xml',
        'report_wizard/account_statement_view.xml',
    ],
}
# -*- coding: utf-8 -*-
