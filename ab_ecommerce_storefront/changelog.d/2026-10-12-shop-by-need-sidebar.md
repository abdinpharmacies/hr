# Shop by Need sidebar selection

Current changes before commit:
- Show Shop by Need immediately after category navigation and before Brands in the desktop sidebar and mobile filter dialog.
- Reuse the header's ten translated need labels, icons and stable keys. Mark the applied URL selection in the sidebar and desktop/mobile header menus.
- Preserve other filters when switching needs and offer All needs to remove only the need selection. Include need in Clear all filters.
- Keep mobile changes pending until Save, restore the applied selection on cancellation, and reset pagination when changing the need.
- Shorten the Arabic All needs label to «الكل» in both Arabic catalogs, preserving the English label and filter behavior.

Validation:
- Six focused JavaScript scenarios passed: URL selection, mobile draft/save with pagination reset and other filters preserved, cancellation, All needs, Clear all filters and desktop navigation.
- Existing mobile deal draft/desktop immediate behavior check passed.
- Python/XML parsing, SCSS compilation, JavaScript syntax and `git diff --check` passed.
- Both Arabic catalogs passed `msgfmt --check-format`; all ten need labels and both section/reset labels are translated without fuzzy flags.
- No live database upgrade or process restart performed. Runtime QWeb rendering and browser interaction on the upgraded module remain unverified.

Files changed:
- `models/website.py`
- `views/shop.xml`
- `views/layout.xml`
- `static/src/js/shop_filter_draft.js`
- `static/src/scss/storefront.scss`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `i18n/ab_ecommerce_storefront.pot`
- `tests/check_shop_need_selection.cjs`
- `changelog.d/2026-10-12-shop-by-need-sidebar.md`
