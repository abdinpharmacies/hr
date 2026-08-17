{
    "name": "Stock Movement Report",
    "summary": "Show the latest stock movements for a product from BConnect.",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "author": "Abdin Pharmacies",
    "developer": "itharrefaat5",
    "depends": [
        "base",
        "ab_product",
        "ab_eplus_connect",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ab_stock_report_cron.xml",
        "views/ab_stock_report_views.xml",
    ],
    "installable": True,
    "application": False,
}
