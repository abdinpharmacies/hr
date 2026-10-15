# Homepage support contrast

## Recent relevant commit

Commit: `95fdee2da4ed2cd7c248d7961db6bc275e9c9dea`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/FIX: translate dynamic storefront labels through Odoo`

User-facing changes:

- Render the address selection label through translated markup.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

## Current changes before commit:

- Keep promotional card text and icons white despite the storefront link inheritance rule.
- Use dark green text on light support buttons, including hover, keyboard focus, and active states.
- Improve support text contrast and soften the orange background highlight.
- Preserve responsive layout, focus outlines, and existing English and Arabic strings.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/2026-10-13-support-contrast.md`

Validation:

- SCSS compilation and whitespace checks passed.
- Updated RTL assets served the scoped card and button colors, including interaction states.
- Sampled white-text contrast across the card gradients and support highlight: minimum 4.64:1; dark green button text: 7.75:1 on white and 6.97:1 on pale green.
- Browser visual verification was unavailable in this session.
