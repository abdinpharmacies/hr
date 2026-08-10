# -*- coding: utf-8 -*-
{
    "name": "AB Transfer Smart",
    "version": "19.0.1.0.0",
    "summary": "Smart automatic transfer calculation for AB transfers",
    "category": "Inventory",
    "depends": [
        "ab_transfer",
        "ab_sales",
        "ab_eplus_connect",
        "report_xlsx",
    ],
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "views/ab_product_views.xml",
        "views/ab_transfer_header_views.xml",
        "views/ab_transfer_smart_wizard_views.xml",
        "views/ab_transfer_smart_cache_views.xml",
        "report/ab_transfer_line_reports.xml",
        "report/ab_transfer_smart_xlsx_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_transfer_smart/static/src/scss/smart_header.scss",
            "ab_transfer_smart/static/src/js/smart_product_import_text_field.js",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
