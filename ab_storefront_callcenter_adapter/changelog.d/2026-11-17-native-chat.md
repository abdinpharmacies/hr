# Native order and floating chat

Baseline: b0095b65 — Alhassan Hossny — 2026-11-17 — ab_storefront_callcenter_adapter/fix: allow website selection on new endpoints

Current changes before commit:
- Gate order composers and direct customer posts on initial-order acknowledgement, independently of later revisions.
- Use native order chatter as the authoritative compatibility-page history; transactionally capture new customer comments only.
- Bridge native Live Chat first inputs and exact-session replies using source-scoped identities and an offline-capable dedicated operator.
- Add explicit chat/sending switches, v2 deduplicated native replies, company isolation and guest/login-boundary tests.
- Declare native Live Chat dependencies; preserve legacy v1 order intake and block legacy reply submission; maintain both Arabic catalogs.

- Derive website scope for native non-website messaging routes and use the native session language for queued acknowledgements; validate both live-test fixes in isolated regressions.

- Verify that reloading storefront channel XML preserves the configured bridge operator and service fetch eligibility; 22 isolated adapter checks pass.

Files changed:
- `ab_storefront_callcenter_adapter/README.md`
- `ab_storefront_callcenter_adapter/__manifest__.py`
- `ab_storefront_callcenter_adapter/changelog.d/2026-11-17-native-chat.md`
- `ab_storefront_callcenter_adapter/controllers/chat.py`
- `ab_storefront_callcenter_adapter/i18n/ar.po`
- `ab_storefront_callcenter_adapter/i18n/ar_001.po`
- `ab_storefront_callcenter_adapter/models/__init__.py`
- `ab_storefront_callcenter_adapter/models/adapter.py`
- `ab_storefront_callcenter_adapter/models/chat.py`
- `ab_storefront_callcenter_adapter/security/ir.model.access.csv`
- `ab_storefront_callcenter_adapter/security/security.xml`
- `ab_storefront_callcenter_adapter/static/src/chat.js`
- `ab_storefront_callcenter_adapter/tests/test_adapter.py`
- `ab_storefront_callcenter_adapter/views/views.xml`
