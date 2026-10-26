Commit: d50d620dec7ea57f5963d0085b74e7101e4297fc
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-25T15:58:08+03:00
Original commit subject: ab_sales_delivery_tracking/allow delivery notification inputs

User-facing changes:
- Allow delivery consent and instructions through the callcenter header filter while retaining consent, instructions and UI-version validation.

Files changed:
- ab_sales_delivery_tracking/changelog.d/2026-10-25-callcenter-pos-field-allowlists.md
- ab_sales_delivery_tracking/models/ab_sales_pos_api.py

Current changes before commit:
- Remove delivery metadata descriptors together with omitted notification fields, preventing ordinary bills from being rejected with Invalid sale field descriptor.
- Preserve delivery fields and descriptors when notifications are enabled, with the existing branch-capability check.
- Repair only orphaned delivery descriptors in a newly authorized corrected revision of a rejected bill; ordinary retries retain their frozen payloads.
- Bump to 19.0.2.0.1. No new user-facing strings; existing English/Arabic messages remain unchanged.

Files changed:
- ab_sales_delivery_tracking/__manifest__.py
- ab_sales_delivery_tracking/changelog.d/2026-10-26-delivery-metadata-descriptors.md
- ab_sales_delivery_tracking/models/delivery_fields.py

Validation:
- Targeted ab_sales and ab_sales_delivery_tracking upgrades passed on a disposable callcenter clone.
- 29 checks passed for notifications on/off, receiver descriptor validation against the branch field schema, the actual rejected payload, immutable retries and correction revision/history behavior.
- External calls were mocked or blocked. No live invoice was submitted or changed.
- Evidence: /tmp/delivery_metadata_fix_20261026/tests.log and results.json.
