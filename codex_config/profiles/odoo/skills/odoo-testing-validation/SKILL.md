---
name: odoo-testing-validation
description: Validate Odoo changes with focused Python, JS/Owl, tours, targeted install/upgrade, security, translation and packaging checks.
---

Read [commands and environment](references/commands.md). Inspect interpreter,
config, addons paths, database purpose and occupied ports. Never stop/restart the
user's PyCharm-managed server to free ports. Ports do not isolate a database:
use an authorized dedicated development DB/replica without concurrent production work.

1. Inspect changed Python/XML/manifests, imports, dependencies and XML IDs.
2. Run at least one changed business-rule test and an access/record-rule test when
   applicable. Use `TransactionCase`, `with_user`, allowed/denied actors and mocked
   external services. No demo files. Record test counts, not just successful exit.
3. For frontend changes use the existing HOOT/web helpers and mock server; for
   browser/server workflows use `HttpCase.start_tour` when warranted. Browser
   tests need HTTP, so do not combine them with `--no-http`.
4. Test a targeted fresh install (`-i`) or upgrade (`-u`) with module-scoped
   `--test-tags`. Never `-u base`. Use unused alternate ports, normally 5069/5072,
   `--workers=0 --max-cron-threads=0`.
5. Review exit status AND configured logs for test execution, registry/view/asset
   errors, security outcomes and English/Arabic runtime behavior. Validate both
   translation catalogs with `msgfmt`.
6. Preserve tests in development/CI. Exclude `tests/`, fixtures, demos, caches and
   development-only migrations from the final runtime package; do not delete the
   user's development tests merely to package an addon.

Report commands, DB/ports, passed/failed counts and skipped checks with reasons.
A review-only validation pass assesses evidence without running live upgrades. Consult
[backup requirements](references/backups.md) for authorized mass-data operations.
