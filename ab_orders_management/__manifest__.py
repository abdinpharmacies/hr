{
    "name": "Orders Management",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "summary": "Manage pharmacy delivery pilots, branches, and assignments",
    "depends": ["base", "web", "ab_hr"],
    "application": True,
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "views/pharmacy_delivery_branch_views.xml",
        "views/pharmacy_delivery_pilot_views.xml",
        "views/pharmacy_delivery_assignment_views.xml",
        "views/pharmacy_delivery_dashboard_views.xml",
        "views/menus.xml",
        "wizard/pharmacy_delivery_assignment_wizard_views.xml",
    ],
    "demo": [
        "data/demo.xml",
    ],
    "author": "OpenAI",
    "assets": {
        "web.assets_backend": [
            "ab_orders_management/static/src/js/**/*.js",
            "ab_orders_management/static/src/xml/**/*.xml",
            "ab_orders_management/static/src/scss/**/*.scss",
        ],
    },
    "installable": True,
}
