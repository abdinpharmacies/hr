{
    "name": "ab_odoo_sync",
    "summary": "Event-driven one-way sync from MAIN to BRANCH Odoo servers",
    "description": "Append-only event log synchronization between MAIN and BRANCH servers.",
    "author": "abdinpharmacies",
    "website": "https://www.abdinpharmacies.com",
    "license": "LGPL-3",
    "category": "Tools",
    "version": "19.0.1.0.0",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/ab_odoo_sync_cron.xml",
        "views/ab_odoo_sync_views.xml",
    ],
    "installable": True,
    "application": False,
}
