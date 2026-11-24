# Checkout and Sales Chatter notification fix — 2026-11-18

> Historical record: versions, deployment state and validation results below describe the dated work only. Temporary QA scripts/evidence may have been removed. For the current order-status button and login-return behavior, use [the current guide](website-order-status-links.md). This record does not establish a current production rollout.

The storefront adapter's `sale.order.message_post` override checked Callcenter chat readiness for every external-user post, including automatic messages whose default type is `notification`. Once confirmation captured an order UUID, a subsequent payment notification could raise the pending chat receipt error and roll back checkout. The guard now applies to `comment` posts. Customer comment ownership, endpoint and acknowledgement checks remain enforced. Order notification delivery is not Callcenter order acceptance.

Callcenter order-only conversation details retain `can_send=False` and the server-side reply restriction, but return an empty display reason so the workspace does not create a reply-disabled popup. Conversations containing customer chat retain their existing eligibility feedback.

The repeated payment page log warning came from the unsupported `t-translation-context` QWeb attribute; it was removed from the owning storefront view. No source UI strings or Arabic translations changed.

Validation used `/opt/odoo19/venv19/bin/python` and `/opt/odoo19/server/odoo-bin`, explicit matching runtime addon roots and isolated databases, with zero workers/cron threads and `--stop-after-init`:

| Database | Checks | Result | Log |
| --- | --- | --- | --- |
| website_chat_validation_20261117 | Targeted ab_crm_website upgrade and TestWebsiteContactGroups | 14 passed | /tmp/order-notification-callcenter-tests.log |
| storefront_chat_validation_20261117 | Targeted ab_ecommerce_storefront and ab_storefront_callcenter_adapter upgrade; TestCapture | 23 passed | /tmp/order-notification-storefront-tests.log |
| storefront_chat_validation_20261117 | Public COD confirmation before receipt; unpaid pending payment; retry without duplicate picking | 1 passed | /tmp/order-notification-public-cod-tests.log |
| website_chat_validation_20261117 | Notification-only browser flow, English and Arabic | 2 passed | /tmp/order-notification-browser-verified.log |

The first browser attempt skipped because its PYTHONPATH lacked websocket-client. The final run used the existing `/tmp/website-browser-deps` dependency and executed both tests successfully. Browser requests were constrained to the isolated database with an exact db-filter. Callcenter HTTP/gevent ports were 5069/5072; storefront no-HTTP checks used 5075/5076. `ss -ltnp` confirmed all four ports released. Both Arabic catalogs in all three affected modules passed `msgfmt --check-format`; changed Python files parsed and both worktree diffs passed whitespace checks.

Live logs also contain branch balance/sales sync warnings requiring a branch connection and stock snapshot. These were not hidden or bypassed. Historical native-chat request.website errors already have a current-source fallback in the existing uncommitted work. No external database was contacted for this fix.

No live process was restarted, no runtime module upgrade was run, and no existing order/payment/stock was rewritten. Owner-controlled Python reloads are needed in both runtime processes; the payment-page XML also needs a targeted ab_ecommerce_storefront upgrade. Existing failed order NO-181126-9GB6H7 was not automatically retried or altered. Its resulting live status remains unverified.
