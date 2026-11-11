## 545f50a38538248ee0f724a898eac97de24f961f — hager yasser — 2026-10-01

Original commit subject: ab_sales_doctor/FEAT(#20447): POS Product Search by Sales Price

User-facing changes:
- Support POS product searches by sales price.

Files changed:
- ab_sales_doctor/changelog.d/2026-08-30-bill-wizard-doctor-filter.md
- ab_sales_doctor/models/ab_sales_ui_api.py
- ab_sales_doctor/static/src/pos/pos_action_doctor.js

## Current changes before commit:

- Preserve each prescription checkbox in initial submissions, retries, and cached submission snapshots.
- Explicitly allow doctor header fields and prescription line flags; remove RPC interception and product-based flag matching.

Files changed:
- ab_sales_doctor/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales_doctor/models/ab_sales_pos_api.py
- ab_sales_doctor/static/src/pos/pos_action_doctor.js
