# Saved reply content — Abdin Pharmacies

Current changes before commit:

- Review and revise the existing 22 Arabic/English saved-reply pairs for صيدليات عابدين / Abdin Pharmacies.
- Use consistent, polite Egyptian Arabic and concise English. Brand greetings, branch checks, contact/order messages, confirmations and closings; retain medicine-use and alternative enquiries for pharmacist review.
- Preserve template titles, XML IDs, active state and every existing required parameter. Do not introduce delivery guarantees, fixed prices, return promises or medical claims.
- Apply the 44 body updates to the existing callcenter intake branch through authorized Odoo ORM writes. Preserve three archived legacy replies and verify no message/queue records were added.
- This is saved-record content maintenance plus its CSV source mirror; it changes no addon runtime code and requires no module upgrade or process restart.

Files changed:
- resources/pharmacy_cosmetics_saved_replies.csv
- VALIDATION.md
- changelog.d/2026-11-08-abdin-saved-replies.md

Validation evidence: `/tmp/abdin-template-review/`. The original content is retained privately for review; fresh-transaction readback verifies all 44 records and existing agent access.
