{
    "name": "Abdin Website Admin Content",
    "summary": "Modern content-management UI for Website administration screens",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "Website/eCommerce",
    "author": "Abdin Pharmacies",
    "developer": "Mohamed Fawzy",
    "application": False,
    "depends": [
        "website_sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "views/content_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_website_admin_content/static/src/js/carousel_position_preview.js",
            "ab_website_admin_content/static/src/scss/content_admin.scss",
        ],
    },
    "installable": True,
}
