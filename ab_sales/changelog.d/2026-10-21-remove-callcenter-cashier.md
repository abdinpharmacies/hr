Commit: c443ec4afd7aef406da88a59aea8831387c706a2
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T16:54:35+03:00
Subject: ab_sales/fix ui error

User-facing changes:
- Restore the submit-error dialog used when sending a bill fails.

Files changed:
- ab_sales/changelog.d/2026-10-20-submission-error-dialog.md
- ab_sales/static/src/pos/pos_action.js

Current changes before commit:
- Remove the callcenter Cashier security group and its administrator implication.
- Keep all sales, returns and callcenter groups and access rules unchanged.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_sales/security/groups_sales.xml
