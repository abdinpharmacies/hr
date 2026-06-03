# -*- coding: utf-8 -*-
{
    "name": "Payroll Sheet Engine (Excel Parity)",
    "summary": "Payroll calculation mirroring Excel sheet logic (J70, E70–H70 block, items and fingerprint) with an editable sheet interface",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Payroll",
    "author": "Alhassan Hossny",
    "license": "LGPL-3",
    "depends": ["ab_hr", "payroll_test"],
    "data": [
        "security/ir.model.access.csv",
        "data/payroll_excel_type_config_data.xml",
        "views/payroll_excel_type_config_views.xml",
        "views/payroll_excel_sheet_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
