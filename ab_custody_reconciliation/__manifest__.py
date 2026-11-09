# -*- coding: utf-8 -*-
{
    'version': '19.0.1.0.0',
    'name': 'Custody Reconciliation',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_custody_request', 'abdin_telegram'],
    'data': [
        'data/custody_channel.xml',
        'data/template_custody_reconciliation_email.xml',
        'security/security_groups.xml',
        'security/record_rules_approval.xml',
        'security/record_rules_reconciliation.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_custody_reconciliation_header.xml',
        'views/ab_reconciliation_employee_approval.xml',
        'views/ab_custody_reconciliation_line.xml',
        'views/ab_custody_reconciliation_wizard.xml',
        'report_wizard/template_custody_settlement.xml',
        'views/ab_accounting_je_header_inherit.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

}
