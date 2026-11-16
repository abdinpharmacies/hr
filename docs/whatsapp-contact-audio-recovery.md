# WhatsApp contact and recording recovery — 2026-11-11

## Confirmed diagnosis

- The recent native incoming voice note reached the durable queue and Odoo, but its media was marked failed. FFmpeg and ffprobe were absent from the worker environment; the missing executable had been collapsed into an invalid-media failure.
- The same recording sent as a document was classified unsupported because document-to-audio normalization was missing. Supported audio MIME types now map to audio while retaining the original provider message type.
- The native voice note was downloaded using the existing account credential and validated with the Ubuntu repository codec package in a private temporary directory. The data was not printed, forwarded or sent as a new message.
- The user confirmed attachment → Contact. The resent callbacks logged `invalid_contact_cards:extra_card_fields`, confirming that unknown top-level provider metadata caused the strict allowlist to reject the whole card before queue storage. Native cards now normalize to supported fields before validation, preserving strict types/limits and the original source digest; unknown metadata is neither rendered nor used to link identities. Diagnostics never include contact values or unknown field names.

## Changes and validation

Missing codec tools now produce a retryable dependency failure without a provider send or terminal incoming-media update. Invalid audio headers remain rejected. Successful authenticated Odoo media recovery clears the stale failure reason while preserving immutable ready bytes and existing account/company/branch access checks.

- 84 gateway tests passed with the installed codec tools, including audio conversion, native media retrieval, audio-file normalization, dependency retries, contact diagnostic redaction and signed contact callback ingestion.
- The isolated `callcenter_retirement_core_test` media ingestion/private-download test passed, covering recovery from failed state and access isolation.
- Earlier notification, map-link and WhatsApp branch-location changes are preserved.

## Runtime work

The user installed the repository FFmpeg package, reloaded the WhatsApp gateway and messaging worker, restarted their PyCharm Odoo process, and resent the native contact. The final gateway reload is complete. Incoming contact events 130 and 131 completed on their first attempt and produced Odoo messages 135 and 136, each retaining one supported contact card. The original voice media is ready (3,937 validated bytes), with the stale failure reason cleared. Recovery was audited against incoming event 126 with its original fingerprint preserved. Gateway, worker and Telegram receiver are active; temporary validation ports are released. Live storage is verified; this final check did not perform a new browser rendering test.

No agent-created customer messages are used. Recovery of the existing voice note uses only authenticated `receive_media`, with an operator audit and an unchanged incoming-event fingerprint; it does not replay the incoming event or create an outgoing operation. The unsupported audio-document event has no retained provider file ID and cannot be reconstructed from its diagnostic digest.
