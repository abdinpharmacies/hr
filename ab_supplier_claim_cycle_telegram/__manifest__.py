{
    'name': 'Supplier Claim Cycle Telegram Notifications',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_supplier_claim_cycle', 'ab_telegram_bot', 'ab_hr', 'queue_job'],
    'data': ['data/queue_job_data.xml', 'data/parameters.xml'],
    'installable': True,
}
