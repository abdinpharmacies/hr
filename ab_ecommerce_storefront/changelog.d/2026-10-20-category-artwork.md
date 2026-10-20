# Storefront category illustrations

Commit: `b87f134138c775ef8e47ff32acc512b586e6db30`
Author: Mohamed Fawzy
Date: 2026-10-15
Original subject: `ab_ecommerce_storefront/IMP: add category image management with fallbacks`

- Added category image management and editable fallback previews.

Files changed relevant to this change:

- `ab_ecommerce_storefront/models/product_public_category.py`
- `ab_ecommerce_storefront/views/category_image_views.xml`

## Current changes before commit:

- Add nine coordinated category illustrations with green, blue, and peach backgrounds, recognizable product compositions, soft lighting, and no embedded text.
- Optimize the covers as 960 × 640 WebP files, approximately 18–29 KB each.
- Apply all nine covers to the existing published top-level categories in `ecom19` through the existing Section Image inverse and native cover field. These content updates are database-specific; shipping the asset files alone does not populate other databases.
- Preserve the existing homepage layout, upload controls, category names, translations, and unrelated working-tree changes.

Files changed:

- `ab_ecommerce_storefront/static/src/img/category_covers/everyday-essentials.webp`
- `ab_ecommerce_storefront/static/src/img/category_covers/medicines.webp`
- `ab_ecommerce_storefront/static/src/img/category_covers/personal-care.webp`
- `ab_ecommerce_storefront/static/src/img/category_covers/beauty.webp`
- `ab_ecommerce_storefront/static/src/img/category_covers/vitamins.webp`
- `ab_ecommerce_storefront/static/src/img/category_covers/medical-devices.webp`
- `ab_ecommerce_storefront/static/src/img/category_covers/mother-baby.webp`
- `ab_ecommerce_storefront/static/src/img/category_covers/hair-care.webp`
- `ab_ecommerce_storefront/static/src/img/category_covers/hygiene-household.webp`
- `ab_ecommerce_storefront/changelog.d/2026-10-20-category-artwork.md`

Generation:

- Created using the built-in image-generation tool; resized and encoded using FFmpeg.
- Shared prompt direction: landscape 3:2 pharmacy category cover; refined minimal 3D product illustration; smooth matte surfaces, soft studio shadows, realistic proportions, centered composition, generous margins, and no text, logos, watermark, border, or embedded UI.
- Subjects: medicine bottle and blister pack; amber vitamin bottle and softgels; soap and pump bottle; blood-pressure monitor and stethoscope; serum, cream, and skincare tube; feeding bottle, teddy bear, and pacifier; pharmacy pouch and essentials; shampoo, conditioner, and hairbrush; household spray, hand soap, and cloth.

Validation:

- Visually inspected a contact sheet containing all nine optimized images.
- Verified nine native cover writes, image dimensions, matching category editor previews, public-user read access, and existing Arabic category labels.
- Both unchanged Arabic catalogs passed `msgfmt --check-format`; no new user-facing strings.
- Public HTTP checks passed for English and Arabic homepages on port 4092, including all eight images displayed per language: HTTP 200 and valid 960 × 640 image content. The existing homepage limit remains eight; all nine categories have covers in the editor.
- No connected browser was available for a full-page desktop/mobile screenshot check; artwork inspection and public HTTP validation were completed.
- Previous covers were empty; pre-write record metadata is saved in `/tmp/category-artwork-review/before-covers.json`.
- No Python, XML, JavaScript, SCSS, manifest, or permission changes were required. No module upgrade or server restart was needed.
