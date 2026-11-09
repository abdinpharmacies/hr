---
name: odoo-ecommerce-demo-deploy
description: Deploy this Odoo 19 ecommerce environment from e_commerce, or switch abdinpharmacies.com to it and restore the previous domain routing. Use only for these Abdin environments.
---

# Odoo Ecommerce Demo Deploy

Read [the deployment environment reference](references/deployment-environment.md)
before acting. Recheck mutable Git, service, database, and website state on every
run; recorded hashes and observed website content are context, not expected state.

An explicit request to deploy to this ecommerce demo authorizes the necessary
push, remote fast-forward pull, backup, targeted module upgrade, and service
restart for the named change. A request to review, diagnose, or prepare a plan
authorizes read-only checks only. Do not infer live deployment authorization from
the presence of this skill.

## Domain cutover and rollback

For switching `abdinpharmacies.com` to the existing ecommerce service/database,
or restoring the previous routing (including “رجعلي الوضع زي ما كان”), read
[production domain cutover and rollback](references/production-domain-cutover.md).
A documentation request authorizes documentation only. An explicit cutover or
rollback request authorizes its bounded routing and recorded URL-setting changes;
it does not authorize code deployment, database restoration, or data migration.
Use that reference instead of running the code-deployment workflow below.

Before any later deployment, determine whether this service now serves the main
production domain. Do not treat `store` as an isolated demo when both domains use
the same database. Report the actual production impact and verify the active
production domain in addition to the storefront routes below.

## Code deployment workflow

1. Inspect the local worktree, branch, intended commits, and `git diff --check`.
   Identify the exact commit range and affected Odoo modules. Do not commit,
   stage, or push unrelated user changes.
2. Confirm the local branch is `e_commerce`. Push only the intended committed
   changes to `origin/e_commerce` when the deployment request authorizes it.
3. Inspect the remote repository before changing it. Require branch
   `e_commerce`, a clean tracked worktree, and a remote branch hash matching the
   pushed local hash. Stop on divergence or unexpected changes.
4. Update the remote checkout only with `git pull --ff-only origin e_commerce`.
   Never force, reset, clean, stash, or discard remote changes.
5. Before any database upgrade, create a uniquely named PostgreSQL custom-format
   backup and verify that exact file with `pg_restore -l`. Do not continue if the
   backup or verification fails. The database backup does not include the
   filestore; do not claim a full restore point unless the matching filestore is
   also retained.
6. Upgrade only modules affected by XML views, data, manifest changes, or PO
   translations. Use the isolated upgrade command in the reference, inspect its
   exit status and complete upgrade log, and never use `-u base`. Do not add an
   upgrade merely for Python-only changes.
7. Restart `odoo19.service` to load changed Python and clear runtime caches, then
   require the service to be active.
8. Verify the deployed commit, clean remote tree, recent Odoo errors, and public
   storefront behavior in English and Arabic. Check `/shop`, `/ar/shop`, and a
   real product page for visible content, not only HTTP status.

## Stop Conditions

Stop without trying to repair or bypass the condition when:

- the local or remote branch is unexpected;
- local commits or changes cannot be separated from unrelated work;
- the remote tracked worktree is dirty or its history has diverged;
- the pushed and remote branch hashes do not match;
- backup creation or `pg_restore -l` verification fails;
- the targeted upgrade exits unsuccessfully or its log shows registry, view,
  translation, or module-loading errors;
- the service is not active after restart; or
- either language or the product-page smoke test fails.

Report the deployed commit, pushed/pulled state, backup filename and verification,
upgraded modules, service state, checked routes, and any warnings. Do not expose
credentials, private keys, connection secrets, or customer data from logs.
