## fc0a6ff4a730e171d33669f6ca75354bec764023 — hossam elsheikh — 2026-10-21

Original commit subject: ab_sales_doctor:fix_translation

User-facing changes:
- Complete Arabic translations for prescription workflows.

Files changed:
- ab_sales_doctor/__manifest__.py
- ab_sales_doctor/changelog.d/2026-10-21-arabic-completion.md
- ab_sales_doctor/i18n/ar.po
- ab_sales_doctor/i18n/ar_001.po
- ab_sales_doctor/static/src/pos/bill_wizard_doctor_filter.xml

## Source reference: d5e539adeb9251ef18e266806a80110f0485abcc — emadco88 — 2026-10-22

Original commit subject: ab_sales_doctor/ UPD, add the doctor fields to allowed

User-facing changes:
- Preserve doctor and individual prescription-line fields through submission.

Files changed:
- ab_sales_doctor/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales_doctor/models/ab_sales_pos_api.py
- ab_sales_doctor/static/src/pos/pos_action_doctor.js

Adapted to the callcenter branch API workflow; not a whole-branch merge.

## Current changes before commit:

- Allow doctor and prescription inputs through the shared submission filters.
- Attach the prescription flag to each submitted line through _buildSubmitLine instead of temporarily wrapping the ORM service.
- Preserve independent prescription flags when the same product appears on multiple lines.

Files changed:
- ab_sales_doctor/changelog.d/2026-10-25-callcenter-pos-field-allowlists.md
- ab_sales_doctor/models/ab_sales_pos_api.py
- ab_sales_doctor/static/src/pos/pos_action_doctor.js
