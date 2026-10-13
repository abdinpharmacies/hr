---
name: odoo-git-commit
description: Create clean, atomic Conventional Commits for Odoo projects. Inspect the working tree and diffs, identify logical changes by Odoo module and feature area, split mixed changes when practical, stage only the intended changes, validate the staged diff, and create one focused commit per logical change.
---

# Odoo Git Commit Skill

Create clean, atomic, reviewable Git commits for Odoo projects.

The primary rule is:

> **One commit = one logical change.**

Do not group unrelated Odoo modules, features, bug fixes, documentation, formatting, or tests into one commit merely because they were changed at the same time.

---

## Commit Format

For Odoo module changes, use:

```text
<module>/<type>: <description>
```

Examples:

```text
ab_ecommerce_storefront/feat: add return policy page
ab_ecommerce_storefront/fix: limit purchase options to supported units
ab_website_sale_product/feat: run website product sync in background
ab_website_sale_product/fix: preserve manually edited website images
ab_website_seo_optimization/feat: add catalog-aware SEO enrichment workflow
```

For repository-wide changes that do not belong to one Odoo module, use:

```text
<type>: <description>
```

Examples:

```text
build: update project dependencies
ci: add automated module validation
docs: update development guide
```

Do NOT use the Conventional Commit parentheses format:

```text
feat(module): description
```

Use the Odoo repository convention:

```text
module/feat: description
```

---

# Commit Types

Use exactly one type.

## `feat`

Use when adding or changing user-visible, business, API, workflow, or functional behavior.

Examples:

```text
ab_ecommerce_storefront/feat: add return policy page
ab_ecommerce_storefront/feat: build category menu from published catalog
ab_website_sale_product/feat: run website product sync in background
```

---

## `fix`

Use when correcting existing incorrect behavior, bugs, regressions, validation problems, or broken workflows.

Examples:

```text
ab_ecommerce_storefront/fix: limit purchase options to supported units
ab_website_sale_product/fix: preserve manually edited website images
ab_website_sale_product/fix: enforce E-Plus stock limits in cart
```

---

## `docs`

Use only for documentation changes.

Examples:

```text
ab_ecommerce_storefront/docs: update storefront commit history
ab_website_sale_product/docs: record website sync commits
docs: update development guide
```

Documentation changes should normally be separated from functional implementation changes unless they are inseparable and intentionally part of the same logical change.

---

## `test`

Use when the primary purpose is adding, removing, or modifying tests.

Examples:

```text
ab_website_sale_product/test: add website sync regression coverage
ab_sales/test: cover order cancellation workflow
```

Tests that are tightly coupled to a feature or bug fix may remain in the same commit when they directly validate that change.

Do not automatically create a separate test commit when the test is part of the implementation of the same logical change.

---

## `perf`

Use when measurable performance improvement is the primary purpose.

Examples:

```text
ab_website_sale_product/perf: optimize website product sync batching
ab_ecommerce_storefront/perf: reduce storefront catalog queries
```

Do not use `perf` merely because a refactor might be faster.

---

## `refactor`

Use when restructuring code without intentionally changing behavior.

Examples:

```text
ab_website_sale_product/refactor: extract sync batch processing
ab_ecommerce_storefront/refactor: extract account validation helpers
```

If behavior changes, use `feat` or `fix` instead.

---

## `style`

Use only for formatting or code-style changes with no functional behavior change.

Examples:

```text
ab_ecommerce_storefront/style: format storefront templates
```

Do not use `style` for visual/UI behavior changes.

A CSS change that intentionally changes the website appearance is usually `feat` or `fix`, not `style`.

---

## `build`

Use for build-system, dependency, packaging, generated build configuration, or environment/build tooling changes.

Examples:

```text
build: update Python dependencies
build: update frontend asset configuration
```

---

## `ci`

Use for continuous integration and automated pipeline changes.

Examples:

```text
ci: add Odoo module validation pipeline
ci: run module tests on pull requests
```

---

## `chore`

Use only for repository maintenance that does not fit a more specific category.

Do not use `chore` as a generic fallback.

Prefer:

```text
build
ci
docs
test
refactor
perf
```

when one of those accurately describes the change.

---

## `revert`

Use when the purpose of the commit is explicitly to revert an earlier commit.

Example:

```text
ab_website_sale_product/revert: revert background sync processing
```

Do not use `revert` for an ordinary bug fix that happens to undo previous behavior.

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
feat: update ecommerce project
```

Instead, separate the changes:

```text
ab_ecommerce_storefront/fix: align account password mask in RTL layout
ab_website_sale_product/perf: optimize website product sync
ab_website_seo_optimization/feat: add catalog-aware SEO enrichment workflow
docs: update project documentation
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
ab_website_sale_product/fix: preserve manually edited website images
```

may contain:

```text
models/
tests/
```

in the same commit.

If tests are independent or represent a separate test-only change, use:

```text
ab_website_sale_product/test: add website image preservation coverage
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
ab_ecommerce_storefront/feat: add return policy page
```

Avoid:

```text
ab_ecommerce_storefront/feat: Added a new return policy page.
```

Avoid:

```text
ab_ecommerce_storefront/chore: changes
```

Avoid:

```text
ab_ecommerce_storefront/feat: modify several files for improvements
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
correct type
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
5. Determine commit type
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
[ ] correct commit type is selected
[ ] subject matches the staged diff
[ ] subject is one line
[ ] subject starts with lowercase
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

When the user asks to create commits:

1. Inspect Git state.
2. Inspect unstaged and staged diffs.
3. Identify logical changes.
4. Split mixed changes when practical.
5. Stage only the intended change.
6. Inspect the staged diff.
7. Determine the Odoo module.
8. Determine the commit type.
9. Create exactly one atomic commit.
10. Repeat for remaining logical changes when requested.
11. Verify the resulting Git state.
12. Report the exact commit subject(s) that were created.

Do not claim a commit was created unless `git commit` actually succeeded.

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
ab_ecommerce_storefront/fix: align account password mask in RTL layout
ab_ecommerce_storefront/feat: add return policy page
ab_website_sale_product/feat: run website product sync in background
```

and handle the README separately:

```text
docs: update project documentation
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
