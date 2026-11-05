Current changes before commit:

- Add the branch-only POS status tag and authorized store-scoped opening/recovery synchronization; retain cached stock on failures. Increment branch addon to 19.0.4.0.3 and maintain Arabic translations.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/__init__.py
- ab_branch_sync/models/pos.py
- ab_branch_sync/static/src/pos/central_status.js
- ab_branch_sync/static/src/pos/central_status.xml
- ab_branch_sync/static/src/pos/central_status.scss
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-05-pos-connection.md

Recent relevant commit: 7b07927cc790d579642ccf53908016d213b46272, hager yasser, 2026-11-04, feat(ab_central_sync): add store-scoped enrollment and custom CA trust. The role split and POS work are uncommitted.

Validation:

- Isolated ORM checks passed for scoped open synchronization, read-only polling, employee authorization, foreign-store rejection, legacy queue exclusion, HTTP403/503 and retained snapshots.
- Component lifecycle checks passed for login gating, opening sync, reconnect sync, overlapping requests, stale store responses and timer cleanup.
- Live branch upgraded to 19.0.4.0.3 and workers reloaded. Central was stopped during live verification; offline status and Arabic messages were correct, and cached stock was retained.
- Live JS/XML/CSS assets built successfully; generated JavaScript syntax, XML insertion anchor and both Arabic catalogs validated. No browser surface was available for visual inspection.
