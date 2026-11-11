# Callcenter module updates — 2026-11-11

The existing module/type commit convention is retained. Implementation commits include their directly related tests and translations. Module documentation follows separately and records actual implementation hashes, authors, dates and file lists. Retired OMS addons are removed in separate commits after the supported live uninstall; their history remains in Git.

## Commits

| Commit | Exact subject |
| --- | --- |
| `dcb9c51e5ef119af0fa1dc1446de67ae775c3ce6` | `ab_crm_core/feat: rename conversation navigation to inbox` |
| `17051b0c69180a578b64ff012b5d5243469f54d8` | `ab_crm_messaging/feat: extend inbound evidence and receipt previews` |
| `77209fcb65977441d975ea0b906b8b0fdf3b8f1b` | `ab_crm_sales_workspace/feat: unify inbox contacts and route orders through sales` |
| `fc6257abbe9867771848594fa4aa50d99d981f1e` | `ab_crm_whatsapp_workspace/feat: extend reception and reconcile historical receipts` |
| `a89212d720d1f5219bfefc09c874d5925d36298e` | `crm_messaging_gateway/feat: harden channel reception and reconcile receipts` |
| `cc40efe78627615c0ff1338473a85a976d180456` | `ab_oms_sync/chore: remove retired synchronization addon` |
| `e956e6e93abff67d3ff260251001c7c18e6181c8` | `ab_oms_branch_adapter/chore: remove retired branch adapter` |
| `3ccfd701d128dfff41f9674e97d8d9d176d1addc` | `ab_oms_core/chore: remove retired order management addon` |
| `e56cf867ac313ac2362640f469c568ec16d152aa` | `ab_oms_website_adapter/chore: remove unused website adapter` |
| `fef9a7c813485a180c94f394670c4c9459ff7d92` | `ab_crm_core/docs: record inbox navigation update` |
| `60aef112bbae5214de2576aa9def6022178c4fb1` | `ab_crm_messaging/docs: record reception and receipt preview updates` |
| `6bb6760bad1da89ccae11122949d0d4d38299bf4` | `ab_crm_sales_workspace/docs: record inbox sales and archive updates` |
| `2fd4a75487b54674044ed0de9918bcfe8f81fa9a` | `ab_crm_whatsapp_workspace/docs: record reception and historical receipt updates` |
| `c37c7bf213785126738c3d3bf5880c7cf2640721` | `crm_messaging_gateway/docs: record reception recovery and reconciliation controls` |
| This documentation commit | `docs: record callcenter rollout and module commit history` |

## Verification

Commit preparation passed Python syntax checks for 46 files, XML parsing for 14 files, JavaScript syntax checks for 20 files, and format validation for eight Arabic catalogs. Whitespace checks and a high-confidence credential-pattern scan passed. Runtime tests and live verification were completed during implementation and are recorded in [the retirement report](messaging-legacy-retirement.md), with earlier feature evidence in the linked rollout records. No additional services or databases were changed during commit preparation.

Private backups, queue snapshots, credentials and generated runtime packages are excluded from these commits.
