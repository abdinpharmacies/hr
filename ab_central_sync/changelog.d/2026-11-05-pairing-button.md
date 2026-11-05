Current changes before commit:

- Document the branch Connect to Central save behavior and one-time pairing-code lifecycle. Central runtime behavior is unchanged.

Files changed:

- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-05-pairing-button.md

Recent relevant commits: see the role-split changelog for the existing baseline; this fix is uncommitted. No user-facing strings were added or changed.

Validation: targeted branch upgrades passed on the disposable database and live abdin_pos. The installed English/Arabic Settings views retain noSaveDialog on Connect. An isolated mocked enrollment confirms the entered code reaches pairing, connection settings persist, and the temporary code is cleared; no live pairing was attempted. Arabic catalogs pass msgfmt --check-format.
