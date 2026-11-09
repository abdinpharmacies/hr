# Approved templates follow the user's preference language

Previous module commit: `e7ca6fd69333f9f3054274b80bd0c3d736e7e4ea`
Author: Alhassan Hossny
Date: 2026-11-09T10:41:10+02:00
Original subject: ab_crm_whatsapp_workspace/docs: document integration and release changes

Changes included in implementation commit `94d7f960`:

- Filter the Chatter and administrator sending pickers to the user's preference language.
- Match provider language variants by base language while retaining account/template authorization.

Files changed:
- `__manifest__.py`
- `models/workspace.py`
- `models/service.py`
- `tests/test_bridge.py`
- `changelog.d/2026-11-09-template-preference-language.md`

Validation: targeted upgrade on `callcenter_dual_test_20261109`, ports 5069/5072, four template-language/authorization tests passed; both Arabic catalogs pass format checks. Live upgrade/reload is pending.
