{
    'name': 'Legacy Migration Compatibility',
    'version': '19.0.1.1.0',
    'author': 'Abdin Pharmacies',
    'developer': 'emadco88',
    'license': 'LGPL-3',
    'depends': ['base', 'ab_accounting_base', 'ab_inventory', 'ab_accounting_tracking', 'ab_hr'],
    'data': ['security/private_contacts.xml', 'security/legacy_hr.xml', 'views/ir_attachment.xml', 'views/legacy_references.xml'],
    'installable': True,
    'application': False,
}
