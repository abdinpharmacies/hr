# Product filter loading feedback

## Recent relevant commit

Commit: `09e2823790bf376e5f5d12d2416d6399bdc1c790`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: add shop by need sidebar selection`

User-facing changes:

- Support Shop by Need selection in the mobile filter draft, including Apply and Cancel.

Files changed:

- `ab_ecommerce_storefront/static/src/js/shop_filter_draft.js`

## Current changes before commit:

- Fade and partially desaturate products when category, need, brand, deal, availability, or reset links navigate to new results.
- Reuse the same feedback for native price and attribute filters, with a delayed green progress line and reduced-motion support.
- Mark results busy and prevent interaction with stale product cards while navigation is pending.
- Preserve mobile draft selection until Apply, accordion expansion, and modified/new-tab clicks.
- Restore results after browser Back, interaction cleanup, or the 30-second cancelled-navigation recovery timeout.
- Add no user-facing strings; preserve existing English and Arabic catalogs and unrelated working changes.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/static/src/js/shop_filter_loading.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/2026-10-13-filter-loading.md`

Validation:

- Targeted `ab_ecommerce_storefront` upgrade passed on isolated database `codex_ecom_branches_20261012`, ports 5069/5072, with cron disabled. The existing Odoo process was not restarted.
- 14 loading scenarios passed in a temporary jsdom harness using actual shop HTML and a synthetic brand link because the fetched catalog has no brands. The harness exercises the interaction lifecycle without the browser's Odoo service layer.
- Existing Shop by Need check passed all 6 scenarios.
- Source and compiled JavaScript syntax checks passed; generated English and RTL CSS contain the fade, progress, and reduced-motion rules.
- English and Arabic shop pages and their generated assets returned HTTP 200. Runtime category headings differ correctly between languages.
- Both Arabic catalogs passed `msgfmt --check-format`; `git diff --check` passed.
- Visual browser verification was unavailable: no connected browser, and the in-app browser could not be opened.
- The running development server on port 4092 still serves a cached JavaScript bundle without the new interaction; restart that development process and hard-refresh before checking the effect there. Only the temporary validation server was stopped.
