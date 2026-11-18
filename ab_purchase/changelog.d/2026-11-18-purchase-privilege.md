# Purchase access setting — 2026-11-18

## Recent commit

- Commit: `9face01308ca1494950a2b73047b1812c730659d`
- Author: Hossam Elsheikh
- Date: 2026-11-17T15:15:48+02:00
- Original commit subject: ab_purchase/FIX: validate submissions and prevent duplicate stock entries
- Retains purchase submission validation and duplicate stock-entry protections.

Files changed:

- `ab_purchase/changelog.d/2026-11-15-purchase-store-view.md`
- `ab_purchase/changelog.d/2026-11-17-access-rollback.md`
- `ab_purchase/i18n/ar.po`
- `ab_purchase/i18n/ar_001.po`
- `ab_purchase/models/ab_purchase_header.py`
- `ab_purchase/models/ab_purchase_je_header_delegate_common.py`
- `ab_purchase/models/ab_purchase_notice_header.py`
- `ab_purchase/models_accounting/ab_purchase__header_inherit.py`
- `ab_purchase/models_accounting/ab_purchase__notice_inherit.py`
- `ab_purchase/views/ab_purchase_header.xml`
- `ab_purchase/views/ab_purchase_notice_header.xml`

## Current changes before commit:

- Show all six existing purchase roles under one Abdin Purchase access setting.
- Retain the original Manager privilege and move the other five roles into it; remove the duplicate privilege definition through the normal module upgrade.
- Preserve group identities, user memberships, implied groups, ACLs and record rules. No model or workflow changes and no new or changed user-facing text.

Files changed:

- `ab_purchase/security/security_groups.xml`
- `ab_purchase/changelog.d/2026-11-18-purchase-privilege.md`

## Verification and deployment

- Targeted `ab_purchase` upgrade passed first on an isolated clone, then on `main19` serving port 4069. Odoo removed the obsolete privilege through its normal upgrade cleanup.
- Headed Playwright verified one purchase access dropdown containing all six existing roles on both databases; no user record was saved.
- Live before/after comparisons matched all 66 group definitions (excluding privilege assignment), 8,385 memberships, 65 inheritance links, 604 ACLs, 157 record rules and 169 rule/group links.
- Existing labels and translations are unchanged; no new user-facing strings were introduced.
- Test clone, server, config and copied filestore removed; main19 remained healthy. Private verification evidence and a pre-upgrade backup are retained in `/tmp/purchase-privilege-merge-20261118`.
- No commit or push performed.
