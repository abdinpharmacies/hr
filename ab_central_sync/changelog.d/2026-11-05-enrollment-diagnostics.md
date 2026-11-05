Current changes before commit:

- Document branch identity validation, configuration restart, and recovery with the saved candidate credential.

Files changed:

- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-05-enrollment-diagnostics.md

Recent relevant commits: see the role-split changelog for the baseline; this diagnostic fix is uncommitted.

Validation: targeted upgrade passed; mocked mismatch rejects enrollment without replacing active credentials or downloading stock. Exported the module POT, merged the new Arabic entry, and passed msgfmt checks. Live enrollment recovered for user-confirmed replica 102/store 29; credential authentication and initial snapshot readiness passed. The initial snapshot contains zero product rows. English/Arabic diagnostic text differs at runtime.
