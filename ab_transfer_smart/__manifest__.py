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
    ],
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "data/ir_cron.xml",
        "views/ab_transfer_header_views.xml",
        "views/ab_transfer_smart_wizard_views.xml",
        "views/ab_transfer_smart_cache_views.xml",
        "report/ab_transfer_line_reports.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_transfer_smart/static/src/scss/smart_header.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
