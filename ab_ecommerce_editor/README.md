# Abdin eCommerce Editor

Odoo 19 content studio for editor-owned pages and articles. The Owl workspace follows the visual language of `ab_core_ui`, with staged entrance animations, animated panels, responsive canvas transitions, block selection feedback, and reduced-motion support. All styles and components belong to this module.

## Using the studio

Open **eCommerce Editor** from Odoo. Create a page or article, select a block on the canvas, and edit its content or design in the inspector. Select **Page settings** to edit the page title, URL, summary, category, cover image, and page design tokens.

- Add, drag, reorder, or remove hero, heading, text, image, button, and divider blocks. Drag directly on a preview block or in the layer list; the highlighted drop edge indicates its new position. Blocks swap with a coordinated hop, including when using the up/down buttons or undo/redo. Up/down buttons provide a keyboard and touch alternative to dragging. Library/editor navigation includes a short exit followed by the staged entrance. Reduced-motion preferences disable these travel effects.
- Change fonts, size, weight, italics, colors, spacing, corners, borders, alignment, mobile size, and device visibility.
- Switch English/Arabic content and desktop/mobile previews. Arabic content uses RTL.
- Undo/redo edits, save drafts, and save named page templates or reusable sections.
- Edit reusable templates from the library. Linked draft instances resolve their latest source when reviewed; detached instances become independent blocks.
- Save revisions and restore an older revision as a draft. Existing published content stays available during draft edits.
- Use **Storefront preview** after saving to view the draft inside the existing storefront header and footer. This route requires editor access. **Open live page** opens the released version.

The current editor manages its own content routes. It does not import or rewrite existing `website.page`, `blog.post`, homepage, catalog, cart, or checkout templates. Its published pages use the current storefront layout. Commerce data and operations remain owned by Odoo's existing commerce modules.

## Publishing and access

| Role | Access |
| --- | --- |
| Editor | Create and edit drafts/templates, upload images, save and restore versions, submit for review |
| Reviewer | Editor access plus return reviewed/scheduled work to draft |
| Publisher | Reviewer access plus publish or schedule a reviewed snapshot |
| Settings administrator | Inherits Publisher through module-owned security XML |

Documents, templates, and revisions have company record rules. Public reads are restricted to the current website and a published revision. Public methods validate permissions before scoped elevation. Native website designer permissions are not granted to editors.

Submitting for review freezes the complete content, resolved reusable sections, styles, translations, and SEO values. Publishing and scheduled publishing release that exact snapshot. Scheduled content is checked every five minutes; publication is skipped if its scheduler no longer has publisher access or access to the company. Scheduled dates entered in the browser are converted to UTC.

Revisions retain their author/date and release publisher/date. Their payload cannot be edited or deleted. Restoring a revision creates a draft; submit and publish it to roll back the public content. Draft save tokens prevent a stale session from overwriting a newer save, including saves within the same second.

Images uploaded through the editor remain private until included in a release. JPEG, PNG, and WebP uploads are limited to 5 MB and 20 million pixels. Image blocks require descriptions before review. Text contrast must reach 4.5:1. The content schema accepts plain text, approved style properties, and safe links; it does not execute HTML, JavaScript, expressions, or arbitrary JSON code.

## Routes and JSON contract

| Route | Purpose |
| --- | --- |
| `/editor/page/<slug>` | Published page |
| `/editor/blog/<slug>` | Published article |
| `/editor/blog` | Latest published articles |
| `/editor/preview/<document_id>` | Authenticated draft preview, no-store/noindex |
| `/api/v1/editor/content/<kind>/<slug>` | Current published configuration |
| `/api/v1/editor/content/<kind>/<slug>/versions/<number>` | A specific previously released revision |

The JSON response is wrapped in `data`. [The v1 JSON Schema](static/schema/content-v1.json) describes this payload. Query parameters:

- `schema=1`: unsupported schema versions return HTTP 409.
- `lang=en_US`, `lang=ar`, or `lang=ar_001`: explicit content language; Arabic normalizes to `ar_001`.
- `components=hero,heading,text,image,button,divider`: capabilities supported by the consuming renderer. Unsupported components become `unsupported` entries with a plain-text fallback and are listed in `unsupported_components`. Clients must handle that fallback explicitly.

Responses contain the schema version, revision number, resolved content, design tokens with Flutter overrides, SEO metadata, and release time. ETags vary by website, revision, language, and capability list; matching conditional requests return 304. Responses use a bounded 60-second cache. Unreleased revisions are never exposed by the version route.

The web renderer uses the shared tokens plus web overrides. Flutter rendering and integration in `/home/abdin_02/flutter_apps/ab_modern_ecommerce_app` are deferred at the user's request. A Flutter renderer must register these components and properties before consuming the configuration; this module does not add executable components to an installed app.

## Validation

Development checks run on the neutralized database `codex_editor_validation_20261028`, using HTTP 5069/gevent 5072, workers 0, and cron threads 0. Test source and screenshots are kept outside the runtime addon in `outputs/ab_ecommerce_editor_validation`. Both Arabic catalogs are exported from Odoo's POT references and checked with `msgfmt --check-format`.

The recorded baseline passed 23 backend regression tests, 10 browser checks, and JSON Schema validation for English, Arabic, and compatibility-fallback responses. Later updates have focused validation records; the latest drag-to-trash interactions still need browser verification. See the local `outputs/ab_ecommerce_editor_validation/VALIDATION.md` for the evidence and remaining scope. These validation artifacts are outside this module's Git import. The module is installed in local `ecom19`; refresh Odoo and open **eCommerce Editor**.

The module has no demo records, install hooks, migrations, external database writes, or shared frontend patches. Its one scheduled task implements the requested publishing schedule.
