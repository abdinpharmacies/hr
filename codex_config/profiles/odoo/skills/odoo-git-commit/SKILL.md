---
name: odoo-git-commit
description: Create atomic Odoo commits using module/TAG subjects and Odoo-specific change categories. Inspect the working tree and diffs, identify logical changes by Odoo module and feature area, split mixed changes when practical, stage only the intended changes, validate the staged diff, and create one focused commit per logical change.
---

# Odoo Git Commit Skill

Create clean, atomic, reviewable Git commits for Odoo projects.

The primary rule is:

> **One commit = one logical change in one Odoo module.**

Never combine files from two Odoo modules in one commit, even when the changes support the same feature. Use separate commits in dependency order. Multiple independent changes within one module also require separate commits.

Do not group unrelated Odoo modules, features, bug fixes, documentation, formatting, or tests into one commit merely because they were changed at the same time.

---

## Execution Mode

Before staging, committing, or pushing, determine whether the user wants **push to remote**, **local commits only**, or **audit only**. Honor an explicit choice in the current request or an established choice for the same ongoing task; do not ask again unless the user changes it. Do not carry authorization from a completed task into a new task.

If the mode is unspecified, ask one question in the user's language:

> تحب أعمل الكوميتات وأرفعها على الريموت، ولا أحتفظ بيها لوكال، ولا أعمل Audit فقط من غير كوميتات؟

Wait for the answer before changing files, the index, commit history, or remotes. Read-only inspection may continue while waiting. A generic request to "commit" or "start" does not choose between these modes, and silence is not a choice.

- **Push to remote:** Create and validate the requested atomic commits, then push them to the intended remote and branch. Verify the outgoing commits and destination first; clarify any ambiguous destination or unrelated outgoing commits before pushing. Report whether the push succeeded.
- **Local commits only:** Create and validate the requested atomic commits, keep them local, and do not push.
- **Audit only:** Inspect Git state and diffs, report findings, and propose module-specific commit groups and subjects. Do not edit files, stage or unstage changes, create commits, or push. Label proposed subjects as proposals, not created commits.

The staging and commit instructions below apply only to the two commit modes. An explicit mode authorizes its stated actions without another routine confirmation; it does not authorize history rewriting or unrelated changes.

---

## Commit Format

For Odoo module changes, use:

```text
<module>/<TAG>: <description>
```

Examples:

```text
ab_ecommerce_storefront/IMP: add return policy page
ab_ecommerce_storefront/FIX: limit purchase options to supported units
ab_website_sale_product/IMP: run website product sync in background
ab_website_sale_product/FIX: preserve manually edited website images
ab_website_seo_optimization/IMP: add catalog-aware SEO enrichment workflow
```

For repository-wide changes that do not belong to one Odoo module, use:

```text
<TAG>: <description>
```

Examples:

```text
CHORE: update project dependencies
CI: add automated module validation
DOCS: update development guide
```

Use the module-first format selected by the user, not Conventional Commit parentheses or Odoo's upstream tag-first format. Keep the description lowercase and imperative.

---

# Commit Tags

