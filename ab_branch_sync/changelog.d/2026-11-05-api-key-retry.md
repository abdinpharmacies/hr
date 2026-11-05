# Inventory Writer API keys and immediate retry — 2026-11-05

Reference commit: `7b07927cc790d579642ccf53908016d213b46272`
Author: hager yasser
Date: 2026-11-04
Original subject: feat(ab_central_sync): add store-scoped enrollment and custom CA trust

The branch addon was split from that implementation in current uncommitted work.

Current changes before commit:

- Replace pairing, certificate and separate scope settings with central URL, database and Inventory Writer user API key. Existing replica/store routing remains in force. Changing connection credentials requires reconnecting.
- Retry immediately checks central status and retries a corrected protocol-3 rejection with the same immutable identity; an accepted operation returns its original bill without another deduction.
- Match sales units only through ab_product_uom, including name/type/factor for new payloads. Reject ab_uom as a sales mapping unit; preserve legacy packaging counts and stock ledger meaning.
- Preserve offline immediate balance feedback, snapshots, local bills, and branch cashier payments. Legacy protocol-2 events require reconciliation and are not replayed.
- Update current setup/workflow and Arabic translations for both language codes.

Validation: isolated real HTTP API-key authentication and foreign-store denial; ordinary writer posting and branch-only payment status; rejected then duplicate/lost-ack Retry; exact stock 19 → 18 once; inactive/unscoped/no-role users denied; offline POS feedback 19 → 18; JS feedback regression; Python/XML and PO validation. Live targeted upgrades to 19.0.5.0.0 and Arabic runtime checks passed. Branch upgrade still reports pre-existing missing unrelated models/module and a duplicate cache-row index warning, including existing duplicate cache rows in this replica scope; these also occur in the previous upgrade log. No unrelated schema/data repair was performed.

Files changed in this change:
- `ab_branch_sync/__manifest__.py`
- `ab_branch_sync/models/enrollment.py`
- `ab_branch_sync/models/operation.py`
- `ab_branch_sync/models/pos.py`
- `ab_branch_sync/models/product.py`
- `ab_branch_sync/models/sales.py`
- `ab_branch_sync/views/enrollment.xml`
- `ab_branch_sync/i18n/ar.po`
- `ab_branch_sync/i18n/ar_001.po`
- `ab_branch_sync/README.md`
- `ab_branch_sync/workflow.md`
- `ab_branch_sync/changelog.d/2026-11-05-api-key-retry.md`
