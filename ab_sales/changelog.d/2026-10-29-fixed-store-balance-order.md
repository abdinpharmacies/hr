# Fixed descending Store Balances opening order

Recent relevant commit:
- Commit: `9d873dc70a36e52eaecf3bf04ebc7dd52025367b`
- Author: Alhassan Hossny
- Date: 2026-10-29
- Original commit subject: ab_sales/feat: improve store balance popup usability
- Added branch search, keyboard fallback, responsive RTL layout and refresh feedback.

Current changes before commit:
- Establish descending balance order once for each popup/product, with locale-aware branch-name and numeric-ID ties. Place initially unknown balances after known balances.
- Retain branch positions through successful, failed and concurrent refreshes, search, same-product replacements, removals and later availability. Append newly encountered IDs numerically.
- Preserve established order through Arabic/English keyboard fallback and clearing search. Reopening the popup or changing product establishes a fresh order.
- Keep stale-response guards, mount-only focus, backend payloads and cached balances unchanged.

Files changed:
- ab_sales/static/src/pos/store_balance_rows.js
- ab_sales/changelog.d/2026-10-29-fixed-store-balance-order.md

Validation:
- The combined popup suite passed 24 logic checks, including refreshes above/below opening extremes, deterministic ties, replacement payloads, keyboard fallback, stale replies and reopening.
- Signed-in English/Arabic popup checks passed at 320/375/767/768/1024px with no popup overflow; existing 44px targets and responsive RTL layout are retained.
- Combined verification totals 174 focused checks; counts overlap across these feature notes and must not be added together. Scripts, screenshots and limitations: `/tmp/customer_identity_validation/RESULTS.md`.
