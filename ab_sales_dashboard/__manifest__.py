{
    "name": "Sales Dashboard",
    "description": "Management sales dashboard backed by BConnect / E-Plus reporting data.",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "author": "Abdin Pharmacies",
    "developer": "Alhassan Hossny",
    "application": True,
    "depends": ["base", "web", "ab_eplus_connect", "ab_store", "ab_product"],
    "data": [
        "security/security_groups.xml",
        "security/record_rules.xml",
        "security/ir.model.access.csv",
        "views/menus.xml",
        "data/sales_dashboard_sequence.xml",
        "data/sales_dashboard_telemetry_cron.xml",
        "views/sales_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_sales_dashboard/static/src/scss/sales_dashboard.scss",
            "ab_sales_dashboard/static/src/js/sales_dashboard_action.js",
        ],
    },
    "installable": True,
}
