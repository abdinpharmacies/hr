commit 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date:   Tue Jul 28 15:21:42 2026 +0300

    INIT commit pos19

- Add the initial Promotion Programs module.
- Add promotion program models, wizard, security, views, translations, and module metadata.

Files changed:

- ab_promo_program/__init__.py
- ab_promo_program/__manifest__.py
- ab_promo_program/i18n/ar_001.po
- ab_promo_program/models/__init__.py
- ab_promo_program/models/ab_promo_program.py
- ab_promo_program/models/ab_promo_program_wiz.py
- ab_promo_program/security/ir.model.access.csv
- ab_promo_program/security/record_rules.xml
- ab_promo_program/security/security_groups.xml
- ab_promo_program/static/description/icon.png
- ab_promo_program/views/ab_promo_program.xml
- ab_promo_program/views/ab_promo_program_wizard.xml
- ab_promo_program/views/menus.xml

Current changes before commit:

- Sort Promotion Programs by newest technical ID first.
- Show the technical ID as a muted first column in the Promotion Programs list.
- Keep creation date available as an optional hidden list column.
- Add missing manifest developer metadata.
- Add optional Promotion Wizard Excel columns for Compensation way, Compensation Type, and promotion_ownership.
- Validate optional compensation and ownership selection values before creating promotions.
- Include non-empty optional compensation and ownership values in the wizard grouping key to avoid merging different promotion metadata.
- Save optional compensation and ownership values on created promotions when the fields are available.

Files changed:

- ab_promo_program/changelog.d
- ab_promo_program/__manifest__.py
- ab_promo_program/i18n/ar.po
- ab_promo_program/i18n/ar_001.po
- ab_promo_program/models/ab_promo_program.py
- ab_promo_program/models/ab_promo_program_wiz.py
- ab_promo_program/views/ab_promo_program.xml
