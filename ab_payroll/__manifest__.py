# -*- coding: utf-8 -*-
{
    "name": "Abdin Payroll",
    "summary": "Secure payroll sheet validation and Telegram distribution",
    "version": "19.0.1.0.2",
    "license": "LGPL-3",
    "category": "Human Resources/Payroll",
    "author": "Abdin Pharmacies",
    "developer": "Alhassan Hossny",
    "depends": ["ab_hr", "abdin_telegram"],
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "views/payroll_sheet_views.xml",
        "views/ab_hr_employee_views.xml",
        "data/payroll_sheet_cron.xml",
        "wizard/payroll_sheet_upload_wizard_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "application": True,
    "installable": True,
}
