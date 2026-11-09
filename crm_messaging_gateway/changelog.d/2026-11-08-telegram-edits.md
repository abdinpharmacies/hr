# Telegram edit reception — 1.4.0

- Subscribe to edited_message in Telegram polling and webhook setup; preserve the existing reception mode and durable polling offsets.
- Normalize edits with the original message reference, unique update identity, edit time and sender validation. Support text, captions, replacement media and location snapshots.
- Defer edit delivery without consuming retries until Odoo advertises edit support. Download only attachment revisions requested by the consumer.
- Keep location transport through native sendVenue. Enable the existing Callcenter account location flag separately in its private configuration, as requested.
- Tests cover subscription, normalization, ordering identities, malformed senders/dates, non-private chats, upgrade waiting and skipped stale attachment downloads.
