# -*- coding: utf-8 -*-
{
    'name': "ab_odoo_replication",

    'summary': """
    ab_odoo_replication
""",

    'description': """
                   ab_odoo_replication    """,

    'author': "abdinpharmacies",
    'website': "https://www.abdinpharmacies.com",

    'license': 'LGPL-3',
    'category': 'Abdin',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'ab_hr', 'ab_product', 'ab_customer',
                'ab_announcement', 'mail', 'ab_promo_program',
                'integration_queue_job'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        # 'data/queue_job_record.xml',
        'views/cron_ab_odoo_replication.xml',
        'views/ab_odoo_replication.xml',
    ],
    # only loaded in demonstration mode
    'installable': True,
}
