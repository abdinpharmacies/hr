Current changes before commit:

- Align the branch-configuration instructions with the current system-parameter namespace and Operations buttons.
- Document automatic enrolled-store access for branch sales users without individual native-inventory roles or store assignments.
- Document automatic connection preparation on POS branch selection, including pre-PIN setup, atomic first snapshots, failure handling and preserved employee checks before periodic delivery.
- Preserve the distinction between branch sales permissions and central API-user inventory authorization. Central runtime code and permissions are unchanged.

Files changed:

- ab_central_sync/workflow.md
- ab_central_sync/changelog.d/2026-11-16-branch-access-workflow.md

Verification:

- Compared the connection-configuration and branch-user-access sections with the branch workflow; both sections match.
- Documentation only; no central upgrade, security change or inventory operation was performed for this change.

Recent relevant commit:

- Commit: ff8b0da3729e30690addf06a3b1c2c3ada2af19f
- Author: hager yasser
- Date: 2026-11-10
- Original subject: docs(ab_central_sync): document inventory workflow
- Document central inventory ownership and branch synchronization procedures.

Files changed:

- ab_central_sync/changelog.d/2026-11-10-branch-replication-independence.md
- ab_central_sync/changelog.d/2026-11-10-inventory-workflow-and-uom-proposal.md
- ab_central_sync/workflow.md
