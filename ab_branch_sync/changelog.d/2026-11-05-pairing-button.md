Current changes before commit:

- Fix Connect to Central being cancelled by the Settings save/reload dialog.
- Use Odoo’s built-in noSaveDialog option so the existing connection action receives the temporary pairing code and saves connection settings.
- Increment the branch module to 19.0.3.0.2; document direct connection and temporary code behavior.

Files changed:

- ab_branch_sync/__manifest__.py
- ab_branch_sync/views/enrollment.xml
- ab_branch_sync/workflow.md
- ab_branch_sync/changelog.d/2026-11-05-pairing-button.md

Recent relevant commits: see the role-split changelog for the existing baseline; this fix is uncommitted. No user-facing strings were added or changed.

Validation: targeted branch upgrades passed on the disposable database and live abdin_pos. The installed English/Arabic Settings views retain noSaveDialog on Connect. An isolated mocked enrollment confirms the entered code reaches pairing, connection settings persist, and the temporary code is cleared; no live pairing was attempted. Arabic catalogs pass msgfmt --check-format.
