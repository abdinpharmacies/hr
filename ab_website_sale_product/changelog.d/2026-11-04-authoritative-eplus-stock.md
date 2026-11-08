# Eplus snapshot replacement and bounded branch refresh

## Current changes before commit:

- Include previously matched, now inactive snapshot products in full inventory synchronization with zero quantity, so old stock does not survive a complete source refresh. Active rows still determine the product total.
- Read and apply branch stock in batches of 1,000 instead of loading the full result into memory. This addresses the recorded `MemoryError` at `cursor.fetchall()`.
- Archive and reactivate branch snapshot rows within one savepoint, clearing ORM caches between batches. A failed source read rolls back the refresh and preserves the previous snapshot; products and stock history are not deleted.
- Propagate connector errors instead of treating a failed fetch as an empty snapshot. Only retry the metadata-free branch query before any batch has been consumed.
- Remove `NOLOCK` hints: inventory refresh uses the connection's normal isolation rather than explicitly accepting dirty reads. The existing aggregate across branches and quantity units remain unchanged; Eplus is read-only.
- The initial snapshot replacement introduced no UI strings; the subsequent branch-timeout correction adds a translated source-failure message, documented in `2026-11-04-branch-stock-timeout.md`.

Files changed:

- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/models/eplus_inventory_sync_job.py`
- `ab_website_sale_product/changelog.d/2026-11-04-authoritative-eplus-stock.md`

Validation:

- Targeted upgrade of this module and `ab_ecommerce_storefront` on isolated `codex_eplus_sync_20261104` passed; 48 storefront inventory/reservation integration tests passed with no failures or errors. External reads were mocked, including bounded cursor fetches, distinct branch quantities, and mid-stream source failure.
- Both Arabic catalogs passed `msgfmt --check-format`; whitespace checks passed.
- Production-scale branch refresh against live Eplus remains unverified. No external write or live stock reset was performed.

- Runtime verification on the isolated database confirmed `Eplus Stock` in `en_US` and `مخزون Eplus` in `ar_001`; the removed guard is absent from the loaded registry.

Follow-up: branch reads now use parameterized per-store ODBC queries. Final combined validation passed 51 tests; see `2026-11-04-branch-stock-timeout.md` for the read-only live probe and translation evidence.

## Relevant prior commit

Commit: `a66d053feb106a3f41b08d22bc44ec785fde7686`
Author: Mohamed Fawzy
Date: 2026-10-29
Original commit subject: `ab_website_sale_product/FIX: restore E-Plus stock refresh on store`

- Restored stock refresh through the connector's default driver.

Files changed:

- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/changelog.d/current.md`
