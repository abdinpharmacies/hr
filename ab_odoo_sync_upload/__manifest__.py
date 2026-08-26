{
    "name": "AB Odoo Sync Upload",
    "summary": "Queue branch records for upload to the reporting database",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "Tools",
    "author": "Abdin Pharmacies",
    "developer": "emadco88",
    "website": "https://www.abdinpharmacies.com",
    "application": True,
    "depends": ["ab_odoo_sync", "queue_job"],
    "data": [
        "security/ir.model.access.csv",
        "data/queue_jobs.xml",
        "data/crons.xml",
        "views/upload_views.xml",
    ],
    "installable": True,
}
