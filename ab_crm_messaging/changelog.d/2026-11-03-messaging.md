# Shared messaging accounts, API and delivery queue

Current changes before commit:

- New Odoo 19 addon based on ab_template; author Abdin Pharmacies, developer Alhassan Hossny.
- Extends existing CRM through inheritance, preserving its source and XML IDs.
- Adds explicit scoped accounts, a dedicated service role, authenticated JSON-2 methods, immutable approved operations, expiring leases and durable receipt/evidence handling.
- Adds staff delivery/review views, branch/company isolation and protected review history; no old gateway or OMS dependency.
- Includes English source strings and both Arabic catalogs; activation remains a separately authorized deployment step.

Files changed:

- __init__.py
- __manifest__.py
- i18n/ar.po
- i18n/ar_001.po
- models/__init__.py
- models/messaging.py
- security/ir.model.access.csv
- security/record_rules.xml
- security/security_groups.xml
- static/description/icon.png
- tests/__init__.py
- tests/test_messaging.py
- views/views.xml
- changelog.d/2026-11-03-messaging.md
