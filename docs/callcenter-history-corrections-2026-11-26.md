# Callcenter history correction record — 2026-11-26

This record supplies descriptions in the requested `<module>/<TAG>: description`
format without changing published commit subjects or IDs. The original subjects
below are quoted exactly as stored in Git. Each description was checked against
the corresponding commit diff. These are documentation corrections, not replacement
commits, reverts or claims of additional implementation.

## Published commits

### `6a8d4ead5ccccd9fe1799a043072b211d487e012`

Original subject: `perf(ab_crm_sales_workspace): bound notifications and inbox queries`

Description: `ab_crm_sales_workspace/PERF: bound unread notifications, cache authorization per request and page inbox queries`

### `228a7930291af434730b039d0791c3c555e2c7e7`

Original subject: `perf(ab_crm_website): aggregate independent target activity`

Description: `ab_crm_website/PERF: aggregate independent website target activity before inbox pagination`

### `2e0a1bdff1c9f0138344e8f8ad8dead234f711fd`

Original subject: `perf(crm_messaging_gateway): drain eligible work in fair bounded cycles`

Description: `crm_messaging_gateway/PERF: drain eligible operations in fair bounded cycles and select website accounts`

### `f39f1c1569def4fc836e68e3eedaedbee1432072`

Original subject: `docs(ab_crm_sales_workspace): record performance release commit`

Description: `ab_crm_sales_workspace/DOCS: record the published workspace performance release in its changelog`

### `f74fba7e3f5ea35fec8f43a428ea59d862227795`

Original subject: `docs(ab_crm_website): record performance release commit`

Description: `ab_crm_website/DOCS: record the published website performance release in its changelog`

### `cabb3bd354cde3566341e9ffae716053f16ac580`

Original subject: `docs(crm_messaging_gateway): record performance release commit`

Description: `crm_messaging_gateway/DOCS: record the published bounded scheduler release in its changelog`

### `7dfe1b76aba282332134cb8340b072784f46c9af`

Original subject: `test(chatter): add performance evidence and validation tooling`

Description: `qa/TEST: add chatter performance samples, summaries and runtime packaging checks`

### `159db3ea9d96cda653b81a492a80e77a3675a95c`

Original subject: `docs(chatter): record performance results and deferred service draft`

Description: `callcenter19/DOCS: document local performance results, validation limits and the deferred service design`

## Reconciliation scope

The starting Callcenter commit is `159db3ea9d96cda653b81a492a80e77a3675a95c`.
New local commits retain this commit and all eight published commits as ancestors.
No amend, rebase, reset, force-push or wording-only revert is part of this correction.
The user requires local review before any push; no push is authorized.

Pending timing work is grouped by owning addon/gateway, followed by QA evidence
and the website reply-preview concurrency fix. Shared website README, manifest
and adapter changes are split so the timing release is `19.0.1.18.0` and the
subsequent concurrency release is `19.0.1.18.1`. Existing performance limitations
in the timing report remain applicable; committing evidence does not certify capacity.

The user subsequently authorized inclusion of FastRAG and all other pending
Callcenter additions. FastRAG connector and installer were compared byte for byte
with `origin/branch19` before import. Their provenance is commit
`2e065db2120d36590e05ce47f34e620b2edb6235`.
They are imported unchanged in separate commits; the installer is a generated
bundle whose canonical source remains `/opt/odoo19/fast_rag`. This import does not
install a service, activate an addon, or claim new runtime validation. The inherited
connector manifest lacks author/developer metadata and its Arabic catalogs cover
the upstream TLS additions; this reconciliation does not certify a complete
translation or retrofit the upstream implementation.

The pre-existing readiness audit, messaging measurement helpers and website
connection preparation tools are also retained as separate reviewable commits.
Committing tools does not authorize running their live configuration or send paths.

## Recovery snapshot

Before changes, staged and unstaged binary patches, the index listing, status and
all nonignored untracked files were saved under
`/tmp/callcenter-reconcile-20261126-131708`. This is a local recovery location,
not a portable release artifact.
