{
    "name": "AB Sales Odoo Sync Upload",
    "summary": "Sales and return source configuration for Odoo Sync Upload",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "Tools",
    "author": "Abdin Pharmacies",
    "developer": "'hossam elsheikh'",
    "application": False,
    "depends": [
        "ab_odoo_sync_upload",
        "ab_sales",
        "ab_sales_lead",
        "ab_sales_doctor",
        "ab_transfer",
        "ab_transfer_smart",
        "ab_employee_access_sales",
    ],
    "data": [
        "data/data_ab_sales_odoo_sync_upload_source.xml",
    ],
    "installable": True,
}
