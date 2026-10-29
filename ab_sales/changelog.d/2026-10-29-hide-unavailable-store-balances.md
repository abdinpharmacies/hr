# Hide unavailable Store Balances

Recent relevant commit:
- Commit: `9d873dc70a36e52eaecf3bf04ebc7dd52025367b`
- Author: Alhassan Hossny
- Date: 2026-10-29
- Original commit subject: ab_sales/feat: improve store balance popup usability
- Added branch search, keyboard fallback, responsive RTL layout and refresh feedback.

Current changes before commit:
- Hide rows whose source is unavailable or whose balance is nonfinite. Retain saved balances, zero balances and known stock when API refresh is disabled.
- Filter and count available branches in their established order. Distinguish no search matches, no transfer-enabled branches and no currently available balances.
- Add the new empty-state message to both Arabic catalogs using the exported Odoo POT. Preserve refresh warnings, saved-balance indicators, eligibility and branch configuration.

Files changed:
- ab_sales/static/src/pos/store_balance_rows.js
- ab_sales/static/src/pos/store_balance_rows.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-10-29-hide-unavailable-store-balances.md

Validation:
- The combined popup suite passed 24 logic checks, covering mixed sources, zero/nonfinite balances, empty/all-unavailable payloads, counts and preserved positions.
- Signed-in English/Arabic popup checks passed at 320/375/767/768/1024px. The isolated fixtures retain known stock for branch 102 with refresh disabled and refresh capability for branch 140.
- Both PO format checks and runtime translations passed. Filtering does not repair external connectivity or enable refresh.
- Combined verification totals 174 focused checks; counts overlap across these feature notes and must not be added together. Scripts, screenshots and limitations: `/tmp/customer_identity_validation/RESULTS.md`.
