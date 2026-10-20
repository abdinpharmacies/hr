# Reusable storefront scrollbars

Current changes before commit:
- Add a reusable scrollbar mixin and `ab-storefront-scroll-region` class with a 12px scrollbar, pill-shaped green thumb, subtle grip marks, slim borderless sage track, hover/pressed feedback, and keyboard focus outline.
- Apply the same styling to existing product rows, recent history, reviews, unit selectors, brands, search suggestions, category/navigation lists, account navigation, and branch lists.
- Keep native scrolling and direction handling; provide 14px coarse-pointer scrollbars and system colors in forced-color mode.
- Remove the directional buttons and heavy track outline for a lighter appearance. Firefox uses its native thin scrollbar; subtle grip marks are a WebKit/Blink enhancement.
- Register the stylesheet after existing storefront styles and mark the recent-history row with the reusable class.
- No user-facing strings changed; both Arabic catalogs remain unchanged by this task.

Validation:
- Existing storefront and new component SCSS compile with the project virtual environment's libsass.
- Manifest parsing, final frontend asset order, changed XML parsing, and `git diff --check` passed.
- Live browser and runtime asset verification were not performed. Overlay scrollbar visibility remains controlled by the browser/operating system.

Files changed:
- `__manifest__.py`
- `static/src/scss/scroll_region.scss`
- `views/browsing_history_templates.xml`
- `changelog.d/2026-10-19-reusable-scrollbar.md`

Relevant commit:
- Commit: `949aaccee3ff14efc5a4411419f2e6ecec678d01`
- Author: Mohamed Fawzy
- Date: 2026-10-15
- Original subject: `ab_ecommerce_storefront/IMP: refine product offers and remove duplicate total`
- Refined product offers in the existing storefront stylesheet inspected for integration.
- Files changed (relevant): `static/src/scss/storefront.scss`
