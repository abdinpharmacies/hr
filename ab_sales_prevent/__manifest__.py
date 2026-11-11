{
    "name": "Abdin Sales Prevent",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "summary": "Database-level switch to disable sales operations.",
    "depends": ["base_setup", "ab_sales", "ab_sales_cashier", "ab_sales_lead"],
    "data": [
        "data/ir_config_parameter.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
}
