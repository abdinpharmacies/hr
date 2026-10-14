## 3db5d596c9429ff082c3fe9b0466692b945f788f - emadco88 - 2026-07-28

Original commit subject: INIT commit pos19

User-facing changes:
- Provide the shared E-Plus connector with connection validation and reconnect support.

Files changed:
- ab_eplus_connect/__init__.py
- ab_eplus_connect/__manifest__.py
- ab_eplus_connect/models/__init__.py
- ab_eplus_connect/models/ab_eplus_connect.py
- ab_eplus_connect/models/check_port_mssql.py
- ab_eplus_connect/models/ping_host.py

## Current changes before commit:

- Add a private bounded POS read policy (3-second connection/validation and 5-second query limits, no replay) without changing the public connector signature or ab_branch_api.
- Apply validation/query timeouts to the actual ODBC connection before cursor creation and pass login timeouts to the driver.
- Isolate refresh pool entries, close and evict failed reads even through connector overrides, and reject incompatible reused transactions without modifying them.

Files changed:
- ab_eplus_connect/changelog.d/2026-10-14-balance-refresh.md
- ab_eplus_connect/models/ab_eplus_connect.py
