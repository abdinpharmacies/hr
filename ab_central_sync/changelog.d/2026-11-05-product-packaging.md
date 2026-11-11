Current changes before commit:

- Derive inventory conversion from replicated package data when no explicit stock mapping exists; no extra product configuration is required.
- Preserve existing explicit mappings and reject invalid packaging or fractional smallest units.
- Increment to 19.0.4.0.2, maintain both Arabic catalogs, and document central-only opening stock and branch snapshots.

Files changed:

- ab_central_sync/models/product.py
- ab_central_sync/models/__init__.py
- ab_central_sync/__manifest__.py
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-05-product-packaging.md

Recent relevant commit: 7b07927cc790d579642ccf53908016d213b46272, hager yasser, 2026-11-04, feat(ab_central_sync): add store-scoped enrollment and custom CA trust (branch worktree baseline). Role separation and this correction are uncommitted; see the role-split changelog for the central baseline.

Validation:

- Targeted live upgrades on central and branch to 19.0.4.0.2; both workers reloaded.
- T500 uses its existing BOX/5-TAB packaging without master writes; whole-unit conversion and explicit-mapping compatibility passed.
- Central-only opening TEST-TAVACIN-20261105 posted +50 tablets. Branch bill N-17716 created central bill N-17591 and movement #2 for -5 tablets; final balance is 45 tablets / 9 boxes.
- HTTP duplicate replay returned the same bill without another deduction. Branch has no T500 inventory movements or test payment; both bills remain pending cashier collection.
- Full branch snapshot, Current Stock Balance report, Arabic runtime checks, and msgfmt validation passed.
