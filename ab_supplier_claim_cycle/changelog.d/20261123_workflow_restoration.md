# 19.0.7.2.5 — workflow restoration and reset feedback

- Unarchive restores a workflow with submission snapshots to the same Published,
  active version, preserving linked claims and decisions without creating a copy.
- Unused workflows still restore to Draft and clear linked draft selections,
  including archived draft claims.
- Every Published workflow shows Reset to Draft. Used workflows reject the action
  with an explanation and a recommendation to use New Version. Closed, archived
  and reset-to-Draft claims continue to protect the workflow through their snapshots.
- Archive now takes the same workflow lock as initial submission. Form and bulk
  Unarchive share restoration logic and retain administrator-only access.
- Added English/Arabic rejection feedback and backend/browser regression coverage.
