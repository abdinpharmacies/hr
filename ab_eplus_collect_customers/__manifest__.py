# -*- coding: utf-8 -*-
{
    "name": "ab_eplus_collect_customers",
    "summary": "Collect spare customers from ePlus branch servers",
    "description": "Collect spare customers from ePlus branch servers and update main server.",
    "author": "abdinpharmacies",
    "website": "https://www.abdinpharmacies.com",
    "license": "LGPL-3",
    "category": "Abdin",
    "version": "19.0.1.0.0",
    "depends": ["ab_eplus_connect", "ab_store"],
    "data": [
        "data/cron_ab_eplus_collect_customers.xml",
    ],
    "installable": True,
}
