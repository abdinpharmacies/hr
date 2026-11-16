# WhatsApp authentication implementation and validation

Activation update (2026-11-16): WhatsApp is now active locally; see [live activation and pilot result](whatsapp-authentication-activation.md).

Date: 2026-11-15. Changes are additive and are not activated on the live website.

## Source changes

- Ecommerce: new `ab_storefront_whatsapp_auth` addon for independent one-code phone
  signup and verified-phone password recovery, encrypted jobs, leased delivery,
  dedicated Bearer exchange, company/website/sender authorization, inherited views
  and 71 terms translated in both Arabic catalogs.
- Ecommerce: new optional `ab_ecommerce_api_whatsapp` addon. The main WhatsApp addon
  does not depend on or install the customer API.
- Gateway: new `app/auth_config.py`, `app/auth_worker.py` and `app/auth_receiver.py`,
  mocked tests, disabled deployment examples and configuration documentation.
- No existing application source file was edited. Existing unrelated AGENTS.md and
  documentation changes were preserved. No live configuration, database upgrade,
  service restart or provider send was performed.

Either Telegram or WhatsApp independently verifies the phone. WhatsApp does not
create a Telegram identity or require Telegram contact sharing or a second signup
OTP. Existing password handling and native MFA remain responsible for sign-in.

## Passed verification

The broad combined Odoo run selected 102 test methods: 98 passed and four existing
checkout fixture errors are recorded below. All 76 selected authentication tests
passed, including the 25 new core tests, three optional API tests, existing
Telegram/email/first-sign-in tests and two Google account tests. The remaining 22
passing tests cover native checkout reservations and access controls.

- Database: `wa_auth_test_20261115`, isolated dedicated configuration and dbfilter.
- Final authentication-only run: 76 passed, zero failures/errors;
  `/tmp/wa-auth-authentication-final.log`. Broad log: `/tmp/wa-auth-all-final.log`.
- Targeted upgrades: `ab_ecommerce_storefront`, `ab_storefront_whatsapp_auth`,
  `ab_ecommerce_api_whatsapp`; HTTP/gevent ports 5069/5072, workers/cron zero.
- Additional HTTP runs used 5159/5162 while the separate fresh install used 5069.
- Browser test: WhatsApp button order, phone/email visibility and initialized JS.
- HTTP tests: signup through password authentication; Arabic rendering; generic
  recovery acknowledgement; CSRF rejection; native Bearer key; HTTPS requirement;
  forged source rejection.
- Optional API end-to-end: signup start/code/complete, WhatsApp recovery, password
  reset, invalidation of the issued API session, default and explicit Telegram.
- Core security tests: no direct worker ORM reads; denied portal/other-worker and
  company scope; browser/purpose binding; expired/replayed/exhausted proofs;
  archived/duplicate identities; resend, cancellation, revoked worker, configuration
  changes, one-use dispatch, unknown send outcome and monotonic receipts.
- Concurrency check: two independent database transactions yielded exactly one
  account and one rejected completion. Reproducible helper:
  `ab_storefront_whatsapp_auth/tests/check_concurrency.py`.
- Clean installation: `wa_auth_clean_20261115`, only the core new addon requested,
  `--load-language=ar_001`; all 20 business/security tests passed, zero failures or
  errors. Log: `/tmp/wa-auth-clean.log`. English is explicitly enabled by HTTP test
  fixtures. The existing `ab_website` installation requires Arabic to be loaded.
- Gateway: 126 passed, one skipped across authentication, existing provider,
  Website, WhatsApp reception and SQLite storage tests. The skipped test requires
  a dedicated PostgreSQL gateway test connection. External provider calls were mocked.
- Both PO files passed `msgfmt --check-format`; Python AST, XML parsing, manifest
  dependencies/imports and production archive contents were checked.

Odoo's separate statistics include setup/teardown counts; the counts above use the
actual `post-tests`/result method totals. Earlier fixture, proxy-header, port and
browser-readiness issues were corrected before the final runs.

## Existing checkout fixture errors

Four existing tests fail in `TestStorefrontReservations.link_eplus_stock()` before
exercising their intended scenario:

- `test_completed_eplus_sync_uses_odoo_stock_for_reservation`
- `test_external_stock_cannot_confirm_without_reservation`
- `test_failed_eplus_sync_does_not_authorize_checkout`
- `test_other_warehouse_eplus_sync_does_not_authorize_checkout`

The helper creates a website product with `list_price=10`, creates a linked
`ab_product` without the matching price, then links them. The existing
`ab_website_sale_product/models/product_template.py::_check_ab_product_base_price`
correctly raises the price-consistency validation error. The stack contains the
existing product/catalog modules; WhatsApp code is not involved. Those existing
fixtures and pricing logic were left unchanged, as requested. This means the broad
checkout run is not fully green.

## Activation and remaining live checks

WhatsApp remains disabled by default. Verify approved Arabic/English AUTHENTICATION
copy-code templates and sender permissions, configure the dedicated service user,
private allowlists and signed receiver wrapper, then perform an explicitly
authorized test-number pilot. No live Meta template availability or OTP delivery
was tested. Live Google OAuth and native MFA enrollment were not exercised; their
existing mechanisms were retained. There is no new-device WhatsApp MFA or phone-change flow.

See [gateway setup](../crm_messaging_gateway/AUTHENTICATION.md) for activation,
monitoring and rollback. Production archives are in `/tmp/wa-auth-artifacts` and
exclude tests, caches and private configuration. Test databases and logs are kept
for review. Temporary servers were stopped and their validation ports released.
