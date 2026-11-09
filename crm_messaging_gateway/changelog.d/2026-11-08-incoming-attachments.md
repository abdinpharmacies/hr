# Incoming Telegram attachments — 1.2.1

Current changes before commit:
- Choose the largest photo variant within the image limit, accept missing optional size metadata and retain the still image of a Telegram live photo.
- Normalize JPEG/PNG/WebP documents as images and common Markdown MIME aliases as Markdown documents.
- Receive static stickers as images, animated stickers as downloadable TGS originals and video stickers as WebM documents.
- Log only bounded attachment-type metadata and a source digest for unsupported Telegram attachments, excluding identifiers, names, captions and content.
- Validation evidence: `docs/incoming-attachment-validation.md` at repository root. Load the Odoo consumer before enabling the updated receiver and download worker.

Files changed:
- `app/__init__.py`
- `app/media.py`
- `app/providers.py`
- `tests/test_incoming_attachments.py`
- `changelog.d/2026-11-08-incoming-attachments.md`
