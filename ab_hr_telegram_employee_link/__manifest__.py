# -*- coding: utf-8 -*-
{
    "name": "HR Telegram Employee Link",
    "summary": "Link Telegram chat IDs to HR employees by employee code",
    "version": "19.0.1.1.1",
    "license": "LGPL-3",
    "author": "Abdin Pharmacies",
    "developer": "Alhassan Hossny",
    "category": "Human Resources",
    "depends": ["ab_payroll", "ab_telegram_webhook"],
    "external_dependencies": {"python": ["telebot"]},
    "data": [
        "views/ab_hr_employee_views.xml",
    ],
    "installable": True,
    "application": False,
}
