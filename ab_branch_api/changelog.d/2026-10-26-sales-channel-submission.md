Commit: 15e41087b65db7e9f95553105f87ea091b585894
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T15:29:00+03:00
Original commit subject: ab_branch_api/- Advertises whether the branch supports delivery notifications. - Accepts delivery consent and delivery instructions from callcenter.

User-facing changes:
- Advertise optional delivery notification support and accept delivery consent and instructions.

Files changed:
- ab_branch_api/README.md
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-10-20-callcenter-parity.md
- ab_branch_api/models/branch_api.py

Current changes before commit:
- Accept sales_channel_id and preserve missing allowlisted header/line values as technical metadata without installing optional branch addons.
- Keep source Many2one/Many2many IDs as arrays with source database UUID and related-model context; preserve typed scalar and empty values.
- Restrict metadata reads/exports to Settings administrators and permit writes only through the private receiver path.
- Validate the versioned descriptor context; preserve native relation resolution, pricing safeguards, branch scope, and immutable retry payloads.
- Require legacy rejected requests lacking necessary source IDs to use the existing correction/revision workflow; corrections replace stale metadata.
- Document receiver-first deployment and add English/Arabic messages in both supported Arabic translation files.
- Bump Branch API to 19.0.5.5.6. No optional addon installation, production upgrades, or live invoice posting performed.

Files changed:
- ab_branch_api/README.md
- ab_branch_api/__manifest__.py
- ab_branch_api/changelog.d/2026-10-26-sales-channel-submission.md
- ab_branch_api/i18n/ar.po
- ab_branch_api/i18n/ar_001.po
- ab_branch_api/models/__init__.py
- ab_branch_api/models/branch_api.py
- ab_branch_api/models/sale_metadata.py

Validation:
- 30 receiver checks passed on a disposable branch clone without ab_sales_channel, including ordinary-user access, guarded retries, corrected revisions and branch isolation.
- Targeted ab_branch_api upgrade, Arabic PO format checks, ar_001 runtime translation and rendered-view visibility checks passed.
- Stock/customer external reads and posting were mocked. The existing return-header null-store schema issue remains unrelated to this change.
- Evidence: /tmp/metadata_qa_20261026/receiver-test.log and verification.json. Disposable databases/configurations removed; production unchanged.
