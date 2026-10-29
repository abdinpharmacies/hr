## 63308c96fc721d075d5aadacff2ceb2ac5c0fb7b - emadco88 - 2026-10-28

Original commit subject: ab_sales/ UPD balance for stores

User-facing changes:
- Open the store balance popup with live balances and retain saved balances when the live read fails.
- Keep individual branch refreshes and display initial loading errors.

Files changed (popup scope):
- ab_sales/static/src/pos/store_balance_rows.js
- ab_sales/static/src/pos/store_balance_rows.xml

## b0f519ef0be53ddeaec9b6157e513615d502cef5 - Hossam Elsheikh - 2026-10-20

Original commit subject: ab_sales/feat: port draft concurrency, search filters, stock freshness and annotations to API-only callcente

User-facing changes:
- Preserve product-search filters and reject stale keyboard-fallback responses.

Files changed (keyboard-search scope):
- ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js

## Current changes before commit:

- Sort matching branches by finite numeric balance, UI-locale branch name, then numeric store ID; keep unknown balances last and reorder after successful refreshes.
- Search branch names and codes literally first, then try Arabic/English keyboard conversions locally, including `s,ih[` for Sohag. Preserve typed text, AND matching, and independent product-search settings.
- Share the existing keyboard mappings with product search while retaining its RPCs, result limit, settings, and stale-response guards.
- Display one entry per row below 768px and two equal-width entries from 768px, with wrapping and RTL support.
- Remove Source and Last refreshed columns; retain unavailable reasons, cached warnings, and initial/refresh errors.
- Use icon-only refresh buttons with translated refresh/loading/retry names and tooltips, disabled states, and busy indicators.
- Give branch refresh buttons a minimum 44 × 44px touch target with centered icons and no flex shrinking.
- Focus search once on each mount without refocusing during filtering, prop updates, or refreshes.
- Preserve backend payloads, permission checks, refresh RPCs, balance formatting, and failed-refresh balances.

Files changed:
- ab_sales/static/src/pos/store_balance_rows.js
- ab_sales/static/src/pos/store_balance_rows.xml
- ab_sales/static/src/pos/store_balance_rows.scss
- ab_sales/static/src/pos/utils/keyboard_mapping.js
- ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-10-29-store-balance-popup.md

Validation:
- Passed 31 logic checks covering numeric sorting, unknowns, object/state retention, literal precedence, both keyboard directions, codes, multiple terms, deduplication, refresh reordering/failure/stale responses, and product-search equivalence with the previous implementation, including the 24-result limit.
- Passed 18 headless Chromium checks using the production Owl component/template, compiled Odoo CSS, runtime translations, and mocked refresh responses. Covered 375/767/768/1024px widths, long names, odd counts, Arabic RTL, keyboard refresh, labels/tooltips, loading/disabled states, visible feedback, and mount-only focus. No browser errors.
- Two targeted `ab_sales` upgrades passed on disposable database `store_balance_popup_validation_20261029`, copied from the existing isolated validation database. Used the callcenter worktree addons, ports 5169/5172, zero workers and disabled cron. The user's Odoo process was not stopped.
- Exported the Odoo 19 POT and preserved unrelated catalog entries. Both Arabic catalogs cover all 16 popup strings and pass `msgfmt --check-format`. Runtime labels passed for `ar` and `ar_001`; the wizard view differs between `en_US` and `ar_001`.
- Compiled backend JS, CSS and RTL CSS, including the new utility and stylesheet. JavaScript/XML syntax and `git diff --check` passed.
- Existing environment warnings remain: unrelated manifest/translation/deprecated-constraint warnings, draft-cache not-null warnings, and a missing copied filestore attachment. They did not prevent upgrades or asset generation.
- Browser refreshes were mocked; live branch API and external database connectivity were not exercised. Test scripts, logs, POT, compiled assets and screenshots remain outside the production addon at `/tmp/store_balance_popup_validation`.

Follow-up validation (44px touch targets):
- Passed 29 component/browser checks, including 320/375/767/768/1024px in English and Arabic RTL: minimum button dimensions, centered icons, visible keyboard focus, wrapping, odd counts, search, mount-only autofocus, loading, retry and disabled behavior.
- Passed 10 signed-in Odoo viewport checks against real B-Connect payloads containing 182 eligible branches. Popup rows and component have no horizontal overflow; branch 102 refresh remains disabled and branch 140 refresh remains available.
- The surrounding Odoo dialog header has 7px horizontal overflow at 320px in both languages. Reverting only the button sizing in the browser produces identical overflow; this pre-existing header issue is outside the module-scoped sizing correction.
- Passed 9 runtime checks on disposable database `store_balance_popup_validation_20261029`: real payload/configuration checks plus all four active/transfer combinations under both `active_test` settings. Excluded branches disappear from popup rows and cached totals and reject direct refresh before a remote call. Configuration changes were rolled back.
- Targeted `ab_sales` upgrade and Odoo backend/RTL asset compilation passed on the isolated database. Both Arabic catalogs pass `msgfmt --check-format`; runtime translation checks pass for `ar` and `ar_001`. This correction adds no user-facing strings or backend changes.
- Missing generated assets in the copied test filestore initially opened an unrelated error dialog; rebuilding those assets in the disposable database allowed signed-in checks to pass without browser errors. The temporary server used ports 5169/5172 with cron disabled; the user's process was not stopped.
- Follow-up scripts, JSON results and screenshots remain in `/tmp/store_balance_popup_validation`, outside the addon. The correction's unstaged diff passes `git diff --check`; the pre-existing staged keyboard utility still has a trailing-blank-line warning.
