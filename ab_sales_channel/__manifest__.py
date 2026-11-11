{
    "name": "Abdin Sales Channel",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "author": "Abdin Pharmacies",
    "developer": "emadco88",
    "application": False,
    "depends": ["ab_sales"],
    "data": [
        "security/ir.model.access.csv",
        "data/ab_sales_channel_data.xml",
        "views/ab_sales_channel_views.xml",
        "views/ab_sales_header_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_sales_channel/static/src/pos/**/*.js",
            "ab_sales_channel/static/src/pos/**/*.xml",
        ],
    },
    "installable": True,
}
