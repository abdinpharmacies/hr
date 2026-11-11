Current changes before commit:

- Show explicit labels for Central URL, database, pairing code, certificate bundle, and connection status.
- Select synchronization stores independently of existing replica sales-store assignments, preserving legacy-store routing.
- Enforce matching selected scopes, prevent enrolled scope edits, and check genuine stock/payment/journal conflicts when adding stores to an existing enrollment.
- Restrict transport authorization, stock reservations, native routing, and replication exclusions to the selected synchronization scope.
- Verify HTTPS using an optional endpoint-specific certificate bundle without disabling certificate verification.
- Limit stock snapshots to products with inventory history in the selected store, retaining zero-stock updates for depleted products.
- Keep open POS bills local until confirmation; their open state never blocks activation or synchronization.
- Add Arabic translations for scope, certificate settings, and integrity conflicts in both catalogs, including Odoo Python translation markers.
- Document the existing-database pilot and its separation from real-store cutover.

Files changed:

- ab_central_sync/controllers/main.py
- ab_central_sync/models/cache.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/models/operation.py
- ab_central_sync/models/replication.py
- ab_central_sync/models/sales.py
- ab_central_sync/views/enrollment.xml
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/README.md
- ab_central_sync/changelog.d/2026-11-04-scoped-pilot.md

Recent relevant commit:

- Commit: 87c5d880
- Author: hager yasser
- Date: 2026-11-04
- Original subject: ab_central_sync/fix: support view loading in XML development mode
- Preserve XML development-mode view loading while improving the settings layout.
- Files changed: ab_central_sync/views/enrollment.xml, ab_central_sync/views/operations.xml, ab_central_sync/changelog.d/2026-11-04-xml-upgrade.md.