Use one uppercase tag. These categories are based on the [official Odoo 19 Git guidelines](https://github.com/odoo/documentation/blob/19.0/content/contributing/development/git_guidelines.rst), checked on 2026-10-13.

Upstream uses `[TAG] module: description` and supports explanatory bodies. This skill intentionally keeps the user's `module/TAG: description`, one-line messages, and strict one-module boundary. The generic image cheatsheet is background reference, not the authoritative tag list for this Odoo skill.

## Official Odoo categories

| Tag | Purpose |
| --- | --- |
| `FIX` | Correct defective behavior. |
| `REF` | Restructure an existing implementation. |
| `ADD` | Introduce a new module. |
| `REM` | Remove obsolete code, views, or other resources. |
| `REV` | Undo an earlier commit. |
| `MOV` | Relocate or rename files or code. |
| `REL` | Record a release. |
| `IMP` | Extend or improve existing functionality. |
| `MERGE` | Identify an actual merge commit. |
| `CLA` | Record contributor-license signing. |
| `I18N` | Update translations. |
| `PERF` | Improve runtime performance. |
| `CLN` | Clean up code. |
| `LINT` | Apply lint corrections. |

## Local project extensions

These tags preserve useful project distinctions; they are not listed in the official Odoo 19 tag list above.

| Tag | Purpose |
| --- | --- |
| `DOCS` | Add or update documentation. |
| `TEST` | Add or change tests as the primary task. |
| `BUILD` | Change build tooling, packaging, or dependency installation. |
| `CI` | Change continuous integration workflows. |
| `CHORE` | Perform routine maintenance, including routine dependency version updates. |

## Selection rules for custom addons

- Use `ADD` only for a new addon. A new field, wizard, report, controller, or workflow within an existing addon normally uses `IMP`; correcting broken behavior uses `FIX`.
- UI and UX improvements use `IMP`, UI bugs use `FIX`, and formatting or lint passes use `LINT`. Do not generate `ux`, `style`, or `feat` tags for new commits.
- Use `REF` for structural changes that preserve intended behavior, `CLN` for smaller cleanup, and `PERF` for a targeted performance change supported by evidence. Removing resources as the primary task uses `REM`.
- Keep pure moves in `MOV` commits and behavior changes in subsequent commits. Odoo XML IDs and model names remain stable unless their rename is explicitly required by the task.
- Use `I18N` for translation-only work. English strings and both Arabic catalogs needed for a feature or fix stay with that `IMP` or `FIX` commit; do not split files that are required for the same logical change.
- Keep required imports, manifest entries, assets, ACLs, views, and directly related tests with their feature. Several file types do not imply several logical changes.
- Independent documentation and tests use `DOCS` and `TEST`. Documentation or regression tests directly supporting a feature may remain with it.
- Use `CHORE` for routine dependency updates, `BUILD` for changes to installation or packaging, and `FIX` when the dependency update resolves a specific defect.
- `REV`, `REL`, `MERGE`, and `CLA` classify work already requested; they do not authorize reverting, releasing, merging, signing agreements, or publishing. Never use `MERGE` to bundle unrelated changes.
- `REM` concerns source resources, not physical deletion of protected business records. Preserve the project's archival and data-integrity rules.

Examples:

```text
ab_queue_monitor/ADD: introduce job monitoring dashboard
ab_sales/IMP: add order review workflow
ab_sales/FIX: preserve branch access during order review
ab_sales/I18N: translate order review messages into Arabic
ab_sales/REF: extract order review validation
ab_sales/PERF: batch order review lookups
ab_sales/CLN: simplify redundant review conditions
ab_sales/LINT: normalize review model formatting
ab_sales/MOV: relocate review helpers
ab_sales/REM: remove unused review template
ab_sales/TEST: cover unauthorized order review
ab_sales/DOCS: document order review workflow
```

Historical lowercase commit subjects remain unchanged when quoting history or recording changelogs. This naming convention applies to new commits; it does not authorize rewriting existing history.

---

# Odoo Module Scope

The scope should normally be the actual Odoo module name.

Examples:

```text
ab_ecommerce_storefront
ab_website_sale_product
ab_website_seo_optimization
ab_sales
ab_stock
ab_account
```

Determine the module from the repository structure and actual changed files.

Typical indicators include:

```text
__manifest__.py
models/
views/
security/
data/
wizard/
controllers/
static/
tests/
```

Do not invent module names.

Do not use vague scopes such as:

```text
misc
general
backend
frontend
odoo
code
```

when the actual module can be identified.

---

# Atomic Commit Rule

Every commit must represent one coherent logical change.

For example, if the working tree contains:

```text
ab_ecommerce_storefront
    account UI fix

ab_website_sale_product
    sync optimization

ab_website_seo_optimization
    SEO enrichment

README
    documentation update
```

Do NOT create:

```text
IMP: update ecommerce project
```

Instead, separate the changes:

```text
ab_ecommerce_storefront/FIX: align account password mask in RTL layout
ab_website_sale_product/PERF: optimize website product sync
ab_website_seo_optimization/IMP: add catalog-aware SEO enrichment workflow
DOCS: update project documentation
```

The exact messages must be derived from the actual staged diff.

---

# Inspect Before Committing

Before creating any commit, inspect the repository.

Run:

```bash
git status --short
```

Then inspect the relevant changes:

```bash
git diff
```

If anything is already staged:

```bash
git diff --cached
```

When useful, inspect the summary:

```bash
git diff --stat
```

Never generate a commit message from filenames alone.

Never assume that all working-tree changes belong together.

---

# Detect Logical Changes

After inspecting the diff, classify changes by:

1. Odoo module
2. Functional area
3. User-visible behavior
4. Bug fix
5. Refactor
6. Test
7. Documentation
8. Performance
9. Build/CI
10. Repository maintenance

Group files together only when they implement the same logical change.

For example:

```text
controller + template + JS + SCSS + test
```

may belong to one commit if they implement one feature.

Do not split tightly coupled implementation files merely because they have different extensions.

---

# Split Mixed Changes

If one file contains unrelated changes, use interactive staging.

Preferred:

```bash
git add -p
```

Use the interactive staging options to select only the hunks belonging to the current logical change.

If necessary, split or edit hunks.

Never discard unrelated work just to create a clean commit.

Never use destructive commands to simplify staging.

---

# Staging Rules

Prefer targeted staging:

```bash
git add <specific-files>
```

or:

```bash
git add -p
```

Avoid blindly using:

```bash
git add .
```

unless inspection has established that the entire working tree is intentionally one coherent change.

Never stage:

```text
.env
credentials
private keys
secrets
database dumps
local configuration
editor files
debug output
temporary files
generated artifacts
```

unless the repository intentionally tracks them.

---

# Odoo-Specific Safety

Pay special attention to Odoo changes involving:

```text
__manifest__.py
security/
ir.model.access.csv
record rules
views/
data/
demo/
migrations/
models/
controllers/
wizard/
static/
i18n/
```

Do not combine unrelated changes to:

* security rules
* business logic
* UI
* translations
* data
* migrations
* tests

unless they form one intentional logical change.

Preserve existing XML IDs and module ownership.

Do not rename or move Odoo records merely to make the diff cleaner.

Do not introduce unrelated cleanup into a functional commit.

---

# Tests

When a commit changes Odoo behavior, inspect the repository for relevant tests.

If tests are part of the same logical change, keep them with the implementation:

```text
ab_website_sale_product/FIX: preserve manually edited website images
```

may contain:

```text
models/
tests/
```

in the same commit.

If tests are independent or represent a separate test-only change, use:

```text
ab_website_sale_product/TEST: add website image preservation coverage
```

Do not invent test commands.

Use the project's existing test configuration and conventions when available.

---

# Commit Message Rules

The description must:

* start with lowercase;
* use imperative/present-tense wording;
* describe the actual change;
* be concise;
* have no trailing period;
* contain no commit body;
* contain no footer;
* contain no unrelated implementation details.

Prefer:

```text
ab_ecommerce_storefront/IMP: add return policy page
```

Avoid:

```text
ab_ecommerce_storefront/IMP: Added a new return policy page.
```

Avoid:

```text
ab_ecommerce_storefront/CHORE: changes
```

Avoid:

```text
ab_ecommerce_storefront/IMP: modify several files for improvements
```

---

# Derive the Message From the Staged Diff

The final commit message MUST be based on:

```bash
git diff --cached
```

not:

```bash
git diff
```

and not the filenames alone.

Before committing, verify that:

```text
staged changes
        ↓
one logical change
        ↓
correct module
        ↓
correct tag
        ↓
accurate description
```

The commit subject must describe what is actually staged.

---

# Commit Sequence

When multiple logical changes exist, process them one at a time.

For each logical change:

```text
1. Identify the change
2. Stage only its files/hunks
3. Inspect git diff --cached
4. Determine module
5. Determine commit tag
6. Generate one-line subject
7. Commit
8. Verify the commit
9. Continue with the next logical change
```

After committing, inspect:

```bash
git status --short
```

Then continue only with remaining intended changes.

---

# Existing Staged Changes

If the user has already staged changes:

```bash
git diff --cached
```

must be inspected first.

Treat the existing index as intentional.

If the staged changes form one coherent logical change, do not unnecessarily unstage them.

If they contain unrelated changes, explain the separation and use targeted staging only when necessary.

Never silently destroy the user's staging state.

---

# Existing Commits and Amend

Use:

```bash
git commit --amend
```

only when the user explicitly intends to modify the latest commit.

Examples:

* forgotten file
* corrected commit subject
* correcting the latest local commit

Do not amend a shared/pushed commit unless the user explicitly requests history rewriting.

Never force-push automatically.

---

# Branch Safety

Before committing, identify the current branch:

```bash
git branch --show-current
```

If the branch is unexpected, do not assume the user wants the commit there.

Be especially careful on:

```text
main
master
production
release/*
```

Do not switch branches automatically.

Do not create or delete branches as part of this skill unless explicitly requested.

---

# Forbidden Destructive Operations

Never run these automatically:

```bash
git reset --hard
git clean -fd
git push --force
git checkout -- <file>
git restore <file>
```

unless the user explicitly requests the exact destructive operation.

Never discard uncommitted changes to simplify staging.

---

# Commit Validation

Before:

```bash
git commit
```

verify:

```text
[ ] staged diff is intentional
[ ] staged diff contains one logical change
[ ] correct Odoo module is identified
[ ] staged module changes belong to exactly one Odoo module
[ ] correct official Odoo tag or documented local extension is selected
[ ] subject matches the staged diff
[ ] subject is one line
[ ] tag is uppercase and description starts with lowercase
[ ] subject has no trailing period
[ ] no unrelated files are staged
[ ] no secrets are staged
```

Preferred command:

```bash
git commit -m "<one-line subject>"
```

Never create a commit body or footer.

---

# Output Contract

Resolve the execution mode first. For audit only, report findings and proposed commit groups and subjects without changing Git state. For either commit mode:

1. Inspect Git state.
2. Inspect unstaged and staged diffs.
3. Identify logical changes.
4. Split mixed changes when practical.
5. Stage only the intended change.
6. Inspect the staged diff.
7. Determine the Odoo module.
8. Determine the commit tag.
9. Create exactly one atomic commit.
10. Repeat for remaining logical changes when requested.
11. Verify the resulting Git state.
12. Push only in push-to-remote mode, after verifying the destination and outgoing commits.
13. Report the exact commit subject(s) that were created and whether they remain local or were pushed.

Do not claim a commit was created unless `git commit` actually succeeded. Do not claim commits were pushed unless the push succeeded.

---

# Example

Given:

```text
ab_ecommerce_storefront/
    account.xml
    account.scss
    return_policy.xml

ab_website_sale_product/
    sync_job.py
    sync_job_views.xml

README.md
```

If the changes represent three independent logical changes, create:

```text
ab_ecommerce_storefront/FIX: align account password mask in RTL layout
ab_ecommerce_storefront/IMP: add return policy page
ab_website_sale_product/IMP: run website product sync in background
```

and handle the README separately:

```text
DOCS: update project documentation
```

Do not combine them into one commit.

---

# Core Principle

When in doubt, optimize for:

```text
small
atomic
module-specific
reviewable
accurate
```

The Git history should tell the development story of the Odoo project clearly.

A commit should answer one question:

> **What single logical change does this commit represent?**
