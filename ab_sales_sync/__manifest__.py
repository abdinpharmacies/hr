{
    "name": "Abdin Sales Sync",
    "summary": "Connect branch sales uploads to the reporting mirror models",
    "version": "19.0.2.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "author": "Abdin Pharmacies",
    "developer": "emadco88",
    "application": True,
    "depends": ["ab_sales", "ab_odoo_sync_mapping"],
    "data": [
        "data/sync_profiles.xml",
        "data/sync_profile_updates.xml",
        "data/sync_profiles_extra.xml",
    ],
    "installable": True,
}
