{
    "name": "AB WhatsApp API",
    "summary": "WhatsApp Cloud API dashboard in Odoo 19 (OWL)",
    "version": "19.0.1.0.1",
    "category": "Tools",
    "author": "Internal",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/ab_whatsapp_api_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_whatsapp_api/static/src/dashboard/whatsapp_dashboard.js",
            "ab_whatsapp_api/static/src/dashboard/whatsapp_dashboard.xml",
            "ab_whatsapp_api/static/src/dashboard/whatsapp_dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
}
