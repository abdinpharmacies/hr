{
    "name": "Stock Update",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "author": "Abdin Pharmacies",
    "developer": "'ahmedzenhom2610'",
    "application": True,
    "depends": ["base", "ab_eplus_connect", "ab_store"],
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "views/ab_stock_update_views.xml",
        "wizard/ab_stock_update_confirm_views.xml",
        "views/ab_store_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
