{
    "name": "Request Telegram Notifications",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "application": False,
    "depends": ["ab_request_management", "ab_payroll"],
    "data": [
        "security/ir.model.access.csv",
        "views/ab_hr_bot_views.xml",
    ],
    "installable": True,
}
