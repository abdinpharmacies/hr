{
    "name": "Abdin Sales Lead",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "application": False,
    "depends": ["ab_sales"],
    "data": [
        "security/ir.model.access.csv",
        "security/rules_sales_lead.xml",
        "views/ab_sales_lead_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_sales_lead/static/src/pos/**/*.js",
            "ab_sales_lead/static/src/pos/**/*.xml",
            "ab_sales_lead/static/src/pos/**/*.scss",
        ],
    },
    "installable": True,
}
