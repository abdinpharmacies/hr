# ab_oms_website_adapter

No prior commits exist for this new module.

Current changes before commit:

- Add Website OMS Adapter with module-owned access control and branch/company safeguards where applicable.
- Provide English UI and Arabic catalogs for ar and ar_001.
- Preserve existing addon files and business-operation ownership.
- Fix the OMS event list/form and inherited website/order views failing with a `NoneType` concatenation error in Odoo XML development mode by expanding compact XML architectures with leading whitespace; preserve XML IDs, UI strings, and view structure.

Author: Alhassan Hossny

Date: 2026-11-03

Files changed:

- `__init__.py`
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/website.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `security/security_groups.xml`
- `static/description/icon.png`
- `views/integration.xml`
- `views/menus.xml`
- `views/views.xml`
- `changelog.d/2026-11-03-initial-crm-oms.md`

Validation of the XML view repair (2026-11-03):

- Reproduced the development-mode loader failure for all four view records before editing.
- Verified both changed XML files retain identical structure and text after whitespace normalization.
- Backed up `e_commerce` and upgraded only `ab_oms_website_adapter`; upgrade exited successfully without ERROR/CRITICAL log entries, with HTTP/cron/queue workers disabled.
- Passed 19 runtime checks: four file-based view loads, eight English/Arabic combined views, two portal inheritance checks, translated action, administrator read access, public read denial, manual event creation denial, and OMS remaining disabled.
- Live HTTP validation passed: administrator login, event action, eight English/Arabic view responses, homepage, shop, and Arabic shop; no new ERROR/CRITICAL entries appeared in the server log during these requests. The existing server process stayed running.
- Both Arabic catalogs pass `msgfmt --check-format`; no user-facing strings changed.
- No Python, permission, order-processing, inventory, or pricing logic changed. External OMS exchange was not exercised.
