# Commands and Local Environment

Verified 2026-09-24 against [Odoo 19 CLI](https://www.odoo.com/documentation/19.0/developer/reference/cli.html),
[testing](https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html),
and local `odoo-bin server --help` / `odoo-bin i18n export --help`.
No database installation/upgrade was performed while building this profile.

Observed interpreter: `/opt/odoo19/venv19/bin/python`; server:
`/opt/odoo19/server/odoo-bin` reports Odoo 19.0. Config
`/opt/odoo19/odoo19.conf` exists, uses HTTP 4090/gevent 8072, log
`/opt/odoo19/odoo.log`, and addons `/opt/odoo19/server/addons,/opt/odoo19/custom-addons`.
That is NOT this ecommerce checkout. Verify/override addons-path deliberately;
do not accidentally test a different copy of the same module. Inspect current
processes/config metadata without printing database passwords or tokens.

Source example database `abdin_replica19` is not automatic authorization or proof
of availability. Select the actual authorized development DB. Port 5069/5072
was free when inspected; recheck with `ss -ltnp` each run. Never kill existing
processes to free validation ports. Use a dedicated DB/filestore/config when
concurrent workers or integrations could affect the test.

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin server \
  -c "$ODOO_CONFIG" -d "$ODOO_TEST_DB" \
  --addons-path="$ODOO_ADDONS_PATH" \
  -u "$ODOO_MODULE" --stop-after-init \
  --workers=0 --max-cron-threads=0 \
  --http-interface=127.0.0.1 --http-port=5069 --gevent-port=5072 \
  --logfile=/tmp/odoo-module-validation.log
```

Set variables explicitly from verified local paths; preserve required addon roots
and avoid duplicate module copies. Use `-i "$ODOO_MODULE"` for a fresh install.
Add `--test-enable --test-tags "/$ODOO_MODULE"` for standard module tests, or
`--test-tags "*/$ODOO_MODULE"` when intentionally including nonstandard tags.
`--test-tags` itself enables tests. Verify at_install/post_install execution and
actual test counts; no selected tests is not a pass. Odoo 19 does not load demo
data by default; do not add demo files or pass `--with-demo`.

`--gevent-port` is unused in threaded mode, but specify both ports to preserve
the project's isolation convention. `--no-http` is suitable only for checks that
do not need browser/tour HTTP. Cron=0 does not suppress every possible external
side effect: use neutralized test config and mocks, not production endpoints.

Use `TransactionCase` for ORM tests (savepoints/rollback) and `HttpCase.start_tour`
for browser integration. Follow the installed HOOT helpers/mock server and
existing test bundles for Owl/JS. Python tests need imports in `tests/__init__.py`.
Temporary dev tests may exist, but production artifacts exclude test-only code
and manifest references to excluded files. Keep reproducible CI/test evidence.

Final checks: targeted registry/view load, security matrix, affected assets/UI,
both Arabic catalogs, manifest imports/data order, no demo/hooks/caches introduced,
and accurate changelog. Record exit status and log test summary. Zero console
output can occur with logfile configuration and is not evidence of test coverage.
