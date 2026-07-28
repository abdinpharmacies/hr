{
    "name": "Ab Employee Access",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "summary": "Employee access profiles used by POS HR flows.",
    "depends": [
        "ab_hr",
        "web",
        "ab_widgets",
    ],
    "data": [
        'security/ir.model.access.csv',
        'views/ab_employee_access.xml',
        'views/ab_employee_access_sales_role_views.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "ab_employee_access/static/src/login/**/*.js",
            "ab_employee_access/static/src/login/**/*.xml",
            "ab_employee_access/static/src/login/**/*.scss",
        ],
    },
    "installable": True,
    "auto_install": True,
    "application": False,
}
