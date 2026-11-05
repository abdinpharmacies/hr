
Current changes before commit:

- Preserve employee return-session context across native return UI entry points.
- Maintain workflow.md for the split, API ownership, enrollment, transaction lifecycle, recovery and clean-pilot rollout.
- Maintain Arabic catalogs and existing security boundaries.

Files changed:

- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-11-05-role-split.md
- ab_employee_access_sales/models/ab_sales_return_ui_api_inherit.py
- ab_employee_access_sales/workflow.md

Recent relevant commit:

- Commit: 0a5577973fd5922dcaef7fbf6db422e6991e5b6c
- Author: emadco88
- Date: 2026-10-29T09:49:15+03:00
- Original subject: ab_employee_access_sales/ FIX return
- Existing module baseline retained outside the role-split/native adapter changes.

Files changed:

- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-10-29-return-login-before-draft.md
- ab_employee_access_sales/models/ab_sales_return_ui_api_inherit.py
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_patch.js
- ab_employee_access_sales/tests/test_ab_employee_access_sales_api.py

Validation: fresh isolated central/branch installation; isolated callcenter upgrade; split role registry checks; native API sale/settlement/pending return without local stock movements; HTTP authentication, scope, ordering, duplicate and changed-content checks; callcenter native/legacy identity checks; snapshot watermark/cache-zero regression. Test harnesses are retained under /tmp/split_* and are not shipped in addons. Live databases were not upgraded.
