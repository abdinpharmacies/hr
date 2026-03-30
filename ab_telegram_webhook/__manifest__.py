{
    "name": "AB Telegram Webhook",
    "summary": "Telegram webhook echo test using telebot",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Abdin Pharmacies",
    "website": "https://www.abdinpharmacies.com",
    "category": "Tools",
    "depends": ["base"],
    "external_dependencies": {
        "python": ["telebot"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/setup.xml",
        "views/ab_telegram_chat_message_views.xml",
    ],
    "installable": True,
    "application": False,
}
