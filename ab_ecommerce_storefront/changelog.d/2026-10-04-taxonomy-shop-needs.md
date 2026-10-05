# Taxonomy descriptions and Shop by Need

## Recent relevant commit

Commit: `e47a109c0df003af3ddb8f4c1bbfab8beec20ee5`
Author: Mohamed Fawzy
Date: 2026-09-29
Original commit subject: `ab_ecommerce_storefront/docs: update storefront commit history`

- Record the module’s recent implementation history.

Files changed:

- `changelog.d/current.md`

## Current changes before commit:

- Connect all ten Shop by Need menu options to stable category-based filters.
- Keep the selected need during pagination, search and category browsing.
- Show the translated selected need as the shop heading.
- Validate live Arabic pages, English pagination, unknown-need filtering and the existing category assurance-strip exclusion.

Files changed:

- `models/website.py`
- `controllers/shop.py`
- `views/shop.xml`
- `changelog.d/current.md`
- `changelog.d/2026-10-04-taxonomy-shop-needs.md`
