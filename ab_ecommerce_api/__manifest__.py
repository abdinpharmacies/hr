{
    "name": "Abdin eCommerce API",
    "summary": "Customer API with OpenAPI documentation and interactive Swagger UI",
    "version": "19.0.1.2.0",
    "license": "LGPL-3",
    "category": "Website/eCommerce",
    "author": "Abdin Pharmacies",
    "developer": "Mohamed Fawzy",
    "depends": ["ab_ecommerce_storefront"],
    "data": [
        "security/record_rules.xml",
        "security/ir.model.access.csv",
        "views/docs.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_ecommerce_api/static/src/workspace.js",
            "ab_ecommerce_api/static/src/workspace.xml",
            "ab_ecommerce_api/static/src/workspace.scss",
        ],
    },
    "installable": True,
    "application": True,
}
