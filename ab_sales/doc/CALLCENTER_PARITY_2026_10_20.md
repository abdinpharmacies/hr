# Callcenter parity implementation — 2026-10-20

Implemented against callcenter19 `bf8d8af7`, using pos19 `d9acd0e4` as the
feature reference. The shared ancestor is `4a76e326`. The pos19 checkout is
unchanged. This is a selective port; it does not merge the branch backend into
the dedicated callcenter.

## Features and architectural decisions

| Area | Callcenter implementation |
| --- | --- |
| Drafts | Per-token storage, revision conflicts, employee isolation, capacity admission, tombstones and safe reset/reconciliation. |
| Product search | Medicine/nonmedicine filters, exact/range price filters, improved product cards and keyboard behavior. |
| Stock display | API cache timestamps, stale indicators, manual refresh and protection against late responses or old snapshots. |
| Bill search | Doctor and item-type filters, pagination, local details, and protection against late search/detail responses. |
| Notes | Append-only annotations with author/time and branch access rules; financial notes remain fixed. |
| Contracts | Customer eligibility, contract columns, manual promotion selection and payer/discount validation. |
| Promotions | Updated eligibility and totals with first-submission snapshots for reporting. |
| Employee access | Existing PIN/session/role protections retained; cashier dependency removed from this dedicated callcenter module. |
| Printing | Optional shared printing service and sales bridge; receipts use local authorized bill data. |
| Delivery | Optional consent/instructions, negotiated provider capability, no local bot credentials or sending jobs. |
| Promotion reports | Local saved callcenter invoices filtered by dates, branch, product and promotion. No external SQL or inferred compensation settlement. |

All callcenter remote operations still use the authenticated branch API. Branch
providers continue to own their existing posting backend. This port does not
remove E-Plus from that backend. Existing callcenter connections, stable reference
encoding, automatic reconciliation and immutable retry payloads remain in place.
No new HR automation, synchronization cron, production migration or cleanup hook
is introduced.

Promotion report rows describe an invoice's recorded promotions and matching
invoice lines; they do not allocate a promotion to each product. Recorded invoice
discount/net values repeat across rows and are deliberately non-additive. Product
filters select rows without recomputing invoice totals. Promotion metadata such
as current ownership comes from the program; financial totals come from the
frozen submission snapshot. Invoices without a snapshot are not reconstructed.

## Installation and paired change

Use a fresh callcenter database. Do not upgrade or clean the existing development
database: the draft storage schema changed intentionally without migration code.
Install `ab_sales`, `ab_sales_contract`, `ab_sales_promo`, `ab_sales_doctor`, and
`ab_employee_access_sales`. Optional modules are `ab_sales_delivery_tracking`,
`ab_sales_printing` (which installs `ab_printing`), and `ab_sales_promo_report`.
Existing dependency declarations install their supporting modules.

The companion provider commit is `294c09c9` on `codex/callcenter-api-parity`, based on pos19
`d9acd0e4`, in `/opt/odoo19/worktrees/callcenter-api-parity`, with `ab_branch_api` version `19.0.5.5.4`. It advertises
`delivery_notifications` and accepts the consent/instructions fields. Deploy it
to the provider before enabling notification consent. Providers without the
capability continue to accept ordinary callcenter sales without those fields.
Retest each Branch Connection and verify selected store/database identity and
posting permission before enabling business use.

## Verification performed

Validation used isolated databases only:
`codex_callcenter_port_20261020`, `codex_callcenter_final_20261020`, and
`codex_callcenter_provider_20261020`. No existing development/production database
was upgraded. External posting was mocked.

- Clean installation of the complete callcenter selection: 48 modules loaded.
  The E-Plus connector and cashier module remain uninstalled.
- Clean provider installation with optional delivery module.
- 20 backend checks covering draft revisions/idempotency, tombstones, capacity,
  isolation, rejected/unknown immutability, annotations, price filters and
  branch-scoped stock snapshots.
- Four access checks for authorized/foreign branch annotations and forbidden
  direct draft cache reads.
- Five pricing/report checks for customer eligibility, payer split validation,
  immutable recorded totals, product-filter behavior and stable reference/unit
  encoding.
- Three retry checks for exact payload/identity/revision replay, changed
  destination rejection and uncertain outcomes after transport failure.
- Two real concurrent PostgreSQL checks for capacity admission and same-revision
  edits: only one writer succeeds.
- 27 mocked branch backend regression checks and two provider extension checks
  for delivery fields and capability negotiation.
- Four frontend regression groups for stale list/detail responses, delayed
  pricing mutations, branch switches and failed stock refreshes.
- Two optional-module checks for receipt preview/mocked dispatch and unsupported
  delivery rejection/ordinary-sale compatibility.
- Browser asset loading, employee PIN login, draft creation, slots and filter
  rendering with the combined optional modules; no console/page errors.
- Python/XML/JavaScript syntax checks, Git whitespace validation, both Arabic
  catalogs checked with msgfmt, and runtime English/Arabic action comparison.

Development test scripts and output remain outside the addons under
`/tmp/callcenter-port`. They are not packaged runtime modules.

## Remaining rollout validation

Before production use, exercise a controlled sale, retry and return against the
real intended branch backend, verify cashier visibility and the original token,
and confirm stock/cash effects occur exactly once. Exercise two actual employee
browser sessions and conflict recovery. Test printer hardware and optional
delivery notification receipt with the intended branch configuration. These
checks were not performed here: no live invoice, return, printer job or business
notification was sent. Existing PyCharm services were left running.

## Handoff state

The callcenter changes are in `/opt/odoo19/worktrees/callcenter` and remain
uncommitted. The worktree files are writable, but its Git metadata directory
`/opt/odoo19/custom-addons/.git/worktrees/callcenter` is still root-owned; no
ownership or Git-index workaround was applied. The API companion has its own
clean committed worktree. The original pos19 checkout remains clean.
