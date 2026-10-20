# Navigation icon motion

## Recent relevant commit

Commit: `95fdee2da4ed2cd7c248d7961db6bc275e9c9dea`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/FIX: translate dynamic storefront labels through Odoo`

User-facing changes:

- Translate dynamic storefront navigation labels through Odoo.

Files changed:

- `ab_ecommerce_storefront/views/layout.xml`

## Current changes before commit:

- Add brief, distinct icon feedback to the six primary navigation controls: home lift, offer-tag swing, staggered category tiles, heartbeat with a moving ECG trace, prescription-line drawing, and order-tracking search scan.
- Reuse the corresponding motions on the four existing mobile navigation links. Preserve destinations, labels, selected states, dropdown attributes, and chevrons.
- Use decorative inline SVGs, hidden from assistive technology and excluded from pointer targeting, inside the existing controls. The heartbeat outline and trace inherit the control color in normal and expanded states.
- Run one short burst on pointer hover, keyboard-visible focus, or press. Restrict hover to a fine pointer that supports hover. Enable animation only when the user has no reduced-motion preference; leave static icons otherwise.
- Keep fixed icon bounds and animate transforms/opacity, with a small SVG stroke-dash animation for the ECG highlight. No JavaScript, new library, asset registration, or new QWeb XML ID is required.
- Preserve existing English and Arabic labels. No new user-facing strings were introduced and no translation catalog was changed by this task.

Files changed:

- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-navigation-icon-motion.md`

Design references:

- UI/UX Pro Max searches for icon-hover motion and reduced-motion interaction support short, localized feedback and keeping primary interactions usable without hover.
- [Material Design motion](https://m2.material.io/design/motion/understanding-motion/) supports motion that reinforces meaning. The six specific gestures are design choices for these controls, not prescribed icon-specific standards.
- [web.dev animation performance](https://web.dev/articles/animations-guide) recommends transforms and opacity and avoiding layout animation. The only additional animated property is the bounded ECG stroke offset.
- [W3C technique C39](https://www.w3.org/WAI/WCAG22/Techniques/css/C39.html) supports enabling nonessential interaction animation under `prefers-reduced-motion: no-preference`.

Validation:

- Final targeted storefront upgrade passed on the idle development database `ecom19_home_ux_20261015`, with this checkout, no HTTP, zero workers/cron threads, and ports 5469/5472 in the validation configuration.
- Two in-process HTTP page checks returned 200 for English and Arabic. Each rendered ten decorative icons, all six primary navigation meanings, nonempty translated labels, existing links, and intact dropdown attributes. Both generated language CSS bundles returned 200 and contained the motion keyframes and media guards.
- Full storefront SCSS compilation, XML parsing, `git diff --check`, both existing Arabic catalogs' `msgfmt --check-format`, header scoping, and static checks for focus/press/hover triggers and non-looping animation passed.
- Read-only HTTP checks against the active development server on port 4092 confirmed the new markup and animation CSS were served under its existing XML/assets development mode. The active server was not restarted or upgraded.
- Browser inventory was empty and the in-app browser was unavailable. Real pointer/keyboard/touch behavior, viewport layout, and frame timing were not visually verified. The SVG raster preview attempt was also unavailable because the Rsvg renderer is not installed.
- Runtime evidence is under `/tmp/ab-navigation-icons-validation/`. No business logic or permissions changed, and no production package was generated. Existing best-seller and navigation-performance work remains separate and untouched.
