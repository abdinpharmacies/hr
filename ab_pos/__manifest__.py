# -*- coding: utf-8 -*-

{
    "name": "Ab POS (Simple)",
    "version": "19.0.0.1.0",
    "category": "Sales",
    "summary": "Simple OWL POS UI for Abdin models",
    "depends": ["web", "ab_sales", "ab_product", "ab_customer", "ab_store"],
    "data": [
        "security/ir.model.access.csv",
        "views/ab_pos_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_pos/static/src/ab_pos_simple/**/*.js",
            "ab_pos/static/src/ab_pos_simple/**/*.xml",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
