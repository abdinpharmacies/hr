# Website order status button

Sales Chatter incoming order cards have a bold “View Order Status” button outside the collapsed invoice. Each card targets its own website order and source UUID. Website Odoo login is required; staff open the Ecommerce Orders screen (`/odoo/ecommerce-orders/<order ID>`) with its existing invoices, payments and deliveries, subject to their usual permissions. This does not add E-Plus or POS progress tracking.

## Manual rollout

1. Back up the destination databases and retain the currently deployed addon packages and configuration.
2. Deploy `ab_storefront_callcenter_adapter` 19.0.1.5.4 on Website Odoo first. Upgrade only that module using its normal maintenance procedure.
3. Deploy `ab_crm_website` 19.0.1.16.1 on Callcenter. Upgrade only that module, then refresh backend assets.
4. A CRM manager or administrator opens the website messaging account and sets **Website Odoo base URL** to the reachable website origin, for example `https://orders.example.com`. Leave it blank to hide links. HTTP is accepted only for loopback development addresses. Credentials, paths, queries and fragments are rejected.
5. Verify two different order cards open their own orders. Check login return, Arabic text, and the staff member’s existing sales/company permissions. Website accounts and staff access must already exist; there is no cross-server SSO.

The integration route is `/odoo/storefront-callcenter/backend-order/<source UUID>/<order UUID>`. After authentication and access checks it opens `/odoo/ecommerce-orders/<order ID>`. It preserves sale.order access and record rules without switching company or using a sudo order recordset. The source UUID predicate bypasses access to the endpoint configuration only; it returns no endpoint data and grants no endpoint access. Portal users get 403; missing or inaccessible orders get 404. UUID knowledge does not grant order access.

## Rollback

Clear the website account origin first to hide links, then restore the previous receiver package using the normal maintenance procedure. Restore the previous source adapter package last. Preserve database order mappings and queues; do not replay historical events or remove business records. Retain the new optional field rather than destructively removing schema. Use the predeployment backup if a full database rollback becomes necessary.

## Validation evidence

Isolated QA databases: `independent_chats_20261124` and `two_server_qa_independent_20261124_store`; ports 5569/5572 and 5589/5592. Production services and account configuration were not changed.

Targeted receiver tests cover per-order URLs, blank configuration, rejected origins and configuration permissions. Website HTTP tests cover login return, exact order/source matching, portal denial, service ACL denial, salesperson record rules and cross-company denial. The frontend check mounts the real Owl template in Arabic at 320px and checks the visible footer outside the collapsed invoice, its exact href and safe new-tab attributes. Both Arabic catalogs pass gettext format checks; the setting label also differs at runtime between English and Arabic.

Runtime packages exclude development tests, changelogs, caches and documentation. Temporary repository QA runners and the uncommitted order-link test files were removed on 2026-11-24; existing tracked regression tests remain available.

Final focused result: **8 passed** (2 receiver, 5 website HTTP, 1 Owl browser), no feature failures. These historical focused results precede the final route and button-label refinements. The development login form was subsequently checked to retain the exact order return URL; that check did not submit staff credentials. The existing broader workspace browser scenario encountered a separate null `website_target` error at `ab_crm_sales_workspace/static/src/chat_controls.js:18` while switching actions; the original test was preserved, and the feature was verified through its dedicated Owl test. Production end-to-end acceptance remains a rollout check.

Login return: integration links use an `/odoo/` prefix so the unchanged storefront login identifies them as backend destinations. The old route remains an alias for existing authenticated links. The integration resolver then opens `/odoo/ecommerce-orders/<order ID>`. No shared login overrides or customer authentication changes are included.

## Current development setup

The development website is `http://127.0.0.1:4102`; Callcenter runs on port 4092. The matching Website Callcenter Pilot account has its website origin configured. Other accounts with different source UUIDs must use their own verified origins. Refresh Sales Chatter after changes.

The button label is **View Order Status** (Arabic: **عرض حالة الطلب**). Both are bold. Links open in a new tab with `noopener noreferrer`. The `/odoo/` prefix selects the existing backend login flow and preserves the return destination; website authentication code is unchanged. The previous `/storefront-callcenter/backend-order/` address remains an alias.
