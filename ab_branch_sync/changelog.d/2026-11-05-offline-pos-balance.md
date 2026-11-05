Current changes before commit:

- Return local sellable balances after POS approval/retry/recovery and immediately update branch product cards and draft lines, even when central is offline. Reject stale display reads and preserve quantities/prices. Increment to 19.0.4.0.4.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/sales.py
- ab_branch_sync/static/src/pos/submission_balance.js
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-05-offline-pos-balance.md

Recent relevant commit: 7b07927cc790d579642ccf53908016d213b46272, hager yasser, 2026-11-04, feat(ab_central_sync): add store-scoped enrollment and custom CA trust. Role split and this fix are uncommitted.

Validation:

- Isolated offline approval returned 19 -> 18 immediately. Retry and recovery returned the same absolute balance; a subsequent acknowledging central snapshot kept 18. No branch inventory movement or payment was created.
- UI tests cover cards and other same-store drafts, zero stock, repeated acknowledgment, lost-response recovery, invalidating stale reads, and foreign-store isolation. Quantities/prices are preserved.
- Live targeted upgrade to 19.0.4.0.4 and worker reload completed. Existing-bill feedback verified without central requests or new transactions; backend assets generated and JavaScript syntax validated.
- No user-facing strings were added or changed, so existing Arabic catalogs require no new entries.
