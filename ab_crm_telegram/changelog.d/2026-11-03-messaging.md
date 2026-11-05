# Telegram private-chat reply handling

Current changes before commit:

- New Odoo 19 addon based on ab_template; author Abdin Pharmacies, developer Alhassan Hossny.
- Extends existing CRM through inheritance, preserving its source and XML IDs.
- Adds Telegram account selection and private-chat destination eligibility; no delivered/read claims.
- Includes English source strings and both Arabic catalogs; activation remains a separately authorized deployment step.

Files changed:

- __init__.py
- __manifest__.py
- i18n/ar.po
- i18n/ar_001.po
- models/__init__.py
- models/account.py
- static/description/icon.png
- changelog.d/2026-11-03-messaging.md
