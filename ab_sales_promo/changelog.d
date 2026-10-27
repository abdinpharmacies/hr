# Optional currency on passive sales headers

Recent relevant commit: `2468a38e7ce5aec2d20f6d855a58b9d9e12efe1a`
Author: emadco88
Date: 2026-10-01
Original subject: ab_sales_promo/ FIX made a passive module

Current changes before commit:

- Make ab_sales_header.currency_id optional so the passive mirror passes mapping validation and Load Matching Fields can generate currency and monetary mappings.
- Preserve the currency relation, existing company-currency default, stored currency values, and monetary fields.
- Keep required-value enforcement available on individual sync mappings and retain readonly target protections.
- Bump the module version to 19.0.1.0.1.

Validation and deployment:

- 14 focused checks passed on an isolated database, covering matching-field loading, currency defaults and optional values, totals, readonly protections, and public access restrictions.
- Isolated installation and targeted module upgrade passed. Test records and generated mappings were rolled back; script: /opt/odoo19/validation/sales_currency/test_currency.py.
- Backed up configuration under /opt/odoo19/resource-tuning-backups/20261026-sales-currency and upgraded only ab_sales_promo on report19 to installed version 19.0.1.0.1.
- Verified production mirror validation succeeds without generating mappings or reapplying uploads.
- Before/after snapshots of profiles, mappings, header counts/currency counts/totals, queue count, and upload 32685 match exactly.
- Restarted Odoo and the already-running queue runner, preserving their running states.

Files changed:

- `__manifest__.py`
- `models/ab_promo_program_compensation.py`
- `changelog.d`

Historical references:

commit affa283
Author: ahmedzenhom2610
Date:   Mon Aug 3 2026

    ab_sales_promo/ FIX translation and required to false

- Kept promotion compensation fields compatible with existing records by removing backend-required flags.
- Adjusted compensation field translations.

Files changed:

- ab_sales_promo/models/ab_promo_program_compensation.py


commit 4c05fdd
Author: ahmedzenhom2610
Date:   Mon Aug 3 2026

    ab_sales_promo/ UPDs add new fields

- Added promotion compensation metadata fields and form section.
- Added Arabic translations for the compensation metadata.
- Updated focused specific promotion tests for compensation metadata compatibility.

Files changed:

- ab_sales_promo/__manifest__.py
- ab_sales_promo/i18n/ar_001.po
- ab_sales_promo/models/__init__.py
- ab_sales_promo/models/ab_promo_program_compensation.py
- ab_sales_promo/tests/test_ab_sales_specific_promo.py
- ab_sales_promo/views/ab_promo_program_compensation.xml
