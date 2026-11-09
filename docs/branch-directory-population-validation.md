# Callcenter public branch directory population

Completed source implementation and data import on 2026-11-08. Runtime loading of
the Python visibility change requires the user's next Odoo restart.

## Diagnosis and source

The live `callcenter` database contained no `ab_crm_branch_location` profiles.
The earlier implementation shipped an unmapped staging CSV without installing
records. In addition, the picker intersected profiles with allowed fulfillment
stores. The Telegram workspace allows store codes `29` and `140`; only El Ataba
(`29`) occurs in the storefront directory.

The user selected the `e_commerce` storefront as the source and explicitly chose
**Show all 42 public locations**. Its `branches.js` reads rendered cards from
`ab_ecommerce_storefront/views/branches_data.xml`. Source commit:
`bd93516314aa0062f1cd6cddc55b550a5e10471d`.

All 42 English names, addresses and coordinates were extracted from that XML.
Arabic names and addresses were extracted from its translation catalogs, with
agreement checked between `ar.po` and `ar_001.po`. Every Arabic branch name has
exactly one active Callcenter store with the same name after removing only the
store's `فرع ` prefix. No fuzzy matching or new operational stores were used.
The shared `19036` hotline comes from `branches_templates.xml`; individual branch
phones remain empty.

The exact mapped import and source hashes are retained in:

- [Callcenter import CSV](data/callcenter-branch-locations.csv)
- [Source provenance](data/callcenter-branch-locations-provenance.json)

## Applied data and source changes

A dedicated database backup was created and its archive listing verified at
`/tmp/branch-directory-fix/backup/callcenter-before-branch-import.dump`
(53,303,680 bytes). The existing CSV validation/import and profile review methods
then committed **42 active, reviewed profiles**, each at revision 2, to the live
database. Profile history records the executing Odoo actor and timestamps; each
review note records the user's source selection and exact mapping method.

Store configuration and Telegram account switches were compared before and after
the import and remained unchanged. CRM and OMS already reference this same
directory. No customer messages were sent.

Workspace version **19.0.1.13.2** changes only the public-directory selection rule:
reviewed active profiles from the employee session's company are eligible when
their mapped store is active, regardless of that store's fulfillment eligibility.
Employee-session validation, conversation ownership and assignment, company
isolation, provider eligibility, review/revision checks and sending gates remain.
Order routing, inventory access and customer delivery details are unchanged.

## Verification

- Isolated 42-row import: passed, including duplicate-record resolution and all
  126 English/Arabic previews. Test records were rolled back.
- Fresh live read-only verification: all 42 committed profiles, mappings, review
  state and 126 previews passed; CRM/OMS views and the shared action are present.
- Targeted isolated upgrade with `--dev=xml` and the full `TestWorkspace` class:
  **78 test methods passed, zero failures/errors**. Odoo's statistics line counts
  80 including setup; the result summary reports 78 test methods.
- Added coverage for all 42 public branches, bilingual search/previews, locations
  outside fulfillment scope, unchanged order store/version/delivery details,
  continued rejection of unauthorized order routing, archived-store exclusion
  and cross-company preview/send rejection.
- Python syntax and `git diff --check`: passed. Both Arabic catalogs passed
  `msgfmt --check --check-format`; only existing metadata-header warnings remain.
  This change introduces no new UI strings.
- Browser verification could not run because the browser connector failed to
  read the live tab. No user drafts or browser pages were changed.

Validation used the isolated `crm_branch_final_test_20261108` database on
5069/5072 with workers and cron disabled. Live verification/import shells used
no HTTP and no cron. Evidence is under `/tmp/branch-directory-fix`.
The runtime package `ab_crm_sales_workspace-19.0.1.13.2.tar.gz` in that directory
excludes development tests, static test assets and caches.

## Runtime status

The 42 saved profiles are already visible in the manager's **Branch Locations**
directory. The running PyCharm process was not restarted or patched. Its picker
will retain the old fulfillment filter until restart. Use the existing config
with the targeted upgrade arguments:

```text
-d callcenter -u ab_crm_sales_workspace
```

Close and reopen **Choose branch** after restart. The live account's
**Telegram Branch Locations Enabled** switch was false and remains false;
gateway/Odoo sending activation and live provider sends were not part of this
directory-population change.
