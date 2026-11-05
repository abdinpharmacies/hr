Current changes before commit:

- Display local enrollment validation errors and identify configured versus paired replica serials.
- Preserve identity/store validation and keep transport exceptions sanitized.
- Add the diagnostic in both Arabic catalogs and increment branch version to 19.0.3.0.3.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/models/enrollment.py
- ab_branch_sync/models/operation.py
- ab_branch_sync/i18n/ar.po
- ab_branch_sync/i18n/ar_001.po
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-05-enrollment-diagnostics.md

Recent relevant commits: see the role-split changelog for the baseline; this diagnostic fix is uncommitted.

Validation: targeted upgrade passed; mocked mismatch rejects enrollment without replacing active credentials or downloading stock. Exported the module POT, merged the new Arabic entry, and passed msgfmt checks. Live enrollment recovered for user-confirmed replica 102/store 29; credential authentication and initial snapshot readiness passed. The initial snapshot contains zero product rows. English/Arabic diagnostic text differs at runtime.
