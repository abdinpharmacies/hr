# Parallel claim review and governed payment preparation

Baseline: 78951ca6 · hager yasser · 2026-10-26 · ab_supplier_claim_cycle/FEAT: Enable Supplier and Section edits in open claim stages

Current changes before commit:

- Submitted claims are readable across claim-cycle roles within company scope.
- Parallel operational/financial review, tax discount/evidence gates, working-day preparation SLA and bank return destinations.
- Protected workflow actions, immutable document versions and revision-linked payment approvals.
- Versioned migration preserves legacy amounts, attachments, history and payment-stage continuity exceptions.
- Shared bilingual form, actionable queues, HTTP/security/migration tests and upgrade documentation.

Files changed: `__manifest__.py`, `models/`, `security/`, `views/parallel_workflow.xml`,
`wizard/`, `migrations/19.0.5.0.0/`, `i18n/ar.po`, `i18n/ar_001.po`, `tests/`,
`README.md`, `VALIDATION.md`.

Design preservation follow-up:
- Extend the original form rather than replacing it. Preserve its colors, panel
  divisions, rounded boxes, notes and timeline exception styling.
- Add paired review stages, preparation, tax amounts and document audit to that design.
- Keep bilingual action labels clear during parallel reviews and retain list colors.
- Additional affected file: `static/src/scss/claim_design.scss` (scoped parallel layout only).

- Removed the chatter panel from the shared claim form through view inheritance;
  existing workflow history, document history and stored messages are preserved.
