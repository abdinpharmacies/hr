{
    "name": "Abdin Sales Cashier",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "depends": ["ab_sales"],
    "data": [
        "security/ir.model.access.csv",
        "views/cashier_action.xml",
        "views/cashier_close_wizard.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_sales_cashier/static/src/cashier/**/*.js",
            "ab_sales_cashier/static/src/cashier/**/*.xml",
            "ab_sales_cashier/static/src/cashier/**/*.scss",
        ],
    },
    "installable": True,
}
