# Module update committed — 9dc09536

- Commit: `9dc0953696f615676b9a0747d28d23d128652b79`
- Author: Alhassan Hossny
- Date: 2026-11-09T14:04:35+02:00
- Original subject: ab_crm_sales_workspace/feat: group customer streams and refine chatter controls

Group authorized conversations by customer, provide reviewed customer linking, retain historical chronology without new alerts, filter saved replies by preference language, refine latest-message and location controls, and render message actions above the composer.

Commit preparation checks: changed Python, XML, JavaScript and JSON syntax; SCSS compilation; all six Arabic catalog format checks; addon manifest paths and ownership metadata; and `git diff --check` passed. Earlier Odoo/gateway suite results remain recorded in the existing validation reports. Their temporary logs and test environment were unavailable in this session; those suites were not rerun for this commit. No live database upgrade or service restart was performed.

The message-menu fix was separately verified using the actual component in a browser fixture at two widths in LTR and RTL, including keyboard controls and composer overlays.

Files changed:
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/alerts.py`
- `models/customer_streams.py`
- `models/saved_reply.py`
- `models/workspace.py`
- `static/src/composer.js`
- `static/src/composer.xml`
- `static/src/location.scss`
- `static/src/workspace.js`
- `static/src/workspace.scss`
- `static/src/workspace.xml`
- `static/tests/composer.test.js`
- `static/tests/message.test.js`
- `tests/test_workspace.py`
