# Minimized assistant appearance

Recent relevant commit:

- Commit: `1525c72f2663958d2946799aed1490566c2d6ef5`
- Author: Mohamed Fawzy
- Date: 2026-11-16
- Original subject: `ab_ecommerce_storefront/IMP: add integrated customer live chat`
- Added the integrated customer support launcher and themed live chat.
- Files changed: `__manifest__.py`, `data/livechat.xml`, `i18n/ab_ecommerce_storefront.pot`, `i18n/ar.po`, `i18n/ar_001.po`, `static/src/img/abdin_pharmacy_bot_avatar.jpg`, `static/src/js/livechat_bridge.js`, `static/src/js/support_widget.js`, `static/src/scss/livechat_theme.scss`, `static/src/scss/storefront.scss`, `views/layout.xml` (all within this module).

Current changes before commit:

- Hide the native minimized chat bubble and its options inside the storefront livechat root so the existing floating support launcher remains the single entry point.
- Preserve chat state, minimizing, reopening, composer behavior and all existing JavaScript logic.
- This entry covers the minimized assistant styling change; other pending module work is recorded separately.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/livechat_theme.scss`
- `ab_ecommerce_storefront/changelog.d/2026-11-17-livechat-minimized.md`

Validation:

- Reproduced the duplicate native bubble on the local development website at port 4102.
- Reloaded with cache bypass and verified the rebuilt stylesheet hides the native bubble without injected test styles.
- Verified minimizing and reopening the existing chat through the support launcher on desktop and at a 390px mobile viewport; the composer remains present.
- SCSS compilation, both Arabic catalogs (`msgfmt --check-format`) and `git diff --check` passed. No user-facing strings changed.
- No database upgrade, service restart or message submission was needed for this CSS-only change.
