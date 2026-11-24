# Local Website chat acceptance — 2026-11-17–18

> Historical record: versions, deployment state and validation results below describe the dated work only. Temporary QA scripts/evidence may have been removed. For the current order-status button and login-return behavior, use [the current guide](website-order-status-links.md). This record does not establish a current production rollout.

Scope: test the existing website and Callcenter servers on this machine. Production deployment is deferred. If production diagnosis is required, the user supplied `ssh -p 2222 hassan@46.202.130.7`; access must be read-only. No production configuration, source, orders, messages, channel or pricelist was edited during this test.

## Actual local runtime

- Ecommerce: `e_commerce`, source `/opt/odoo19/worktrees/e_commerce`, existing Odoo on 4102, certificate-verified HTTPS proxy on `127.0.0.1:5443`.
- Callcenter: `callcenter`, source `/opt/odoo19/worktrees/callcenter19`, existing Odoo on 4092, HTTPS proxy on `127.0.0.2:5444`.
- Both servers had already been reloaded/upgraded by their owner when testing began. Callcenter reports `ab_crm_website` 19.0.1.5.0; ecommerce initially reported adapter 19.0.1.1.0.
- The dedicated Website worker was reloaded locally to run v2. Existing source/account mappings and production sending-disabled settings were preserved.
- Only local endpoint `website-pilot` was configured for native chat and outgoing replies, using its existing website Live Chat channel and the module-owned Callcenter Support operator. Only its local Callcenter account's outgoing switch was enabled. Prior settings are saved privately in `/tmp/local-chat-settings-before.json` and `/tmp/local-chat-channel-before.json`.

## Passed against the running servers

| Check | Actual result |
| --- | --- |
| Source transport | Authenticated, certificate-verified v1 and v2 fetch each returned HTTP 200. |
| First floating input | A separate guest client created native session 18 and posted its first input through `/mail/message/post`; the real supervised worker delivered and acknowledged it once. |
| Staff reply | Sent from the existing authenticated staff browser, accepted by the gateway and visible exactly once to the original guest through native history. |
| Native browser widget | A fresh `localhost:4102` browser context displayed the native greeting and Callcenter Support operator. Its first input reached its own Visitor conversation (native session 19), and the staff reply appeared in that same widget. |
| Guest reconnection | Reload restored the widget/history. A follow-up retained the same opaque native destination and Callcenter conversation. |
| Order guest chat | The existing labelled local acceptance order S00158 remained protected by its own checkout-session/capability. One message submitted twice with the same UUID produced one native comment, one destination message and one acknowledgement. |
| Cross-order protection | Borrowing that session to submit against the other guest order returned HTTP 403. |
| Order reply | Staff replied from the existing order conversation. The original order guest saw exactly one reply in the authoritative native order history. Floating replies did not appear there. |
| Native order-page comment | After the owner reload, the native `/mail/message/post` request posted successfully and reached the existing order conversation exactly once. |
| Arabic queued acknowledgement | A new Arabic native guest session received exactly one Arabic acknowledgement, then its customer input was delivered and acknowledged by the real worker. |
| Queue and receipts | Six local customer events acknowledged; three staff replies had unique native receipts and accepted outgoing operations. No reply was reflected as an incoming event. |
| Business preservation | Existing captured order count stayed seven. Testing created chat evidence only; no new checkout/order, payment, POS invoice or stock operation was created. |
| Other source boundary | All acceptance events belong to `website-pilot`; `website-production` sending remains disabled. |

Non-secret detailed evidence: `/tmp/local-chat-live-evidence.json`. Browser proof: `/tmp/local-chat-browser-reply.jpg`. The user's pre-existing browser chat draft was preserved; acceptance used a separate guest session.

## Issues found and verified fixes

1. The native `/mail/message/post` route has no `request.website`. The source ownership helper now derives the website from the request host when that attribute is absent. The live attempt failed before posting; the protected compatibility endpoint already works. Regression coverage explicitly removes the website-route attribute.
2. Native message posting used the public user's default language for the queued acknowledgement, even though the session language was Arabic. It now uses `livechat_lang_id`; regression coverage checks both English and Arabic under an English posting context.
3. A source without chat v2 returned 404 on every poll, causing misleading repeated warnings despite successful v1 intake. The worker now remembers that per-source result until restart, while retaining v1 intake. Restart the worker after upgrading an older source to enable its v2 exchange. The original v1 durable payload is preserved, with a regression covering an order queued before the worker upgrade.

The source fixes are loaded locally as adapter **19.0.1.1.1**. All **22** ecommerce regressions pass on `storefront_chat_validation_20261117` after targeted upgrades of the storefront and adapter (`/tmp/local-chat-upgrade-preservation.log`). All **98** selected gateway checks pass, including both isolated queue backends, dual-channel and authentication regressions.

4. The owner reload also upgraded the storefront, whose Live Chat XML replaced the operator list with the administrator alone. This removed the configured bridge operator and made v1/v2 fetch return 422. The existing local bridge membership was restored through Odoo while preserving other operators. Storefront **19.0.1.0.1** now adds its default operator without replacing configured operators. A regression reloads that exact XML and verifies both retained membership and service fetch eligibility. The fixed XML was validated on the isolated database; current local membership was restored without another Odoo restart.

## Completed live verification and remaining scope

The owner reloaded ecommerce on 4102. Native order-page comment submission and Arabic queued acknowledgement both passed against the running server. Matching source/destination receipts total six acknowledged customer events and three accepted staff replies, with the captured order count still seven. Both local fetch versions returned HTTP 200 with zero pending events after the configuration repair. A bounded retry handles normal HTTP 409 contention with the real polling worker. Odoo was not stopped or restarted by the agent. No additional reload is required to continue local testing.

The local browser does not yet trust the pilot HTTPS CA: opening the secure order compatibility page produced a certificate-authority error, which was not bypassed. Guest API checks used the existing trusted CA bundle with verification enabled. Floating browser checks used the normal local HTTP website.

Authenticated-customer login transitions, the complete mobile customer widget and a new checkout/payment cycle were not repeated against live data in this pass; their existing isolated regression coverage is separate evidence. Production acceptance and rollout have not been performed.
