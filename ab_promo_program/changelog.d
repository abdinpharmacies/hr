commit f816a46
Author: hager yasser
Date:   Sun Aug 16 2026

    ab_promo_program/feat: update Promotion Wizard Excel columns with new fields

- Add optional Promotion Wizard Excel columns for Compensation way, Compensation Type, and promotion_ownership.
- Validate optional compensation and ownership selection values before creating promotions.
- Include optional compensation and ownership values in the wizard grouping key to avoid merging different promotion metadata.
- Save optional compensation and ownership values on created promotions when the fields are available.

Files changed:

- ab_promo_program/changelog.d
- ab_promo_program/i18n/ar.po
- ab_promo_program/i18n/ar_001.po
- ab_promo_program/models/ab_promo_program_wiz.py


commit 3db5d59
Author: emadco88
Date:   Tue Jul 28 2026

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

- Move promotion ownership and compensation metadata fields into the base Promotion Programs module.
- Replace ownership values with `other_promotion` and `our_promotion`, defaulting new manual and Excel-created promotions to `other_promotion`.
- Keep compensation company, timing, type, and approval attachment fields optional at the model layer while preserving form-level required timing/type controls.
- Add the always-visible Compensation Details group to the base promotion form and keep the existing supplier accounting domain.
- Keep Excel validation/grouping compatible with the new ownership keys and English labels.
- Move Arabic compensation and ownership translations into `ab_promo_program` for both `ar` and `ar_001`.
- Replace the Promotion Wizard paste placeholder with the exact tab-separated header row and one realistic example row.
- Translate remaining Arabic promotion form labels for UoM basis, incentives, replica databases, and refine compensation/ownership wording.

Files changed:

- ab_promo_program/changelog.d
- ab_promo_program/i18n/ar.po
- ab_promo_program/i18n/ar_001.po
- ab_promo_program/models/ab_promo_program.py
- ab_promo_program/models/ab_promo_program_wiz.py
- ab_promo_program/views/ab_promo_program.xml
- ab_promo_program/views/ab_promo_program_wizard.xml
