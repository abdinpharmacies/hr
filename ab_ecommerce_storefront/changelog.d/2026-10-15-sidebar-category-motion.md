# Sidebar category motion

Current changes before commit:
- Match the shop sidebar category opening to the header category/need menus: slide, fade, slight scale, and 45 ms stagger between immediate children.
- Animate each panel to its measured height, with smooth closing and cancellation when toggled repeatedly.
- Preserve one expanded sibling per level, nested navigation, and accessible expanded state; disable interaction with closing panels and honor reduced motion.
- Reuse the registered module asset without changing UI strings, translations, templates, or backend behavior.

Validation:
- JavaScript syntax and `git diff --check` passed.
- Six temporary Node harness scenarios passed: opening/stagger, nested scope, sibling closing, rapid reversal, reduced motion, and animation API fallback.
- Browser-based motion verification and a targeted database upgrade were not performed. The temporary Node harness validates behavior independently of the running Odoo server.

Files changed:
- `static/src/js/shop_category_accordion.js`
- `changelog.d/2026-10-15-sidebar-category-motion.md`

Relevant commit:
- Commit: `f4ecc3b63f3aea0974b13851d4767258353ffd0c`
- Author: Mohamed Fawzy
- Date: 2026-09-10
- Original subject: `ab_ecommerce_storefront/ux: add expandable shop category filters`
- Added the expandable shop category navigation extended by this change.
- Files changed (relevant): `static/src/js/shop_category_accordion.js`
