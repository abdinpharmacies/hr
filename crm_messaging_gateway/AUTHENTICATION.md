# WhatsApp storefront authentication

The authentication transport is additive. Existing gateway provider, staff composer,
Website worker and Odoo authentication sources remain unchanged. Install
`ab_storefront_whatsapp_auth` on ecommerce; install `ab_ecommerce_api_whatsapp` only
when the optional customer API is already needed. Neither addon is automatically installed.

Telegram and WhatsApp independently prove phone ownership. WhatsApp requires one
six-digit code before account creation and creates only a verified phone identity.
It does not create a Telegram identity or enable Telegram device protection.
Password login and native Odoo MFA continue through their existing mechanisms.

## Configuration and activation

Keep transport records and `auth.json` disabled until a pilot is authorized.
Create a dedicated internal ecommerce service user with only the
`WhatsApp Authentication Worker` group and the required website company. Do not
assign administrator or staff workspace roles. Generate a native Odoo API key for
that user. The worker has no direct ORM access to identities, challenges, delivery
payloads or authentication configuration. Its HTTPS Bearer endpoints authorize
source UUID, exact service user and website company before elevation.

In ecommerce Settings / WhatsApp Authentication, configure the website, service
user, Meta phone-number sender ID and approved English/Arabic authentication
copy-code template names and exact locale codes. Templates must already be approved
as AUTHENTICATION with a COPY_CODE button; the staff composer is unchanged.
Verify approval and sender permission with Meta before enabling. The implementation
passes the same OTP to the body and URL button parameters, as shown in the
[authentication template guidance](https://aws.amazon.com/blogs/messaging-and-targeting/send-whatsapp-business-messages-with-aws-end-user-messaging-social/).
Graph v26.0 remains enforced by the existing account configuration.

Copy `deploy/auth-config.example.json` to a private mode-0600 file and set
`CRM_AUTH_CONFIG` to its path. Replace the example source UUID with the ecommerce
transport's generated Source value. Each source pins an HTTPS origin, database,
dedicated API key, existing WhatsApp account code, sender ID and allowed
language-to-template mapping. Do not use staff or Website exchange credentials.
The existing `CRM_MESSAGING_CONFIG` still supplies Meta sender credentials.

For activation, select the additive receiver factory
`app.auth_receiver:create_app` instead of `app.main:create_app` in the existing
ASGI launch configuration, with `--factory`. Both expose the existing webhook URL.
The wrapper verifies Meta signatures and separates authentication statuses into
`auth:<source UUID>` gateway queues before the existing staff path. Use this receiver
before the first OTP pilot. No live service or configuration is changed by these files.
The example new systemd unit runs `python -m app.auth_worker` every second alongside
the other workers. Deployment paths in the example must match the actual runtime.

Enable the ecommerce transport, the private auth configuration, and existing
sender/global sending flags only after checking approved templates, receiver
routing and an explicitly authorized test-number pilot. No pilot message is sent
by installation or validation.

## Delivery and recovery invariants

The worker leases committed ecommerce jobs, obtains a one-use dispatch authorization,
and then reuses the existing provider sender. Codes remain encrypted in the Odoo
queue and are never copied to the gateway's durable storage or staff histories.
Dispatch consumes the lease even if its response is lost. Connect failures and
rate limits permit at most three attempts while the challenge remains valid.
Ambiguous network outcomes and expired dispatch leases become unknown and are
never resent automatically. Unused leases can be reclaimed. Provider references
and opaque source/delivery UUIDs correlate signed callbacks. Duplicate or older
receipts cannot regress accepted/delivered/read state or verify a phone.

Phone signup and recovery share the existing phone/IP rate buckets across Telegram
and WhatsApp, defaulting to five requests per phone/hour and 20 per IP/hour. Email
recovery also contributes to the existing shared recovery IP limit. WhatsApp
resends require 60 seconds; codes expire after five minutes and allow five attempts.
Switching channels or phones invalidates the previous browser signup challenge.
Completion locks the challenge and phone identity, rechecks ownership and consumes
the proof in the account-creation transaction. Existing/archived/staff logins are
not adopted or reactivated.

Recovery accepts only an active customer with a verified phone identity in the
configured website/company. A phone on an order/contact alone grants nothing.
Telegram-verified phone identities are eligible for WhatsApp recovery. The browser
receives the same acknowledgement for unknown identities. Existing reset grants,
credential stamps, password writes and session invalidation are reused. A WhatsApp
reset grant is additionally bound to the original website transport.

Monitor event states and age through administrator tools without decrypting payloads.
Queued, accepted, delivered, failed and unknown outcomes are distinct. Disable the
transport and dedicated worker to roll back. Preserve receipt routing for already
sent messages. No live database upgrade or service restart is included in this change.

## Production packaging

Package the two new addon directories separately, excluding `tests/`, `__pycache__/`
and `*.pyc`. Do not package staged copies of existing ecommerce addons or private
configuration. Keep gateway development tests out of the deployed service artifact.
