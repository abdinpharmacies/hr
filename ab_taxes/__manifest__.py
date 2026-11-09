{
    'version': '19.0.1.0.0',
    'name': 'ab_taxes',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'depends': ['base', 'web_progress'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/ab_taxes.xml',
        # 'views/purchase_tax_invoices.xml',
        # 'views/cron_taxes_supplier_invoices.xml',
        # 'wizard/download_tax_invoices_pdf.xml',
        'data/taxes.xml',
    ]

}
