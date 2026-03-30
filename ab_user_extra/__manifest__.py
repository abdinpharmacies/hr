{
    "name": "AB User Extra",
    "summary": "Link Telegram accounts with Odoo users and PIN",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Abdin Pharmacies",
    "website": "https://www.abdinpharmacies.com",
    "category": "Tools",
    "depends": ["base", "ab_telegram_webhook"],
    "data": [
        "security/ir.model.access.csv",
        "views/ab_user_telegram_link_views.xml",
    ],
    "installable": True,
    "application": False,
}
