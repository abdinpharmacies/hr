# Supplier Claim Cycle

Odoo 19 · version 19.0.5.0.0 · Developer: Alhassan Hossny

## Workflow and permissions

Check/transfer: Draft → parallel Inventory/Purchasing → parallel Tax/Supplier
Accounts → Secretarial preparation → Bank Accounts → Ready to Close → Closed.
Cash skips operational review and Bank Accounts.

All claim-cycle roles can read submitted claims, decisions, documents and history,
including closed/archived records. Drafts are restricted to their creator,
Secretarial and Manager. Global company rules cover claims, history and document
versions. Use the correct current Odoo company for branches. Legacy North/South
area is a classification, not an independent branch authorization mechanism.

Each department can act only at its stage with a pending/deferred decision.
Managers follow the same gates. Reviewer is read-only even with another departmental
role; Manager takes precedence. Direct state, decision, calculation and history
writes are rejected. Archive instead of deleting claims.

Operational rejection preserves the other completed approval and cancels unfinished
review. Financial rejection restarts financial decisions after correction. Deferral
requires a reason and follow-up date and permits the parallel department to continue.
Tax review is required except for Non-tax Payment. Tax chooses whether to apply the
fixed 1% discount and must upload evidence. Supplier Accounts cannot approve first.
Claim amounts use Float with two-decimal precision and centralized decimal rounding.

## Preparation and evidence

Set `supplier_claim_secretarial_sla_days` on the company form (default 2).
The deadline counts working dates after preparation starts, excluding calendar
holidays. Configure the company calendar before use. Changing the setting does not
recalculate existing deadlines.

Supplier Accounts owns supplier cheque evidence; Tax owns tax evidence; Secretarial
owns payment requests; Bank Accounts owns optional bank documents. Preparation
requires financial approvals, applicable supplier/tax evidence and a payment
request for every payment method. Bank action requires completed preparation.

Bank rejection requires a destination and reason. Return to Secretarial preserves
supplier/tax documents and requires corrected payment-request content. Return to
Supplier Accounts suspends preparation, resets its review and conditionally resets
Tax. Payment requests are invalidated on either return.

Manager-only document replacement requires a reason, increments the document
revision and preserves previous content/filename with actor and timestamp. It
invalidates dependent payment requests/bank decisions. Amount or tax-type changes
restart financial review. Payment requests and bank approvals reference the
supplier-document revision used.

All Claims includes submitted, closed and archived records. Dedicated queues cover
pending departmental work, drafts, corrections, payment requests, returned requests
and overdue preparation. Every department uses the same bilingual form. The form
extends the original colored panels, box divisions and timeline design; the new
Tax and preparation sections reuse that styling.

## Supported upgrade from 19.0.4.2.1

Production upgrade requires separate explicit authorization.

1. Preserve the original addon revision/configuration. Back up PostgreSQL using
   `pg_dump -Fc` and copy the matching filestore. Record claim/history counts.
2. Restore into a neutralized isolated database; disable external integrations
   and cron. Never validate against a database used by production workers.
3. Audit legacy amounts. Surrounding whitespace and conventional comma thousands
   separators are supported. Malformed, zero, negative and nonfinite values stop
   the upgrade with affected claim IDs, before any conversion is written.
4. Legacy claims have no company ownership. A single active company is assigned
   automatically. With multiple companies/branches, set system parameter
   `ab_supplier_claim_cycle.migration_company_map` to a reviewed JSON object mapping
   every legacy claim ID string to a company XML ID, for example
   `{"123": "base.main_company"}`. Missing/invalid assignments stop migration.
   Review this mapping against actual business ownership; creator's current company
   is not used to guess historical ownership.
5. Run targeted `-u ab_supplier_claim_cycle` with the correct addons path. Upgrade
   `ab_supplier_claim_cycle_telegram` too when installed. Never use `-u base`.
6. Compare counts, amount totals, attachment bytes/filenames, decisions, company
   ownership and original historical states. Test role access, both languages,
   calendar deadlines and notification queues before authorizing production.
7. If validation fails, restore the database and filestore backup with the original
   code into a separate recovery database. Do not downgrade the migrated schema.
   Investigate the failure and repeat the isolated rehearsal first.

Migration preserves original amount text in its legacy database column and verifies
supplier document content/filename equality. Inventory/Purchasing map to Operational
Review; Supplier Accounts maps to Financial Review. Return resume stages are mapped;
historical event states remain unchanged. Tax-required financial claims start pending.

Legacy Bank Accounts claims stay there under a protected, logged tax/preparation
exception. No human approval or missing document is fabricated. `not_required` for
these migrated tax decisions denotes this explicit exemption. Ready-to-Close and
Closed claims stay in place. Returns/replacements remove the exception and enforce
new gates. Legacy claims already returned by Bank Accounts remain returned to
Secretarial and resume financial review after correction, so new tax/preparation
gates can be satisfied without extending the in-progress-bank exemption. This
resume-stage adjustment is explicitly logged.

## Optional Telegram

`ab_supplier_claim_cycle_telegram` supports parallel stages, preparation and bank
returns. Recipients must have claim access and company membership. Sends are queued;
tests mock delivery. Claim links use the registered All Claims action.

The older `ab_supplier_claim_workflow_telegram` addon is incompatible with this
repository's existing baseline: it inherits absent `ab_supplier_claim_escalation`
and `ab_supplier_claim_manager_service` models and targets an absent `status` field.
Do not install it with this release without a separate compatibility project.

## Validation

Run on an isolated database with the correct addons paths and unused ports:

```bash
odoo-bin -c /path/to/isolated.conf -d supplier_claim_test \
  -i ab_supplier_claim_cycle,ab_supplier_claim_cycle_telegram \
  --test-tags=/ab_supplier_claim_cycle,/ab_supplier_claim_cycle_telegram \
  --workers=0 --max-cron-threads=0 --http-interface=127.0.0.1 \
  --http-port=5069 --gevent-port=5072 --stop-after-init
```

Use `-u` for upgrade validation. HTTP/browser tests require HTTP enabled, Chrome
and `websocket-client` in the test interpreter. Tests cover business/security rules,
combined roles, company isolation, SLA holidays, immutable documents, translations,
HTTP downloads, browser rendering and mocked Telegram delivery. See `VALIDATION.md`
for measured results, migration recovery evidence and remaining deployment checks.
