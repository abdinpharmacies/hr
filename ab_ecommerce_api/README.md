# Abdin eCommerce API

Odoo 19 customer API for Flutter and other HTTP clients. This addon depends on
`ab_ecommerce_storefront` and reuses its inventory holds, checkout idempotency,
authentication challenges, customer pricing and prescription workflow.

## Documentation and authentication

Install the **Abdin eCommerce API** app, then open **Storefront API** from Odoo's
app menu as a System Administrator. **API Docs** embeds the interactive Swagger
playground inside Odoo; **Quick start** explains customer sign-in, authorization,
Flutter headers and token expiry. The workspace offers OpenAPI download, reload
and a standalone documentation link. Its shell and guide support English/Arabic.

The original `/api/v1/docs` route remains available. The bundled Swagger UI
5.33.1 runs locally without a CDN or an external specification validator.
Download `/api/v1/openapi.json` for Postman or OpenAPI tooling. Its request
schemas come from the same definitions used for server input validation.
Swagger's own controls and the developer specification use English; module
pages and customer error messages support English and Arabic.
Swagger styles are isolated from the backend, and its assets load only when
the documentation opens. Reloading or leaving the workspace clears the token
from the documentation page. Changing between Docs and Quick start keeps it
in memory. Requests affect the current database, not a sandbox automatically.

Customer API routes never use the documentation administrator's cookie. Call
`POST /api/v1/auth/login`, then send `Authorization: Bearer <access_token>`.
Only portal customers are eligible. Employee and administrator credentials
cannot obtain customer API tokens. Native Odoo API keys are not accepted.

Access tokens expire after 15 minutes. Refresh tokens have an absolute 30-day
lifetime and rotate on every refresh, invalidating the preceding pair. Serialize
refresh requests in Flutter. Reusing an already rotated refresh token revokes
the related device session, including its latest access token. Customers can
list and revoke their own device sessions or sign out everywhere. Logout revokes
both tokens. Password changes, account archival and loss of portal/company access
invalidate the session. Tokens are stored as SHA-256 hashes and must be kept in
device secure storage. Each customer can have at most 20 active device sessions
per website; issuing another session revokes the least recently used sessions.

When password login returns `verification_required`, approve the existing
Telegram device challenge and call `/auth/verify-device`. Other MFA schemes and
Google sign-in use the browser flow:

1. Generate a random PKCE verifier of 43–128 URL-safe characters on the device.
2. Compute its SHA-256 digest and base64url encode it without padding.
3. Send that `code_challenge` to `/auth/browser/start`.
4. Open the returned same-origin `authorization_url` in the system browser.
5. Complete the existing website login, Google OAuth or MFA and explicitly
   authorize the app. Never put an access token into a redirect URL.
6. Poll `/auth/browser/token` every 10 seconds with `flow_token` and the original
   `code_verifier`. It returns `authorization_pending` until approved, then the
   token pair. The flow expires in five minutes and can be redeemed only once.

Email registration respects Odoo's signup setting. Phone registration reuses
Telegram phone verification. Recovery preserves the existing channel queues,
expiry and attempt limits. Configure those channels in the storefront before
using them; this addon does not create provider credentials or cron jobs.

## Customer operations

- Catalog: configuration, homepage, banners, published products and variants,
  category and brand filters, search, offers, categories and brands.
- Account: profile, delivery addresses, country and state lookups.
- Cart: add variants, set quantities, coupons, eligible reward choices and
  warehouse-scoped inventory holds.
- Checkout: owned shipping address, compatible carriers and rates, compatible
  payment providers/methods, checkout validation and idempotent payment creation.
- Orders: owned order details, delivery progress and posted invoice downloads.
- Prescriptions: private image upload, idempotent submission, status and images.
- Wishlist, browsing history, public branch directory, contact messages and
  links to the existing company/policy pages.

