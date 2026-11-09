# Incoming attachments — 19.0.1.5.1

Current changes before commit:
- Accept UTF-8 Markdown as a private downloadable document, without rendering its content as HTML.
- Accept Telegram animated sticker originals after bounded gzip/JSON validation, and WebM sticker documents through existing signature validation.
- Preserve immutable media, service-only ingestion and scoped staff downloads. No schema or new source UI strings; existing English and Arabic error messages remain in use.
- Validation evidence: `docs/incoming-attachment-validation.md` at repository root.

Files changed:
- `__manifest__.py`
- `models/media.py`
- `tests/test_messaging.py`
- `changelog.d/2026-11-08-incoming-attachments.md`
