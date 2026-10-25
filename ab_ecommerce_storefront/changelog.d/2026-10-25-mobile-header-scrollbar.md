# Mobile header scrollbar

## Current changes before commit

- Hide the visual horizontal scrollbar below the mobile header navigation while preserving touch, wheel, and drag scrolling.
- Prevent unrelated storefront scrollbar selectors from overriding the header-specific hidden-scrollbar rule.
- Present the four primary navigation actions as equal-width icon-and-label items at 414px and below.
- Keep Track order fully visible without horizontal scrolling or an ambiguous icon-only control.
- No user-facing strings changed; both Arabic catalogs remain unchanged.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/scroll_region.scss`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/2026-10-25-mobile-header-scrollbar.md`

Relevant commit:

- Commit: `f65e94ac27e5d1b3217abc97c871cf5e8a435f30`
- Author: Mohamed Fawzy
- Date: 2026-10-21
- Original subject: `ab_ecommerce_storefront/FIX: refine header and mobile carousel indicators`
- Added the header-specific hidden-scrollbar rule refined by this change.
- Files changed (relevant): `ab_ecommerce_storefront/static/src/scss/scroll_region.scss`, `ab_ecommerce_storefront/static/src/scss/storefront.scss`
