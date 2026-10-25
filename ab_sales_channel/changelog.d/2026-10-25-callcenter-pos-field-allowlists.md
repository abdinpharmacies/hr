## 1d71a1367d4c093091ccaebf4d6d416d9105f697 — emadco88 — 2026-08-11

Original commit subject: ab_sales_channel/ UPDs make field required

User-facing changes:
- Require a sales channel in the invoice form.

Files changed:
- ab_sales_channel/changelog.d/2026-08-11-sales-channel.md
- ab_sales_channel/i18n/ar.po
- ab_sales_channel/i18n/ar_001.po
- ab_sales_channel/models/ab_sales_channel.py
- ab_sales_channel/models/ab_sales_header.py
- ab_sales_channel/views/ab_sales_header_views.xml

## Source reference: ade5853f62f52bc54d926c85fb48eb4a8577d16d — emadco88 — 2026-10-22

Original commit subject: ab_sales_channel/ UPD , add the allowed fields via hook

User-facing changes:
- Preserve the selected sales channel through submission.

Files changed:
- ab_sales_channel/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales_channel/models/__init__.py
- ab_sales_channel/models/ab_sales_pos_api.py

Adapted to the callcenter branch API workflow; not a whole-branch merge.

## Current changes before commit:

- Register the POS API extension and allow sales_channel_id through shared submission filters when this addon is installed.

Files changed:
- ab_sales_channel/changelog.d/2026-10-25-callcenter-pos-field-allowlists.md
- ab_sales_channel/models/__init__.py
- ab_sales_channel/models/ab_sales_pos_api.py
