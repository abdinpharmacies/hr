# 19.0.7.1.0 — Four generic security roles

- Keep Workflow Participant, Secretarial, Reviewer, and Administrator with their
  existing XML IDs. Department responsibilities remain configured on stages.
- Migrate effective department members, including inactive users, to direct
  Participant membership before removing the five department groups and their
  obsolete ACLs/rules. Unexpected external dependencies stop the upgrade.
- Participants read complete workflows, history, and documents for assigned
  claims, with read-only supplier access. Approval/editing remains stage-scoped;
  company restrictions and Reviewer restrictions remain enforced.
- Upgrade existing dynamic databases in place; do not uninstall/reinstall or
  reimport claims. No business model or public API changes.
- Historical transfer bundles map department roles to Participant. The importer
  requires a 19.0.7.1.0 target and does not recreate deleted groups.
