Current changes before commit:

- Accept HTTP central endpoints for trusted LAN/VPN deployments without certificates.
- Add administrator-only Verify TLS Certificate setting, enabled by default; persist explicit disabled values and ignore CA bundles when disabled.
- Keep pairing/authentication, scope checks and redirect refusal; never downgrade automatically after a TLS failure.
- Update both Arabic catalogs and workflow documents; increment branch module to 19.0.3.0.1.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/views/enrollment.xml
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-05-optional-tls-verification.md

Recent relevant commits: none; ab_branch_sync is a new uncommitted module in this worktree. The role-split changelog records its baseline.

Validation: isolated targeted upgrade; HTTP/HTTPS verification modes, custom CA handling, persisted disabled setting, authentication and redirect preservation, invalid URL rejection and no automatic TLS downgrade passed. Arabic catalogs passed msgfmt and the new field label was checked at runtime. Live settings were not changed.
