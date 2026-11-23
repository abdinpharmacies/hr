# Two-server QA fixes

## 149fb44eebf01cf47e9abe39fc9fa6e6b26e1bfe

Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_website/feat: group orders into receive-only customer conversations

- Preserve original website order evidence in customer conversations.
- Historical receive-only and phone-grouping expectations are superseded by the later chat and verified-identity changes.

Files changed:
- README.md
- __manifest__.py
- changelog.d/2026-11-16-customer-conversations.md
- changelog.d/2026-11-16-link-candidate-locks.md
- changelog.d/2026-11-16-receive-only.md
- i18n/ar.po
- i18n/ar_001.po
- models/adapter.py
- security/ir.model.access.csv
- security/security.xml
- static/src/order.xml
- tests/contact_group_concurrency.py
- tests/test_adapter.py
- tests/test_contact_groups.py
- tests/test_pos.py

## Current changes before commit:

This entry describes the QA follow-up; earlier uncommitted chat implementation remains documented separately.

- Preserve the validated employee-session context when creating agent-uploaded attachments; keep actor, target, branch/company and attachment guards in force.
- Advance the receiver version to 19.0.1.15.0.
- Reconcile older tests with verified identity ownership, explicit reply/media/read targets and lifecycle information items.
- Verify the upload allow/deny path, including rejection without partial attachments for a forged employee session.
- Preserve native POS draft/payment evidence while testing the now-supported agent replies.
- Add no runtime source strings; preserve both Arabic catalogs.

Files changed:
- __manifest__.py
- controllers/adapter.py
- tests/test_adapter.py
- tests/test_contact_groups.py
- tests/test_pos.py
- changelog.d/2026-11-23-two-server-qa.md
