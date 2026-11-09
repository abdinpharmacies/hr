# Templates follow the user's preference language

Previous module commit: `d5d7bd8fa7febb0defe905e9670dfb1b86415cfb`
Author: Alhassan Hossny
Date: 2026-11-09T10:41:10+02:00
Original subject: ab_crm_sales_workspace/docs: document chatter updates and validation

Changes included in implementation commit `9dc09536`:

- Filter the Templates picker to the language selected in user preferences; Arabic variants share Arabic templates.
- Retain the existing EN/AR-tagged saved replies without a data migration, and store the preference language for new replies.
- Preserve an existing template's language when it is renamed; retain branch/session authorization.
- Add the Language field label to both Arabic catalogs.

Files changed:
- `__manifest__.py`
- `models/saved_reply.py`
- `tests/test_workspace.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-09-template-preference-language.md`

Validation: targeted upgrade on `callcenter_dual_test_20261109`, ports 5069/5072, four template-language/authorization tests passed; both Arabic catalogs pass format checks. Live upgrade/reload is pending.
