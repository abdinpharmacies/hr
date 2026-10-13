---
name: git-commit
description: Create clean one-line Conventional Commits with an accurate optional scope, using diff inspection and interactive staging to keep each commit logically atomic. Use when the user asks to create, suggest, stage, split, amend, or make a Git commit.
---

# Git Commit Skill

Create and manage Git commits as clean, reviewable, atomic units.

## Non-Negotiable Commit Format

Every normal commit MUST be a single line and MUST use:

```text
<type>(<scope>): <description>
```

Scope is optional:

```text
<type>: <description>
```

Breaking changes use `!` before the colon:

```text
feat(api)!: remove legacy endpoint
```

Do NOT create a commit body, footer, multi-line message, explanation, or trailing period.

The only information allowed in the commit message is the one-line subject above.

## Commit Type Decision

Choose exactly one type by the following decision process:

1. `fix` — fixes an existing bug or incorrect behavior.
2. `feat` — adds, changes, or removes user-visible/API functionality or behavior.
3. `test` — adds, removes, or changes tests.
4. `perf` — a performance-focused code refactor whose primary purpose is measurable performance improvement.
5. `refactor` — restructures feature-related code without changing behavior or public API/UI behavior.
6. `style` — formatting or code-style-only changes with no behavior change.
7. `docs` — documentation-only changes.
8. `build` — dependencies, build tooling, project version, packaging, generated build configuration, or build-system changes.
9. `ops` — operational/infrastructure changes such as deployment, CI/CD, monitoring, backups, or infrastructure-as-code when they are not part of application behavior.
10. `chore` — maintenance or repository housekeeping that does not fit the categories above.

Do not use `chore` as a lazy fallback when a more specific type applies.

If a change spans multiple concerns, split it into separate logical commits when practical instead of inventing a vague type.

## Scope Rules

Scope is OPTIONAL, but USE IT when the changed area has a clear logical name.

Good scopes are project-specific logical areas such as:

```text
onboarding
home
auth
profile
api
storage
localization
theme
router
ci
```

Determine the scope from the repository's actual structure, feature names, module names, or subsystem names.

Rules:

- Prefer the smallest meaningful logical area that describes the change.
- Use one scope only.
- Do not use file names unless the file itself is the logical subsystem.
- Do not use class, method, variable, ticket, issue, PR, or task identifiers as scope.
- Do not invent a scope when the change genuinely spans unrelated areas; omit scope rather than using `misc`, `general`, or similar vague labels.
- Keep the scope concise.

## Description Rules

The description MUST:

- be concise and specific;
- describe what the commit changes;
- use imperative, present tense (e.g. `add`, `fix`, `remove`, `extract`, `update`);
- start with lowercase;
- have no trailing period;
- avoid filler such as `changes`, `updates`, `improvements`, `stuff`, `work`, or `minor changes`;
- avoid implementation trivia unless it is the actual purpose of the change.

Think:

```text
This commit will <description>
```

Prefer:

```text
feat(onboarding): add goal selection
fix(auth): preserve session after token refresh
refactor(home): extract workout summary widget
build: update Flutter dependencies
```

Avoid:

```text
feat(onboarding): updated goal selection.
fix: changes to auth
chore: minor improvements
update onboarding
implemented the new UI
```

## Inspect Before Committing

Before creating any commit:

1. Inspect repository state with `git status`.
2. Inspect the relevant unstaged changes with `git diff`.
3. Inspect staged changes with `git diff --cached` when anything is already staged.
4. Determine whether all changes belong to one logical commit.
5. If changes contain multiple unrelated concerns, split them before committing.

Never generate a commit message from filenames alone.
Never assume the user's working tree contains only the intended change.

## Staging Strategy

Prefer targeted staging over blindly running `git add .`.

Use path-based staging when the files form one coherent change:

```bash
git add <relevant-files-or-directory>
```

When a file contains changes belonging to different logical commits, use interactive staging:

```bash
git add -p
```

Use interactive staging to select only the hunks that belong to the current commit.

If necessary, use split/edit options from interactive staging to separate mixed hunks.

After staging, ALWAYS verify:

```bash
git diff --cached
```

The staged diff MUST contain only the changes represented by the commit subject.

Do not stage unrelated files, generated artifacts, local configuration, secrets, editor files, debug output, or temporary experiments unless they are intentionally part of the commit.

## Atomic Commit Rule

One commit MUST represent one coherent logical change.

Examples:

```text
feat(onboarding): add goal selection
```

should contain the implementation needed for goal selection, not unrelated login fixes or README edits.

If the working tree contains:

- a new feature;
- an unrelated bug fix;
- formatting changes;
- test changes for a different feature;

split them into separate commits when practical.

Do not create tiny meaningless commits merely to satisfy this rule. Keep tightly coupled implementation changes together when they form one coherent unit.

## Commit Message Generation

Derive the message from the FINAL staged diff, not from the entire working tree.

The message must summarize the primary logical change in the staged content.

Use the narrowest accurate type and scope.

Do not mention files unless that is the meaningful user-facing or subsystem-level change.

Do not include implementation details that are not useful in the one-line history.

## Validation Before Commit

Before executing `git commit`:

- confirm the staged diff is intentional;
- confirm the commit contains one logical change;
- confirm the subject matches the staged diff;
- confirm the message is exactly one line;
- confirm there is no period at the end;
- confirm the type and optional scope are valid;
- confirm breaking changes use `!` in the subject when applicable.

Preferred final command form:

```bash
git commit -m "<one-line conventional commit>"
```

## Existing Staged Changes

If the user already staged changes, treat the index as intentional until inspection shows otherwise.

Inspect:

```bash
git diff --cached
```

Do not automatically unstage or rewrite the user's staging area without a clear reason.

If the staged diff is coherent, commit it directly.

If it is mixed, explain which parts are unrelated and use targeted/interactive staging only when necessary.

## Existing Commit / Amend

Use `--amend` only when the user is clearly editing the most recent commit rather than creating a new logical commit.

For a forgotten file or corrected subject on the latest local commit:

```bash
git add <files>
git commit --amend --no-edit
```

or:

```bash
git commit --amend -m "<one-line conventional commit>"
```

Do not amend commits that have already been pushed/shared unless the user explicitly asks to rewrite history.

## Commit History Cleanup

During active development, temporary commits are acceptable when they help progress.

Before a pull request, clean local history when appropriate with interactive rebase:

```bash
git rebase -i <base>
```

Use `fixup!` commits and autosquash when useful:

```bash
git commit --fixup <commit>
git rebase -i --autosquash <base>
```

The final history should contain meaningful, reviewable commits rather than a trail of typo/fix/fix-again commits.

Do not rewrite shared history unless explicitly requested.

## Safety / Boundaries

Never run destructive Git commands such as:

```bash
git reset --hard
git clean -fd
git push --force
```

unless the user explicitly requests that exact destructive operation.

Never discard uncommitted changes just to make staging easier.

Never commit secrets, credentials, `.env` files, private keys, or obvious local-only configuration unless the repository clearly and intentionally tracks them.

## Output Contract

When asked to create a commit:

1. Inspect the relevant Git state and diff.
2. Stage/split changes as necessary.
3. Produce exactly one one-line Conventional Commit subject.
4. Commit using that exact subject.
5. Do not add a commit body or footer.
6. When reporting back, show the final commit subject exactly as created.
