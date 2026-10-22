# Storefront API change log

## Current changes before commit:

Author: Mohamed Fawzy
Date: 2026-10-21
Commit: Not committed; this is a new module with no prior module history.

- Add 62 customer HTTP operations covering authentication, device sessions, catalog, accounts,
  carts, checkout, orders, invoices, prescriptions, wishlist and public content.
- Issue hashed, customer-only bearer credentials with 15-minute access expiry,
  absolute 30-day refresh expiry, rotation, reuse detection, family revocation,
  device-session management and credential invalidation.
- Preserve existing MFA using device challenges and explicit browser consent
  with PKCE. Scope private data to the customer, website and company.
- Reuse native pricing, inventory reservation, promotions, checkout idempotency,
  payment and prescription business logic without direct external database access.
  Require replay-safe idempotency keys when adding cart items.
- Add an administrator-only Odoo workspace with embedded Swagger UI, a quick-start
  guide, locally bundled assets and generated OpenAPI 3.0.3 documentation.
- Add English and Arabic workspace strings, module pages and customer errors.
- Validate 41 automated tests covering allowed and denied access, business workflows,
  replay safety, input validation, translation, documentation authorization and
  responsive English/Arabic browser rendering.

Files changed:

- `ab_ecommerce_api/__init__.py`
- `ab_ecommerce_api/__manifest__.py`
- `ab_ecommerce_api/README.md`
- `ab_ecommerce_api/changelog.d/current.md`
- `ab_ecommerce_api/controllers/__init__.py`
- `ab_ecommerce_api/controllers/api.py`
- `ab_ecommerce_api/controllers/common.py`
- `ab_ecommerce_api/controllers/docs.py`
- `ab_ecommerce_api/controllers/schemas.py`
- `ab_ecommerce_api/models/__init__.py`
- `ab_ecommerce_api/models/api_session.py`
- `ab_ecommerce_api/security/ir.model.access.csv`
- `ab_ecommerce_api/security/record_rules.xml`
- `ab_ecommerce_api/views/docs.xml`
- `ab_ecommerce_api/views/menus.xml`
- `ab_ecommerce_api/i18n/ar.po`
- `ab_ecommerce_api/i18n/ar_001.po`
- `ab_ecommerce_api/static/lib/swagger-ui/docs-init.js`
- `ab_ecommerce_api/static/lib/swagger-ui/README.md`
- `ab_ecommerce_api/static/lib/swagger-ui/LICENSE`
- `ab_ecommerce_api/static/lib/swagger-ui/swagger-ui-bundle.js`
- `ab_ecommerce_api/static/lib/swagger-ui/swagger-ui.css`
- `ab_ecommerce_api/static/src/workspace.js`
- `ab_ecommerce_api/static/src/workspace.xml`
- `ab_ecommerce_api/static/src/workspace.scss`
