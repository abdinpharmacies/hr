# Website live chat input

Recent relevant commit:

- Commit: `1525c72f2663958d2946799aed1490566c2d6ef5`
- Author: Mohamed Fawzy
- Date: 2026-11-16
- Original subject: `ab_ecommerce_storefront/IMP: add integrated customer live chat`
- Added the integrated support launcher, chatbot, operator handoff and offline email collection.
- Files changed: `__manifest__.py`, `data/livechat.xml`, `i18n/ab_ecommerce_storefront.pot`, `i18n/ar.po`, `i18n/ar_001.po`, `static/src/img/abdin_pharmacy_bot_avatar.jpg`, `static/src/js/livechat_bridge.js`, `static/src/js/support_widget.js`, `static/src/scss/livechat_theme.scss`, `static/src/scss/storefront.scss`, `views/layout.xml` (all within this module).

Current changes before commit:

- Accept the visitor's first message at the welcome step before forwarding to an operator. Previously the transient conversation reached the operator step without an initial interaction, leaving its composer disabled.
- Preserve the existing welcome text, XML IDs, operator handoff, offline email fallback and translations.

Files changed:

- `ab_ecommerce_storefront/data/livechat.xml`
- `ab_ecommerce_storefront/changelog.d/2026-11-17-livechat-input.md`

Validation:

- Reproduced the missing composer on the local development website at port 4102 before the fix; confirmed the composer appears after the fix.
- Applied only the XML-owned welcome step's `step_type` through the ORM on development database `e_commerce`. The native first-step warning cleared. No full module upgrade or process restart was performed.
- Native ORM checks passed for operator handoff and offline email collection with operator availability mocked. All temporary guest/channel/message records and bus notifications were rolled back; no operator was contacted.
- English and Arabic runtime welcome translations differ and remain populated. Both Arabic catalogs passed `msgfmt --check-format`; no source strings changed.
- XML parsing and `git diff --check` passed. Validation shell sessions used `--no-http --max-cron-threads=0` and queues disabled; no temporary server ports were opened.
- Other databases require the normal targeted module upgrade to load the corrected XML data.