Guests can browse; cart and checkout require a customer account. Carts are
device-session scoped and survive token refresh. The website browser cart is
independent. Product IDs in catalog lists are template IDs; cart items and
wishlist mutations take variant IDs from `variant_ids` or `variants`.
The API exposes customer actions, not generic model CRUD or employee operations.
Email/phone identity changes and trusted-device management stay in the existing
account-security website workflow linked by `/config`. There is no separate
zero-total order confirmation endpoint; checkout currently uses provider payments.

JSON success responses are wrapped in `data`; failures use
`error.code` and translated `error.message`. Use `?lang=ar` or
`Accept-Language: ar` for Arabic. Supported pagination returns `items`, `page`,
`limit` and `has_more`, with at most 50 items per page. Unknown input fields,
non-finite quantities and client-provided prices are rejected. Private response
data is not cacheable. A failed mutation rolls back its business changes.
`POST /cart/items` requires a unique 16–128 character `Idempotency-Key` header.
Repeating the same key and body returns the first result without adding quantity
again; reusing the key with different content returns HTTP 409.

## Checkout sequence

1. Create/select a delivery address, then add product variants to the cart.
2. Set `/cart/address`, query `/cart/delivery-methods`, and select a method when
   the order has deliverable products. Taxes, prices and shipping are server-owned.
3. Apply an optional coupon. Query `/cart/rewards` when a reward choice is needed.
4. Query `/cart/payment-methods` and call `POST /cart/checkout` with `{}`.
5. Send the resulting `idempotency_key`, `provider_id` and `payment_method_id`
   to `/orders/{order_id}/payment`. Retrying the same request reuses the transaction.
6. Complete the provider's returned processing flow. Depending on the provider,
   its redirect form may need a WebView or its official SDK. Poll the order's
   `payment_state`; an app redirect alone never proves payment success.

Payment callbacks and post-processing remain owned by Odoo/payment providers.
This addon does not implement or emulate a gateway, mark client-reported payments
paid, or bypass authoritative stock reservation. Existing E-Plus-backed items
that cannot be authoritatively reserved remain blocked by storefront rules.
Checkout returns HTTP 422 when those business requirements are not met.

For prescriptions, first request `/prescriptions/submission`. Submit its key,
an owned `address_id` and `prescription_image` as multipart data to
`/prescriptions`. JPEG, PNG and WebP images are validated by the existing image
reader, up to 8 MiB and 25 million pixels. Duplicate requests reuse the original
submission; changed payloads with the same key are rejected. Uploaded prescriptions
remain in the pharmacy review workflow.

## Installation and operations

Put the addon next to `ab_ecommerce_storefront` on the Odoo addons path. Install
only `ab_ecommerce_api` and its declared dependencies on the intended database.
For a clean database the existing `ab_website` setup requires `ar_001` to be
loaded first, for example using `--load-language=ar_001` during initialization.

Use HTTPS outside loopback development. Keep PostgreSQL private, select a fixed
database with `dbfilter`, disable database listing, and configure trusted reverse
proxy headers correctly. There is no wildcard CORS policy. Flutter native
clients do not require CORS; a separate Flutter Web origin needs an explicitly
reviewed origin configuration. Use the same origin as the configured website.

No external database credentials or general model access belong in the app.
API rate limits supplement reverse-proxy request and upload limits. Documentation
is restricted to System Administrators. Do not publish test account credentials.

Development tests live in `tests/`; runtime archives exclude them and caches.
Run only `/ab_ecommerce_api` tests against a dedicated database on alternate
ports, with workers and cron disabled. Never upgrade `base` or stop the user's
running Odoo merely to validate this module.

## Scope of verification

Automated coverage and the local tryout use a dedicated database and a test
transfer provider. Real Google credentials, Telegram/email delivery, live
shipping adapters and real gateway callbacks require environment-specific
integration checks before production rollout. Policy content remains owned by
the existing website pages. No production deployment is performed by installation
into the isolated development database.
