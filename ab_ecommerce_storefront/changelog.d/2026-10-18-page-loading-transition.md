# Storefront page loading transition

## Recent relevant commit

Commit: `44639625062895b73970db9ff87c29c5cdbd22f1`
Author: Mohamed Fawzy
Date: 2026-09-08
Original subject: `ab_ecommerce_storefront/feat: refine storefront header and homepage structure`

User-facing changes:

- Translate the checkout completion message through Odoo.

Files changed (relevant to this work):

- `ab_ecommerce_storefront/static/src/js/logo_motion.js`

## Current changes before commit:

- Replace the initial page-load splash with feedback during navigation between storefront pages. Start after 450 ms; never intercept, delay, replay, or resubmit the navigation.
- Keep the previous page visible through a static 10 px blur and translucent surface. Animate the configured website logo, a soft halo, and three brand-colored accents in a restrained 1.8-second loop. Reuse the site's logo, colors, and typography without adding a library or media asset.
- Observe native Navigation API events when available, with ordinary link and form listeners as a fallback. Connect the existing deferred logo and shop-filter navigation paths. Ignore same-document navigation, external destinations, downloads, modified clicks, and canceled fallback events.
- Keep the XML overlay hidden until needed. Restore focus, prior inert state, and busy state on dismissal, navigation errors, aborts, pagehide/pageshow, or interaction destruction. Disable the feature in the website editor.
- Attach the loader interaction to `.ab-storefront #wrapwrap`, Odoo's actual public-interaction discovery root, and resolve its overlay through `ownerDocument.body`. The initial `body.ab-storefront` selector was outside that discovery scope, so the loader never started on real storefront pages; manually instantiated tests missed this integration defect.
- Keep “Loading your next page…” / “جارٍ تحميل الصفحة التالية…” as the only loading label throughout the wait. Support Escape and release the overlay after twenty seconds, without a visible dismiss button or retrying the underlying operation.
- Show one short health tip as a plain paragraph immediately below the loading label. Remove the extra “Your health matters” heading, card background, border, shadow, padding, and all source links from the loader. Reduce the logo scene size on short screens and allow the overlay to scroll.
- Choose an initial tip randomly, then advance through all six tips across page loads using tab-scoped session storage. Advance only when the loading screen actually appears and keep the same tip for the entire wait. Blocked or invalid storage never prevents navigation.
- Store all six tips directly in the module's QWeb layout and render them in the site's language through the existing Arabic catalogs. Include the active tip in the dialog description and keep keyboard focus within the overlay. No health information is fetched from external sources during loading; source references remain only in development review artifacts.
- Preserve a static, readable loading state for reduced-motion preferences. Include a backdrop-filter fallback and safe-area padding.
- Preserve existing translation entries in both Arabic catalogs and the bundled POT, including unused terms from the earlier design. The simplified loader reuses the already translated loading phrase and six tips; no new user-facing strings were introduced in this follow-up.
- Preserve the separate uncommitted navigation-icon, best-seller, and performance work.

Files changed:

- `ab_ecommerce_storefront/static/src/js/logo_motion.js`
- `ab_ecommerce_storefront/static/src/js/shop_filter_loading.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-page-loading-transition.md`

Design evidence:

- UI/UX Pro Max's loading-feedback guidance supports avoiding flashes for near-instant actions, preserving focus, and exposing accessible busy status.
- [NN/g: Progress indicators](https://www.nngroup.com/articles/progress-indicators/) supports clear feedback and additional context for longer waits.
- [Ding and Kyung: Optimizing Animation Speed](https://academic.oup.com/jcr/article/53/1/136/8165440) reports lower perceived waiting time with moderate-speed animations in its experiments. The exact 1.8-second motion, blur, and logo treatment here are design choices, not a tested optimum for Abdin customers.
- The supplied logo-motion playground informed the breathing/float direction. Its original files were not modified.
- Health content sources checked on 2026-10-18: [CDC handwashing](https://www.cdc.gov/clean-hands/about/index.html), [NHS dental care](https://www.nhs.uk/live-well/healthy-teeth-and-gums/how-to-keep-your-teeth-clean/), [NHS medicine storage](https://www.nhs.uk/baby/first-aid-and-safety/safety/baby-and-toddler-safety/), [WHO healthy diet](https://www.who.int/news-room/fact-sheets/detail/healthy-diet), [WHO physical activity](https://www.who.int/news-room/fact-sheets/detail/physical-activity), and [CDC antibiotic use](https://www.cdc.gov/antibiotic-use/about/).
- The exact bilingual wording and source URLs are available for human review in `outputs/loading-transition/health-tips-review.html` and `.json`, alongside an updated interactive `preview.html`. These are development artifacts outside the addon. Medical wording requires human review and approval before public release; no production deployment was performed.

Validation:

- 28 updated deterministic JavaScript lifecycle/navigation checks passed using the actual loader class with a simulated DOM and timers. They cover native events, fallback clicks/forms, invoice downloads, cancellation, fast navigation, focus/inert/busy restoration, an unchanged loading message during long waits, Escape, errors, aborts, editor mode, teardown, one stable tip per wait, a full six-tip cycle across documents, invalid/unavailable storage, keyboard focus isolation, and templates with no tips.
- After the discovery correction, all 22 checks passed with the interaction attached to the content root. A separate CSS-selector regression against the active Arabic page reproduced zero matches for the old selector and exactly one match for the corrected selector, with access to the body-level overlay and its controls. The root-selection and matching behavior were traced in the installed Odoo 19 `interaction_service.js`.
- Read-only HTTP checks on the running development site at port 4092 confirm the loading phrase and six static tip paragraphs in English and Arabic, no extra heading/links/buttons, no card styling, and the updated interaction bundle. Existing browser tabs need a hard refresh to load these assets.
- Targeted `-u ab_ecommerce_storefront` passed on the idle development copy `ecom19_home_ux_20261015`, using this checkout, no HTTP, zero workers/cron threads, and ports 5569/5572. The active `ecom19` server was not stopped, restarted, or upgraded.
- The earlier isolated development run passed ten Odoo HTTP checks, including English/Arabic tips, compiled CSS, and loader availability on shop, contact, and login pages. The simplified follow-up was checked directly on both languages of the running local site, including exact wording, plain-paragraph structure, hidden state, and generated styles.
- XML parsing, full storefront SCSS compilation, Odoo JavaScript transpilation, Node syntax checks, both Arabic catalogs and POT `msgfmt --check-format`, and `git diff --check` passed.
- Calculated worst-case text contrast over black beneath the 68% scrim is 3.31:1 for the 22 px/700-weight heading and 5.67:1 for body copy, meeting their respective WCAG AA thresholds.
- The validation copy lacked its logo filestore object; the matching existing object was copied into its isolated filestore. Other unrelated missing attachments and existing module deprecation warnings remain in the validation environment.
- Browser inventory was empty; both in-app browser and Chrome creation reported unavailable. Actual viewport rendering, animation smoothness, screen-reader behavior, and browser navigation events have not been visually verified. The deterministic tests do not substitute for browser testing.
- Refreshed only the existing loader fragment in `ab_ecommerce_storefront.layout`, the loading phrase, and six translated tips through Odoo ORM on local `ecom19`, then signaled template cache invalidation. No service restart or module upgrade was performed on that active development server; unrelated view content was preserved.
- Reproducible validation scripts and logs are in `/tmp/ab-loader-validation/`. No business logic, permissions, production database, or runtime packaging changed.
