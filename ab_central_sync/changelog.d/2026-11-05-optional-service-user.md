Current changes before commit:

- Align inventory protocol 3 with the existing POS optional service-user assignment.
- Preserve explicit assignments, authenticated replica scope, actor ACLs, and employee authorization.
- Remove the unconditional service-user setup gate; distinguish unsupported protocol versions.
- Increment to 19.0.4.0.1 and update the workflow.

Files changed:

- ab_central_sync/__manifest__.py
- ab_central_sync/controllers/main.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-05-optional-service-user.md

Recent relevant commits: see the role-split changelog for commit hashes, authors, dates and original subjects; this correction is uncommitted.

Validation: isolated tests allow authorized v3 posting with an unassigned service user and reject explicit-user mismatches or unauthorized employees. Branch online approval, local cashier payment, and HTTP403 rejection passed. Targeted live upgrades to 19.0.4.0.1 and worker reloads completed; authenticated replica102/store29 handshake verified. No live bill was created or replayed for verification. Both Arabic catalogs pass msgfmt.
