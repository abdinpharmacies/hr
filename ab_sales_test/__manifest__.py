{
    "name": "Abdin Sales Regression Tests",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "author": "Abdin Pharmacies",
    "developer": "'ahmedzenhom2610'",
    "application": False,
    "depends": [
        "ab_sales",
        "ab_sales_contract",
        "ab_sales_promo",
        "ab_sales_doctor",
        "ab_hr",
        "ab_employee_access_sales",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/test_case_views.xml",
    ],
    "installable": True,
}
