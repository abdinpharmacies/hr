# -*- coding: utf-8 -*-
{
    "name": "Abdin Payroll",
    "summary": "Secure payroll sheet validation and Telegram distribution",
    "version": "19.0.1.1.1",
    "license": "LGPL-3",
    "category": "Human Resources/Payroll",
    "author": "Abdin Pharmacies",
    "developer": "Alhassan Hossny",
    "depends": ["ab_hr"],
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "views/menus.xml",
        "data/payroll_sheet_cron.xml",
        "views/payroll_sheet_views.xml",
        "wizard/payroll_sheet_upload_wizard_views.xml",
    ],
    "application": True,
    "installable": True,
}
