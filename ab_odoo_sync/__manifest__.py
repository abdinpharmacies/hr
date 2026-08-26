{
    "name": "ab_odoo_sync",
    "summary": "Event-driven one-way sync from MAIN to BRANCH Odoo servers",
    "description": "Append-only event log synchronization between MAIN and BRANCH servers.",
    "author": "abdinpharmacies",
    "developer": "Alhassan Hossny",
    "website": "https://www.abdinpharmacies.com",
    "license": "LGPL-3",
    "category": "Tools",
    "version": "19.0.2.3.1",
    "depends": ["base", "web", "queue_job"],
    "data": [
        "security/ir.model.access.csv",
        "data/ab_odoo_sync_queue_job.xml",
        "data/ab_odoo_sync_cron.xml",
        "views/ab_odoo_sync_views.xml",
        "views/ab_odoo_sync_upload_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_odoo_sync/static/src/fields/pretty_json/pretty_json_field.js",
            "ab_odoo_sync/static/src/fields/pretty_json/pretty_json_field.xml",
            "ab_odoo_sync/static/src/fields/pretty_json/pretty_json_field.scss",
        ],
    },
    "installable": True,
    "application": False,
}
