# Current changes before commit:

- Add the new `ab_website_admin_content` module for the Website Content administration workspace.
- Reuse the existing Odoo actions for Pages, Product Pages, and Technical Pages instead of duplicating business logic.
- Add scoped list and kanban styling derived from the storefront design tokens: Abdin green, orange accent, soft green backgrounds, white surfaces, compact rounded controls, and restrained shadows.
- Improve the Pages list with administrator-friendly columns for URL, indexed state, menu inclusion, SEO, publish status, website, last update, and preview.
- Improve the Product Pages list with image, URL, website categories, publish status, website, price, and preview.
- Improve Technical Pages with a clearly advanced route-focused list, preview action, and search view.
- Add backend Homepage Carousel management for slide image, sequence, active state, optional content, and per-slide CTA text/destination.
- Let admins choose between a normal text CTA button and an uploaded CTA image button for each carousel slide.
- Add a Link CTA style that makes the uploaded slide artwork the clickable destination and hides position controls that do not apply to a full-slide link.
- Include every enabled CTA style with a destination in the Homepage Carousel `With CTA` filter.
- Add CTA X/Y position and width controls with a draggable backend preview so admins can place the CTA over the slide image.
- Render backend carousel previews with the uploaded image MIME type and allow dragging the CTA from anywhere on the preview image.
- Keep backend carousel CTA placement coordinates left-to-right so RTL forms do not mirror the saved preview position.
- Smooth backend carousel CTA dragging by preserving the pointer grab offset and throttling form field updates during movement.
- Keep carousel CTA placement dragging active across long drags by updating Odoo fields only on drop and tracking pointer movement at document level.
- Store CTA placement relative to the visible slide image, preserve the last valid coordinates when a long drag is cancelled, and keep centering physical in RTL layouts.
- Center uploaded Image Button artwork inside the backend drag box so its visible position matches the text CTA and storefront output.
- Keep a visible selection outline and corner resize handles around Image Buttons, saving direct preview resizing through the existing CTA Width field.
- Apply the same persistent outline and direct corner resizing to text CTAs while keeping long labels contained in the selected width.
- Clear website template cache when carousel slides are created, edited, or deleted so homepage changes appear immediately.
- Add website-designer management access and public/portal read rules for active carousel slide images.
- Add Arabic translations for all new module strings in both `ar.po` and `ar_001.po`.
- Translate the new Link CTA style in both supported Arabic language files.

Files changed:

- `ab_website_admin_content/__init__.py`
- `ab_website_admin_content/__manifest__.py`
- `ab_website_admin_content/models/__init__.py`
- `ab_website_admin_content/models/website_carousel_slide.py`
- `ab_website_admin_content/security/ir.model.access.csv`
- `ab_website_admin_content/security/record_rules.xml`
- `ab_website_admin_content/views/content_views.xml`
- `ab_website_admin_content/static/src/js/carousel_position_preview.js`
- `ab_website_admin_content/static/src/scss/content_admin.scss`
- `ab_website_admin_content/i18n/ar.po`
- `ab_website_admin_content/i18n/ar_001.po`
- `ab_website_admin_content/changelog.d/current.md`
