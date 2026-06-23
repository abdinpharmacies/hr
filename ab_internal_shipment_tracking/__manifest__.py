{
    "name": "Internal Shipment Tracking",
    "summary": "Track internal movement of documents, files, and devices",
    "version": "19.0.1.0.0",
    "category": "AbdinSupplyChain",
    "license": "LGPL-3",
    "application": True,
    "depends": ["base", "mail", "ab_hr", "ab_store"],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "data/sequence.xml",
        "data/state_migration.xml",
        "views/internal_shipment_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
