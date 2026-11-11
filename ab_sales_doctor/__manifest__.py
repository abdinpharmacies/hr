{
    "name": "Abdin Sales Doctor Prescription",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "depends": ["ab_sales", "ab_odoo_connect", "ab_odoo_replication"],
    "data": [
        "security/ir.model.access.csv",
        "data/ab_doctor_cron.xml",
        "views/ab_doctor_views.xml",
        "views/ab_product_doctor_prescription_views.xml",
        "views/ab_sales_header_views.xml",
        "views/ab_sales_line_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_sales_doctor/static/src/pos/**/*.js",
            "ab_sales_doctor/static/src/pos/**/*.xml",
            "ab_sales_doctor/static/src/pos/**/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
